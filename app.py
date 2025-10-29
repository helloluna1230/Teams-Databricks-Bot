# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

import sys
from datetime import datetime
from http import HTTPStatus
from aiohttp import web
from aiohttp.web import Request, Response
from botbuilder.core import (
    ConversationState,
    MemoryStorage,
    TurnContext,
    UserState,
)
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

from bots import AuthBot
import logging
import traceback

# Create the loop and Flask app
from config import DefaultConfig
from dialogs import MainDialog

CONFIG = DefaultConfig()

# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(CONFIG))


# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # Handles uncaught exceptions during turn execution
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Inform user that an error occurred
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )

    # Send a trace activity if using Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity for debugging
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send trace activity to emulator
        await context.send_activity(trace_activity)


# Assign the global error handler to the adapter
ADAPTER.on_turn_error = on_error

# Create MemoryStorage and state management objects
MEMORY = MemoryStorage()
USER_STATE = UserState(MEMORY)
CONVERSATION_STATE = ConversationState(MEMORY)

# Create dialog instance
DIALOG = MainDialog(CONFIG.CONNECTION_NAME,
                    CONFIG.DATABRICKS_HOST,
                    CONFIG.SERVING_ENDPOINT_NAME,
                    USER_STATE,
                    CONVERSATION_STATE)

# Create the main bot instance
BOT = AuthBot(CONVERSATION_STATE, USER_STATE, DIALOG)


# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    # Deserialize incoming request to Activity object
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    activity = Activity().deserialize(body)

    # Log incoming activity type and name
    logging.info(f"Incoming activity type: {activity.type}")
    logging.info(f"Activity name: {getattr(activity, 'name', None)}")

    try:
        # Process activity with the bot adapter and bot logic
        response = await ADAPTER.process(req, BOT)

        if response and response.body == b'null':
            response.body = None

        logging.info(f"Response output: {response}")
        logging.info(f"Response body output: {response.body}")

        return response

    except Exception as e:
        # Log unexpected errors during activity processing
        logging.error(f"Exception in processing activity: {e}")
        traceback.print_exc()
        return Response(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            text="Internal server error while processing the activity."
        )


# Create aiohttp app and register message route
APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

# Run aiohttp web server
if __name__ == "__main__":
    try:
        web.run_app(APP, host="0.0.0.0", port=CONFIG.PORT)
    except Exception as error:
        raise error
