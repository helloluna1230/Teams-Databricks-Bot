# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

import os
from collections.abc import Mapping

from microsoft_agents.activity import load_configuration_from_env


def load_agent_configuration(environment: Mapping[str, str]) -> dict:
    config = load_configuration_from_env(environment)
    settings = config["CONNECTIONS"].get("SERVICE_CONNECTION", {}).get(
        "SETTINGS", {}
    )
    for name in ("CLIENTID", "AUTHTYPE"):
        if not settings.get(name):
            raise ValueError(
                f"CONNECTIONS__SERVICE_CONNECTION__SETTINGS__{name} is required. "
                "Migrate the legacy MicrosoftApp settings before starting."
            )
    if str(settings.get("ANONYMOUS_ALLOWED", "false")).lower() != "false":
        raise ValueError("Anonymous access to /api/messages is not allowed.")
    return config


class DefaultConfig:
    def __init__(self, environment: Mapping[str, str] | None = None):
        environment = os.environ if environment is None else environment
        self.PORT = int(environment.get("PORT", "8000"))
        self.DATABRICKS_HOST = environment.get("DATABRICKS_HOST", "")
        self.DATABRICKS_TOKEN = environment.get("DATABRICKS_TOKEN", "")
        self.DATABRICKS_AUTH_TYPE = environment.get(
            "DATABRICKS_AUTH_TYPE", "pat"
        )
        self.DATABRICKS_CLIENT_ID = environment.get("DATABRICKS_CLIENT_ID", "")
        self.DATABRICKS_CLIENT_SECRET = environment.get(
            "DATABRICKS_CLIENT_SECRET", ""
        )
        self.DATABRICKS_AZURE_RESOURCE_ID = environment.get(
            "DATABRICKS_AZURE_RESOURCE_ID", ""
        )
        self.DATABRICKS_AZURE_CLIENT_ID = environment.get(
            "DATABRICKS_AZURE_CLIENT_ID"
        ) or environment.get(
            "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID", ""
        )
        self.SERVING_ENDPOINT_NAME = environment.get("SERVING_ENDPOINT_NAME", "")
        self.GENIE_SPACE_ID = environment.get("GENIE_SPACE_ID", "")
