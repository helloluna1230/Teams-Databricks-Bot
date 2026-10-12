import json
import time
import unittest
from unittest.mock import AsyncMock, patch

import jwt
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from cryptography.hazmat.primitives.asymmetric import rsa
from microsoft_agents.authentication.msal import MsalAuth
from microsoft_agents.hosting.core.authorization.jwt.jwt_token_validator import (
    JwtTokenValidator,
)
from microsoft_agents.hosting.aiohttp import CloudAdapter

from app import create_app, on_turn_error
from client.databricks_client import DatabricksClient


class AppTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.signing_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        cls.other_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )

    def token(self, audience=None, signing_key=None, expires=None):
        return jwt.encode(
            {
                "iss": "https://api.botframework.com",
                "aud": audience or "11111111-1111-1111-1111-111111111111",
                "exp": time.time() + 600 if expires is None else expires,
                "nbf": time.time() - 60,
                "serviceurl": "https://smba.trafficmanager.net/teams/",
            },
            signing_key or self.signing_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    async def asyncSetUp(self):
        self.app = create_app(
            {
                "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID":
                    "11111111-1111-1111-1111-111111111111",
                "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE":
                    "UserManagedIdentity",
                "DATABRICKS_AUTH_TYPE": "oauth-m2m",
                "GENIE_SPACE_ID": "space-id",
            }
        )
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_missing_token_is_rejected_before_adapter(self):
        with patch.object(CloudAdapter, "process", new_callable=AsyncMock) as process:
            response = await self.client.post(
                "/api/messages", json={"type": "message", "text": "Hello"}
            )
        self.assertEqual(response.status, 401)
        process.assert_not_awaited()

    async def test_invalid_token_is_rejected_before_adapter(self):
        with patch.object(CloudAdapter, "process", new_callable=AsyncMock) as process:
            response = await self.client.post(
                "/api/messages",
                json={"type": "message", "text": "Hello"},
                headers={"Authorization": "Bearer invalid-token"},
            )
        self.assertEqual(response.status, 401)
        process.assert_not_awaited()

    async def test_signed_request_runs_real_adapter_and_bot(self):
        with (
            patch.object(
                MsalAuth,
                "get_access_token",
                new_callable=AsyncMock,
                return_value="test-access-token",
            ),
            patch.object(
                JwtTokenValidator._jwk_client_manager,
                "get_signing_key",
                new_callable=AsyncMock,
                return_value=self.signing_key.public_key(),
            ),
            patch.object(
                DatabricksClient,
                "call_genie_space",
                new_callable=AsyncMock,
                return_value=[{"role": "assistant", "content": "Genie answer"}],
            ) as query,
        ):
            response = await self.client.post(
                "/api/messages",
                headers={"Authorization": "Bearer " + self.token()},
                json={
                    "type": "message",
                    "channelId": "msteams",
                    "serviceUrl": "https://smba.trafficmanager.net/teams/",
                    "conversation": {"id": "conversation"},
                    "from": {"id": "user"},
                    "recipient": {"id": "bot"},
                    "text": "Question",
                    "deliveryMode": "expectReplies",
                },
            )
            body = await response.json()
        self.assertEqual(response.status, 200, body)
        self.assertEqual(body["activities"][0]["text"], "Genie answer")
        query.assert_awaited_once_with("Question", "space-id")

    async def test_signed_invalid_tokens_are_rejected(self):
        tokens = [
            self.token(audience="different-bot"),
            self.token(signing_key=self.other_key),
            self.token(expires=time.time() - 600),
        ]
        with (
            patch.object(
                JwtTokenValidator._jwk_client_manager,
                "get_signing_key",
                new_callable=AsyncMock,
                return_value=self.signing_key.public_key(),
            ),
            patch.object(CloudAdapter, "process", new_callable=AsyncMock) as process,
        ):
            for token in tokens:
                with self.subTest(token_type=tokens.index(token)):
                    response = await self.client.post(
                        "/api/messages",
                        headers={"Authorization": "Bearer " + token},
                        json={"type": "message"},
                    )
                    self.assertEqual(response.status, 401)
        process.assert_not_awaited()

    async def test_real_adapter_reports_query_failure(self):
        with (
            patch.object(
                JwtTokenValidator._jwk_client_manager,
                "get_signing_key",
                new_callable=AsyncMock,
                return_value=self.signing_key.public_key(),
            ),
            patch.object(
                MsalAuth,
                "get_access_token",
                new_callable=AsyncMock,
                return_value="test-access-token",
            ),
            patch.object(
                DatabricksClient,
                "call_genie_space",
                new_callable=AsyncMock,
                side_effect=RuntimeError("query denied"),
            ),
            self.assertLogs("app", level="ERROR"),
        ):
            response = await self.client.post(
                "/api/messages",
                headers={"Authorization": "Bearer " + self.token()},
                json={
                    "type": "message",
                    "channelId": "msteams",
                    "serviceUrl": "https://smba.trafficmanager.net/teams/",
                    "conversation": {"id": "conversation"},
                    "from": {"id": "user"},
                    "recipient": {"id": "bot"},
                    "text": "Question",
                    "deliveryMode": "expectReplies",
                },
            )
            body = await response.json()
        self.assertEqual(response.status, 200, body)
        self.assertEqual(
            body["activities"][0]["text"],
            "Agent is not available at this moment.",
        )

    async def test_real_adapter_rejects_missing_conversation(self):
        with patch.object(
            JwtTokenValidator._jwk_client_manager,
            "get_signing_key",
            new_callable=AsyncMock,
            return_value=self.signing_key.public_key(),
        ):
            response = await self.client.post(
                "/api/messages",
                headers={"Authorization": "Bearer " + self.token()},
                json={"type": "message", "text": "Question"},
            )
        self.assertEqual(response.status, 400)

    async def test_get_routes_preserve_existing_status_codes(self):
        response = await self.client.get("/")
        self.assertEqual(response.status, 404)
        response = await self.client.get("/api/messages")
        self.assertEqual(response.status, 405)

    async def test_authenticated_request_is_forwarded_to_adapter(self):
        async def authenticated(request, handler):
            return await handler(request)

        with (
            patch("app.jwt_authorization_middleware", authenticated),
            patch.object(
                CloudAdapter,
                "process",
                new_callable=AsyncMock,
                return_value=web.Response(status=201),
            ) as process,
        ):
            response = await self.client.post(
                "/api/messages", json={"type": "message"}
            )
        self.assertEqual(response.status, 201)
        process.assert_awaited_once()

    async def test_malformed_activity_has_explicit_error_response(self):
        async def authenticated(request, handler):
            return await handler(request)

        with (
            patch("app.jwt_authorization_middleware", authenticated),
            patch.object(
                CloudAdapter,
                "process",
                new_callable=AsyncMock,
                side_effect=json.JSONDecodeError("Invalid JSON", "", 0),
            ),
        ):
            response = await self.client.post("/api/messages", data="{")
        self.assertEqual(response.status, 400)
        self.assertEqual(
            await response.json(), {"error": "Invalid activity payload"}
        )

    async def test_adapter_errors_are_logged_and_reported(self):
        context = AsyncMock()
        with self.assertLogs("app", level="ERROR"):
            await on_turn_error(context, RuntimeError("query failed"))
        context.send_activity.assert_awaited_once_with(
            "Agent is not available at this moment."
        )
