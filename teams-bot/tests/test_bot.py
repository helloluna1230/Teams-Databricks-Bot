import unittest
from unittest.mock import AsyncMock, Mock

from microsoft_agents.activity import (
    Activity,
    ChannelAccount,
    ConversationAccount,
    ResourceResponse,
)
from microsoft_agents.hosting.aiohttp import CloudAdapter
from microsoft_agents.hosting.core import (
    ConversationState,
    MemoryStorage,
    TurnContext,
)

from bots import DatabricksBot
from client.databricks_client import DatabricksClient


class BotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Mock(spec=DatabricksClient)
        self.client.call_genie_space = AsyncMock(
            return_value=[{"role": "assistant", "content": "Genie answer"}]
        )
        self.client.call_model_endpoint = AsyncMock(
            return_value=[{"role": "assistant", "content": "Model answer"}]
        )
        self.storage = MemoryStorage()
        self.adapter = AsyncMock(spec=CloudAdapter)
        self.adapter.send_activities.return_value = [ResourceResponse(id="reply")]
        self.bot = DatabricksBot(self.client, self.storage, "space-id", "endpoint")

    def context(self, text="Question", conversation_id="conversation"):
        return TurnContext(
            self.adapter,
            Activity(
                type="message",
                channel_id="msteams",
                service_url="https://smba.trafficmanager.net/teams/",
                text=text,
                conversation=ConversationAccount(id=conversation_id),
                from_property=ChannelAccount(id="user"),
                recipient=ChannelAccount(id="bot"),
            ),
        )

    def sent_activities(self):
        return [
            activity
            for call in self.adapter.send_activities.call_args_list
            for activity in call.args[1]
        ]

    async def test_genie_takes_priority_over_model_serving(self):
        await self.bot.on_turn(self.context())
        self.client.call_genie_space.assert_awaited_once_with(
            "Question", "space-id"
        )
        self.client.call_model_endpoint.assert_not_awaited()
        self.assertEqual(self.sent_activities()[0].text, "Genie answer")

    async def test_genie_questions_remain_independent(self):
        await self.bot.on_turn(self.context("First"))
        await self.bot.on_turn(self.context("Second"))
        self.assertEqual(
            [call.args for call in self.client.call_genie_space.await_args_list],
            [("First", "space-id"), ("Second", "space-id")],
        )

    async def test_model_serving_receives_history(self):
        self.bot.genie_space_id = ""
        await self.bot.on_turn(self.context("First"))
        await self.bot.on_turn(self.context("Second"))
        self.client.call_model_endpoint.assert_awaited_with(
            "endpoint",
            "Second",
            [
                {"role": "user", "content": "First"},
                {"role": "assistant", "content": "Model answer"},
            ],
        )

    async def test_conversations_have_separate_history(self):
        self.bot.genie_space_id = ""
        await self.bot.on_turn(self.context("First", "one"))
        await self.bot.on_turn(self.context("Second", "two"))
        self.client.call_model_endpoint.assert_awaited_with(
            "endpoint", "Second", []
        )

    async def test_clear_preserves_existing_history_semantics(self):
        self.bot.genie_space_id = ""
        await self.bot.on_turn(self.context("First"))
        await self.bot.on_turn(self.context("CLEAR"))
        await self.bot.on_turn(self.context("Second"))
        self.assertEqual(self.client.call_model_endpoint.await_count, 2)
        self.assertEqual(
            self.client.call_model_endpoint.await_args.args[2][0]["content"],
            "First",
        )
        self.assertEqual(
            self.sent_activities()[1].text,
            "No active dialog state found to clear.",
        )

    async def test_clear_deletes_only_legacy_dialog_state(self):
        context = self.context("clear")
        state = ConversationState(self.storage)
        await state.load(context)
        state.set_value("DialogState", {"dialog_stack": ["old-dialog"]})
        state.set_value("history", [{"role": "user", "content": "First"}])
        await state.save(context)
        await self.bot.on_turn(self.context("clear"))
        state = ConversationState(self.storage)
        await state.load(self.context())
        self.assertIsNone(state.get_value("DialogState"))
        self.assertEqual(state.get_value("history")[0]["content"], "First")

    async def test_empty_message_gets_explicit_feedback(self):
        await self.bot.on_turn(self.context(" "))
        self.client.call_genie_space.assert_not_awaited()
        self.assertEqual(
            self.sent_activities()[0].text, "Please send a text question."
        )

    async def test_failure_propagates_to_adapter_error_handler(self):
        self.client.call_genie_space.side_effect = RuntimeError("denied")
        with self.assertRaisesRegex(RuntimeError, "denied"):
            await self.bot.on_turn(self.context())
        state = ConversationState(self.storage)
        await state.load(self.context())
        self.assertIsNone(state.get_value("history"))

    async def test_tool_result_is_sent_as_adaptive_card(self):
        response = [
            {
                "role": "assistant",
                "content": "Checking data",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {"name": "query", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call-1", "content": "42"},
            {"role": "assistant", "content": "The answer is 42"},
        ]
        self.client.call_genie_space.return_value = response
        await self.bot.on_turn(self.context())
        activities = self.sent_activities()
        self.assertEqual(len(activities), 3)
        card = activities[1].attachments[0]
        self.assertEqual(
            card.content_type, "application/vnd.microsoft.card.adaptive"
        )
        self.assertEqual(
            card.content["body"][1]["facts"][-1]["value"], "42"
        )

    async def test_unmatched_tool_result_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no matching tool call"):
            await self.bot.send_response_activities(
                self.context(),
                [{"role": "tool", "tool_call_id": "missing", "content": "42"}],
            )

    async def test_welcome_does_not_advertise_logout(self):
        context = self.context()
        context.activity.type = "conversationUpdate"
        context.activity.members_added = [
            ChannelAccount(id="bot"),
            ChannelAccount(id="user"),
        ]
        await self.bot.on_turn(context)
        self.assertEqual(len(self.sent_activities()), 1)
        self.assertNotIn("logout", self.sent_activities()[0].text)
