#!/usr/bin/env python3
# Copyright © Databricks, Inc. All rights reserved.
# Licensed under the MIT License.

import os

""" Bot Configuration """


class DefaultConfig:
    """ Bot Configuration """

    PORT = 8000
    APP_ID = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
    APP_TYPE = os.environ.get("MicrosoftAppType", "")
    APP_TENANTID = os.environ.get("MicrosoftTenantId", "")
    CONNECTION_NAME = os.environ.get("ConnectionName", "")
    DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
    SERVING_ENDPOINT_NAME = os.environ.get("SERVING_ENDPOINT_NAME", "")
    GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
