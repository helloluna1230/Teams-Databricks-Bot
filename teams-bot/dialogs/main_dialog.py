# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import ConversationState, CardFactory, MessageFactory
from botbuilder.dialogs import (
    ComponentDialog,
    WaterfallDialog,
    WaterfallStepContext,
)

from client.databricks_client import DatabricksClient
import logging
# Set the logging level to INFO
logging.basicConfig(level=logging.INFO)

tool_card_placeholder = {
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {
      "type": "TextBlock",
      "text": "Agent Tool Call",
      "weight": "Bolder",
      "size": "Medium"
    },
    {
      "type": "FactSet",
      "facts": [
      ]
    }
  ]
}

class MainDialog(ComponentDialog):
    def __init__(self, databricks_host:str,
                 databricks_token: str,
                 databricks_auth_type: str,
                 databricks_client_id: str,
                 databricks_client_secret: str,
                 databricks_azure_resource_id: str,
                 databricks_azure_client_id: str,
                 serving_endpoint_name: str,
                 genie_space_id: str,
                 conversation_state: ConversationState):
        super(MainDialog, self).__init__(MainDialog.__name__)
        self.conversation_state = conversation_state

        self.history = self.conversation_state.create_property('history')

        self.databricks_client = DatabricksClient(
            databricks_host,
            databricks_token,
            databricks_auth_type,
            databricks_client_id,
            databricks_client_secret,
            databricks_azure_resource_id,
            databricks_azure_client_id,
        )
        self.serving_endpoint_name = serving_endpoint_name
        self.genie_space_id = genie_space_id

        self.add_dialog(
            WaterfallDialog(
                "WFDialog",
                [
                    self.api_call_step
                ],
            )
        )

        self.initial_dialog_id = "WFDialog"

    def create_tool_call_card(self, tool_call_info):

        tool_card = tool_card_placeholder.copy()

        tool_card["body"][1]["facts"] = [{ "title": "Tool", "value": tool_call_info["name"]},
        { "title": "Params", "value": tool_call_info["arguments"]},
        { "title": "Result", "value": tool_call_info["output"] }]

        return tool_card

    async def send_response_activities(self, input_text, response, new_history, dc_context):
        new_history.append({"role": "user", "content": input_text})
        new_history.extend(response)
        tool_calls = dict()
        for item in response:
            if item["role"] == "assistant" and "tool_calls" not in item:
                await dc_context.send_activity(item["content"])
            elif item["role"] == "assistant" and "tool_calls" in item:
                if item["content"]:
                    await dc_context.send_activity(item["content"])
                for tool_call in item["tool_calls"]:
                    tool_calls[tool_call["id"]] = tool_call
            elif item["role"] == "tool":
                assert item[
                           "tool_call_id"] in tool_calls, f"Every tool call must have a tool result. Call id: {item['tool_call_id']}"
                tool_call = tool_calls[item["tool_call_id"]]
                tool_info = {"name": tool_call["function"]["name"],
                             "arguments": tool_call["function"]["arguments"],
                             "output": item["content"]}
                activity = MessageFactory.attachment(
                    CardFactory.adaptive_card(self.create_tool_call_card(tool_info)))
                await dc_context.send_activity(activity)
        return new_history

    async def api_call_step(self, step_context: WaterfallStepContext):
        try:
            input_text = step_context.context.activity.text
            actual_history = await self.history.get(step_context.context, default_value_or_factory=list)
            if self.genie_space_id:
                response = await self.databricks_client.call_genie_space(
                    input_text,
                    self.genie_space_id,
                )
            else:
                response = await self.databricks_client.call_model_endpoint(
                    self.serving_endpoint_name,
                    input_text,
                    actual_history,
                )
            new_history = await self.send_response_activities(input_text,
                                                              response,
                                                              actual_history,
                                                              step_context.context)
            await self.history.set(step_context.context, new_history)
            return await step_context.end_dialog()
        except Exception as error:
            logging.error(str(error))
            await step_context.context.send_activity("Agent is not available at this moment.")
            return await step_context.end_dialog()

