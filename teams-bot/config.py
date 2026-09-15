#!/usr/bin/env python3
# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

import os

""" Bot Configuration """


class DefaultConfig:
    """ Bot Configuration """

    PORT = 8000
    APP_ID = os.environ.get("MicrosoftAppId") or os.environ.get("MicrosoftAppID", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
    APP_TYPE = os.environ.get("MicrosoftAppType", "")
    APP_TENANTID = os.environ.get("MicrosoftTenantId", "")
    DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
    DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")
    DATABRICKS_AUTH_TYPE = os.environ.get("DATABRICKS_AUTH_TYPE", "pat")
    DATABRICKS_CLIENT_ID = os.environ.get("DATABRICKS_CLIENT_ID", "")
    DATABRICKS_CLIENT_SECRET = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
    DATABRICKS_AZURE_RESOURCE_ID = os.environ.get("DATABRICKS_AZURE_RESOURCE_ID", "")
    DATABRICKS_AZURE_CLIENT_ID = os.environ.get("DATABRICKS_AZURE_CLIENT_ID") or APP_ID
    SERVING_ENDPOINT_NAME = os.environ.get("SERVING_ENDPOINT_NAME", "")
    GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
