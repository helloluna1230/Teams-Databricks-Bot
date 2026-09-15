# Teams Demo Agent

This MLflow `ResponsesAgent` is deployed to Databricks Model Serving and answers data questions through the `Teams NYC Taxi Data` Genie Space.

The registered Unity Catalog model is `databricksdemo.default.teams_demo_agent`. Run `deploy.py` with `DATABRICKS_HOST` and `DATABRICKS_TOKEN` configured to log, register, and deploy it.