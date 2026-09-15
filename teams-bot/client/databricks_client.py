# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

import asyncio
import logging
import uuid

from azure.identity import ManagedIdentityCredential
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks_ai_bridge.genie import Genie


DATABRICKS_AZURE_SCOPE = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"

class DatabricksClient:
    def __init__(self, databricks_host: str, token: str, auth_type: str,
                 client_id: str, client_secret: str,
                 azure_workspace_resource_id: str,
                 azure_client_id: str):
        self.databricks_host = databricks_host
        self.token = token
        self.auth_type = auth_type
        self.client_id = client_id
        self.client_secret = client_secret
        self.azure_workspace_resource_id = azure_workspace_resource_id
        self.azure_client_id = azure_client_id
        self.workspace_client = None
        self.managed_identity_credential = None

        if auth_type == "azure-managed-identity-oauth":
            self.managed_identity_credential = ManagedIdentityCredential(
                client_id=azure_client_id
            )

    def _get_workspace_client(self):
        if self.managed_identity_credential:
            access_token = self.managed_identity_credential.get_token(
                DATABRICKS_AZURE_SCOPE
            )
            return WorkspaceClient(
                config=Config(
                    host=self.databricks_host,
                    token=access_token.token,
                    auth_type="pat",
                )
            )

        if self.workspace_client is None:
            if self.auth_type == "oauth-m2m":
                config = Config(
                    host=self.databricks_host,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    auth_type="oauth-m2m",
                )
            elif self.token:
                config = Config(
                    host=self.databricks_host,
                    token=self.token,
                    auth_type="pat",
                )
            else:
                config = Config(
                    host=self.databricks_host,
                    azure_workspace_resource_id=self.azure_workspace_resource_id,
                    azure_client_id=self.azure_client_id,
                    azure_use_msi=True,
                    auth_type="azure-msi",
                )
            self.workspace_client = WorkspaceClient(config=config)
        return self.workspace_client

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
                                  history:list):
        workspace_client = self._get_workspace_client()
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
                               genie_space_id: str) -> list:
        message = await asyncio.to_thread(
            self._get_workspace_client().genie.start_conversation_and_wait,
            genie_space_id,
            question,
        )
        answers = [
            attachment.text.content
            for attachment in message.attachments or []
            if attachment.text
            and attachment.text.content
        ]
        if not answers:
            raise Exception("Genie completed without an answer attachment")
        return [{"role": "assistant", "content": "\n\n".join(answers)}]
