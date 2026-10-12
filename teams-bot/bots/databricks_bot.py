# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

from microsoft_agents.activity import ChannelAccount
from microsoft_agents.hosting.core import (
    ActivityHandler,
    CardFactory,
    ConversationState,
    MessageFactory,
    Storage,
    TurnContext,
)

from client.databricks_client import DatabricksClient


class DatabricksBot(ActivityHandler):
    def __init__(
        self,
        client: DatabricksClient,
        storage: Storage,
        genie_space_id: str,
        serving_endpoint_name: str,
    ):
        super().__init__()
        self.client = client
        self.storage = storage
        self.genie_space_id = genie_space_id
        self.serving_endpoint_name = serving_endpoint_name

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Welcome to Databricks Bot Example. "
                    "Ask a question about your data."
                )

    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text
        if not text or not text.strip():
            await turn_context.send_activity("Please send a text question.")
            return

        # SDK state caches belong to a turn, not to the shared bot instance.
        state = ConversationState(self.storage)
        await state.load(turn_context)
        if text.strip().lower() == "clear":
            if state.get_value("DialogState"):
                state.delete_value("DialogState")
                await state.save(turn_context)
                await turn_context.send_activity(
                    "Dialog state cleared. You can start again."
                )
            else:
                await turn_context.send_activity(
                    "No active dialog state found to clear."
                )
            return

        history = state.get_value("history", list)
        if not isinstance(history, list):
            raise ValueError("Conversation history must be a list.")
        if self.genie_space_id:
            response = await self.client.call_genie_space(
                text, self.genie_space_id
            )
        else:
            response = await self.client.call_model_endpoint(
                self.serving_endpoint_name, text, history
            )

        await self.send_response_activities(turn_context, response)
        state.set_value(
            "history", history + [{"role": "user", "content": text}] + response
        )
        await state.save(turn_context)

    async def send_response_activities(
        self, turn_context: TurnContext, response: list
    ):
        tool_calls = {}
        for item in response:
            if item["role"] == "assistant" and "tool_calls" not in item:
                await turn_context.send_activity(item["content"])
            elif item["role"] == "assistant":
                if item["content"]:
                    await turn_context.send_activity(item["content"])
                for tool_call in item["tool_calls"]:
                    tool_calls[tool_call["id"]] = tool_call
            elif item["role"] == "tool":
                call_id = item["tool_call_id"]
                if call_id not in tool_calls:
                    raise ValueError(
                        f"Tool result has no matching tool call: {call_id}"
                    )
                function = tool_calls[call_id]["function"]
                card = {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.5",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Agent Tool Call",
                            "weight": "Bolder",
                            "size": "Medium",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Tool", "value": function["name"]},
                                {
                                    "title": "Params",
                                    "value": function["arguments"],
                                },
                                {"title": "Result", "value": item["content"]},
                            ],
                        },
                    ],
                }
                await turn_context.send_activity(
                    MessageFactory.attachment(CardFactory.adaptive_card(card))
                )
