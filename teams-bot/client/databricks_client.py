# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

import logging
import uuid

import httpx
from databricks.sdk import WorkspaceClient
from databricks_ai_bridge.genie import Genie

class DatabricksClient:
    def __init__(self, databricks_host: str, request_timeout: float = 300):
        self.databricks_host = databricks_host
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout),
        )

    async def exchange_token(self, provider_oauth_token: str):

        url = f"{self.databricks_host}/oidc/v1/token"

        data = {
            "subject_token": provider_oauth_token,  # replace with your JWT token variable
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "scope": "all-apis"
        }

        response = await self.client.post(url, data=data)

        return response.json()['access_token']

    def _throw_unexpected_endpoint_format(self):
        raise Exception("This app can only run against ChatModel, ChatAgent, or ResponsesAgent endpoints")

    def _convert_to_responses_format(self, messages):
        """Convert chat messages to ResponsesAgent API format."""
        input_messages = []
        for msg in messages:
            if msg["role"] == "user":
                input_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                # Handle assistant messages with tool calls
                if msg.get("tool_calls"):
                    # Add function calls
                    for tool_call in msg["tool_calls"]:
                        input_messages.append({
                            "type": "function_call",
                            "id": tool_call["id"],
                            "call_id": tool_call["id"],
                            "name": tool_call["function"]["name"],
                            "arguments": tool_call["function"]["arguments"]
                        })
                    # Add assistant message if it has content
                    if msg.get("content"):
                        input_messages.append({
                            "type": "message",
                            "id": msg.get("id", str(uuid.uuid4())),
                            "content": [{"type": "output_text", "text": msg["content"]}],
                            "role": "assistant"
                        })
                else:
                    # Regular assistant message
                    input_messages.append({
                        "type": "message",
                        "id": msg.get("id", str(uuid.uuid4())),
                        "content": [{"type": "output_text", "text": msg["content"]}],
                        "role": "assistant"
                    })
            elif msg["role"] == "tool":
                input_messages.append({
                    "type": "function_call_output",
                    "call_id": msg.get("tool_call_id"),
                    "output": msg["content"]
                })
        return input_messages

    def _parse_responses_output(self, response):
        result_messages = []

        logging.info(f"Response from openai client: {response}")

        for item in response.output:
            logging.info(f"Item type: {item.type}")
            if item.type == "message":
                content = "".join([e.text for e in item.content if e.type == "output_text"])
                if content:
                    result_messages.append({"role": "assistant", "content": content})
            elif item.type == "function_call":
                tool_calls = [{"id": item.call_id,
                               "type": "function",
                               "function": {"name": item.name,
                                            "arguments": item.arguments}}]

                result_messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
            elif item.type == "function_call_output":
                result_messages.append({"role": "tool", "content": item.output, "tool_call_id": item.call_id})

        logging.info(f"Response parsed from openai client: {result_messages}")
        return result_messages

    def _parse_chat_response(self, response):

        logging.info(f"Response from openai client: {response}")

        result_messages = []
        if hasattr(response, "messages") and response.messages:
            result_messages.extend(response.messages)
        elif hasattr(response, "choices") and response.choices:
            choice_message = response.choices[0].message
            message_content = choice_message.content
            if isinstance(choice_message.content, list):
                message_content = "".join(
                    [part.get("text", "") for part in choice_message.content if part.get("type") == "text"])
            message = {"role": "assistant", "content": message_content}
            if choice_message.tool_calls:
                message["tool_calls"] = choice_message.tool_calls
            result_messages.append(message)
        return result_messages

    def _get_endpoint_task_type(self, workspace_client, endpoint_name: str) -> str:
        """Get the task type of a serving endpoint."""
        try:
            ep = workspace_client.serving_endpoints.get(endpoint_name)
            return ep.task if ep.task else "chat/completions"
        except Exception:
            return "chat/completions"

    def _query_responses_endpoint(self,
                                  workspace_client,
                                  messages: list,
                                  serving_endpoint_name: str) -> list:

        input_messages = self._convert_to_responses_format(messages)

        openai_client = workspace_client.serving_endpoints.get_open_ai_client()

        response = openai_client.responses.create(model=serving_endpoint_name, input=input_messages)

        result_messages = self._parse_responses_output(response)

        if not result_messages:
            self._throw_unexpected_endpoint_format()

        return result_messages

    def _query_chat_endpoint(self, workspace_client, messages: list, serving_endpoint_name: str) -> list:
        """Calls a model serving endpoint with chat/completions format."""

        openai_client = workspace_client.serving_endpoints.get_open_ai_client()

        res = openai_client.chat.completions.create(model=serving_endpoint_name, messages=messages)

        result_messages = self._parse_chat_response(res)

        if not result_messages:
            self._throw_unexpected_endpoint_format()

        return result_messages

    async def call_model_endpoint(self,
                                  serving_endpoint_name: str,
                                  text:str,
                                  provider_oauth_token: str,
                                  history:list):

        oauth_db_token = await self.exchange_token(provider_oauth_token)

        workspace_client = WorkspaceClient(host=self.databricks_host, token=oauth_db_token)

        task_type = self._get_endpoint_task_type(workspace_client, serving_endpoint_name)

        logging.info(f"Serving endpoint task type: {task_type}")

        logging.info(f"Actual history in the chatbot: {history}")

        messages = history + [{"role": "user", "content": text}]

        if task_type == "agent/v1/responses":
            result_messages = self._query_responses_endpoint(workspace_client, messages, serving_endpoint_name)
        else:
            result_messages = self._query_chat_endpoint(workspace_client, messages, serving_endpoint_name)

        return result_messages

    async def call_genie_space(self, question: str,
                               provider_oauth_token:str,
                               conversation_id: str,
                               genie_space_id: str):

        oauth_db_token = await self.exchange_token(provider_oauth_token)

        workspace_client = WorkspaceClient(host=self.databricks_host, token=oauth_db_token)

        genie = Genie(genie_space_id, workspace_client)

        genie_result = genie.ask_question(question, conversation_id)

        return genie_result.result
