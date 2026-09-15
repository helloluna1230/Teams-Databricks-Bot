# Databricks Agent Bot for Microsoft Teams

This demo connects Microsoft Teams to a Databricks serving endpoint. The bot uses a user-assigned Azure managed identity to call Databricks, so Teams users do not sign in to the Azure tenant that owns the Databricks workspace.

## Authentication model

1. Teams sends activities to Azure Bot Service.
2. Azure Bot Service forwards them to this application on Azure App Service.
3. The application authenticates to Databricks with its user-assigned managed identity.
4. Every Teams user shares that Databricks service principal's permissions and audit identity.

This mode is intended for demos or workloads where per-user Databricks authorization is not required. Do not expose data or tools that require user-level access controls through this shared identity.

## Required environment variables

```bash
MicrosoftAppId=<user-assigned-managed-identity-client-id>
MicrosoftAppType=UserAssignedMSI
MicrosoftTenantId=<azure-tenant-id>
DATABRICKS_HOST=https://<workspace-host>
DATABRICKS_AZURE_RESOURCE_ID=/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Databricks/workspaces/<workspace>
DATABRICKS_AZURE_CLIENT_ID=<user-assigned-managed-identity-client-id>
SERVING_ENDPOINT_NAME=<serving-endpoint-name>
```

`MicrosoftAppPassword` and `ConnectionName` are not used in managed identity mode.

## Azure and Databricks setup

1. Attach the Azure Bot's user-assigned managed identity to the App Service.
2. Add that managed identity to the Databricks account or workspace as a Microsoft Entra ID managed service principal.
3. Grant the service principal permission to query the selected serving endpoint and any data or tools used by the agent.
4. Set the Azure Bot messaging endpoint to `https://<web-app>.azurewebsites.net/api/messages`.
5. Enable the Microsoft Teams channel.
6. Replace `<app_id>` and `<web_app_domain>` in `appManifest/manifest.json`, package the manifest and icons, and upload the package in the Teams tenant.

The Teams tenant can differ from the Azure and Databricks tenant because Teams users are not used for Databricks authentication.

## Run locally

Managed identity authentication only works on an Azure host with the identity attached. Install dependencies and run the web process with:

```bash
python -m pip install -r requirements.txt
python app.py
```

The service listens on port `8000` by default and receives Bot Framework activities at `/api/messages`.