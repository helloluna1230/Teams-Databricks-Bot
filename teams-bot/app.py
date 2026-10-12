# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

import json
import logging
import os
from collections.abc import Mapping

from aiohttp import web
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.aiohttp import (
    CloudAdapter,
    jwt_authorization_middleware,
)
from microsoft_agents.hosting.core import MemoryStorage, TurnContext
from pydantic import ValidationError

from bots import DatabricksBot
from client.databricks_client import DatabricksClient
from config import DefaultConfig, load_agent_configuration

logger = logging.getLogger(__name__)


@web.middleware
async def authorize_messages(request: web.Request, handler):
    if request.method == "POST" and request.path == "/api/messages":
        return await jwt_authorization_middleware(request, handler)
    return await handler(request)


async def on_turn_error(context: TurnContext, error: Exception):
    logger.error(
        "Unhandled error while processing an activity",
        exc_info=(type(error), error, error.__traceback__),
    )
    await context.send_activity("Agent is not available at this moment.")


def create_app(environment: Mapping[str, str] | None = None) -> web.Application:
    environment = os.environ if environment is None else environment
    config = DefaultConfig(environment)
    connection_manager = MsalConnectionManager(
        **load_agent_configuration(environment)
    )
    adapter = CloudAdapter(connection_manager=connection_manager)
    adapter.on_turn_error = on_turn_error
    client = DatabricksClient(
        config.DATABRICKS_HOST,
        config.DATABRICKS_TOKEN,
        config.DATABRICKS_AUTH_TYPE,
        config.DATABRICKS_CLIENT_ID,
        config.DATABRICKS_CLIENT_SECRET,
        config.DATABRICKS_AZURE_RESOURCE_ID,
        config.DATABRICKS_AZURE_CLIENT_ID,
    )
    bot = DatabricksBot(
        client,
        MemoryStorage(),
        config.GENIE_SPACE_ID,
        config.SERVING_ENDPOINT_NAME,
    )

    async def messages(request: web.Request) -> web.Response:
        try:
            return await adapter.process(request, bot)
        except (json.JSONDecodeError, ValidationError) as error:
            logger.warning("Invalid activity payload: %s", type(error).__name__)
            return web.json_response(
                {"error": "Invalid activity payload"}, status=400
            )

    app = web.Application(middlewares=[authorize_messages])
    # The SDK's JWT middleware requires this literal application key.
    app["agent_configuration"] = (
        connection_manager.get_default_connection_configuration()
    )
    app.router.add_post("/api/messages", messages)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(
        create_app(), host="0.0.0.0", port=DefaultConfig().PORT
    )
