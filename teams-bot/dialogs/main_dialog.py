# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import UserState, ConversationState, CardFactory, MessageFactory
from botbuilder.dialogs import (
    WaterfallDialog,
    WaterfallStepContext,
)
from botbuilder.dialogs.prompts import OAuthPrompt, OAuthPromptSettings

from client.databricks_client import DatabricksClient
from dialogs import LogoutDialog
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

class MainDialog(LogoutDialog):
    def __init__(self, connection_name: str,
                 databricks_host:str,
                 serving_endpoint_name: str,
                 user_state: UserState,
                 conversation_state: ConversationState):

        # Initializes the MainDialog with OAuthPrompt and WaterfallDialog.
        super(MainDialog, self).__init__(MainDialog.__name__, connection_name)

        self.user_state = user_state
        self.conversation_state = conversation_state

        self.connection_name = connection_name

        self.user_login_accessor = self.user_state.create_property('has_logged_in')
        self.history = self.conversation_state.create_property('history')

        self.oauth_prompt = OAuthPrompt(
                OAuthPrompt.__name__,
                OAuthPromptSettings(
                    connection_name=connection_name,
                    text="Sign into Databricks to chat with agents.",
                    title="Sign In",
                    timeout=300000
                )
            )
        self.databricks_client = DatabricksClient(databricks_host)
        self.serving_endpoint_name = serving_endpoint_name

        self.add_dialog(self.oauth_prompt)

        self.add_dialog(
            WaterfallDialog(
                "WFDialog",
                [
                    self.ensure_signin_step,
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

    async def ensure_signin_step(self, step_context: WaterfallStepContext):
        # Try to retrieve the token
        token_response = await self.oauth_prompt.get_user_token(step_context.context)
        if not token_response or not getattr(token_response, "token", None):
            await self.user_login_accessor.set(step_context.context, False)
            # No valid token: begin OAuthPrompt
            return await step_context.begin_dialog(OAuthPrompt.__name__)
        await self.user_login_accessor.set(step_context.context, True)
        # Token is valid, move to next step using token as result
        return await step_context.next(token_response)

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
        token_response = step_context.result
        has_logged_in = await self.user_login_accessor.get(step_context.context, False)
        if token_response and token_response.token and not has_logged_in:
            # Set flag after first login completes
            await self.user_login_accessor.set(step_context.context, True)

            await step_context.context.send_activity("You are now logged in.")
            # Do NOT call API on first login
            return await step_context.end_dialog()
        elif token_response and token_response.token:
            try:
                # Call Databricks agent API.
                input_text = step_context.context.activity.text.lower()
                actual_history = await self.history.get(step_context.context, default_value_or_factory=list)
                response = await self.databricks_client.call_model_endpoint(self.serving_endpoint_name,
                                                                            input_text,
                                                                            str(token_response.token),
                                                                            actual_history)
                new_history = await self.send_response_activities(input_text,
                                                                  response,
                                                                  actual_history,
                                                                  step_context.context)
                await self.history.set(step_context.context, new_history)
                return await step_context.end_dialog()
            except Exception as e:
                logging.error(str(e))
                await step_context.context.send_activity("Agent is not available at this moment.")
                return await step_context.end_dialog()
        else:
            await step_context.context.send_activity("Authentication failed.")
            return await step_context.end_dialog()

