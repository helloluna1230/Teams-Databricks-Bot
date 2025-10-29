# Databricks AI Agent Bot for Microsoft Teams

A sophisticated Microsoft Teams bot that provides AI agent capabilities through Databricks serving endpoints, featuring secure OAuth authentication on behalf of the user and intelligent conversation management.

## Overview

This bot integrates Microsoft Teams with Databricks AI/ML serving endpoints to provide users with an intelligent conversational AI agent directly within Teams. The bot handles secure authentication using OAuth with token exchange on behalf of the user, maintains conversation history, and supports advanced features like tool calling with visual feedback through adaptive cards.

## Key Features

* **🔐 Secure Authentication**: OAuth integration with Microsoft identity providers and token exchange to Databricks on behalf of the user
* **🤖 AI Agent Integration**: Direct connection to Databricks AI/ML serving endpoints
* **💬 Conversation Management**: Maintains conversation history across interactions
* **🛠️ Tool Calling Support**: Advanced function calling capabilities with visual adaptive card feedback
* **👥 Teams Integration**: Full Microsoft Teams bot experience with personal and team scopes
* **🔄 Real-time Processing**: Asynchronous handling of AI responses and tool executions

## Architecture

### Authentication Flow
1. User authenticates with Microsoft OAuth via Teams
2. Bot exchanges Microsoft token for Databricks token using OIDC token exchange on behalf of the user
3. Databricks token is used to authenticate with serving endpoints

### Component Overview
- **`AuthBot`**: Main bot class handling Teams interactions and member management
- **`MainDialog`**: Core dialog managing authentication and AI interactions
- **`DatabricksClient`**: Client for Databricks API interactions and token management
- **`LogoutDialog`**: Handles user logout functionality
- **Adaptive Cards**: Visual representation of tool calls and results

## Prerequisites

### Required Accounts & Services
- **Microsoft Teams**: Account with permissions to upload custom apps (not a guest account)
- **Databricks Workspace**: Access to a Databricks workspace with AI/ML serving endpoints
- **Azure Bot Service**: Bot Framework registration for Teams integration
- **Microsoft Entra ID**: App registration for OAuth authentication

### Development Environment
- **Python 3.11+**: [Download Python](https://www.python.org/downloads/)
- **Tunneling Solution**: [dev tunnel](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started?tabs=windows) or [ngrok](https://ngrok.com/) for local development
- **Visual Studio Code**: Recommended with Microsoft 365 Agents Toolkit extension

### Required Environment Variables
```bash
MicrosoftAppId=<your-bot-app-id>
MicrosoftAppPassword=<your-bot-app-password>
MicrosoftAppType=<app-type>
MicrosoftTenantId=<your-tenant-id>
ConnectionName=<oauth-connection-name>
DATABRICKS_HOST=<your-databricks-workspace-url>
SERVING_ENDPOINT_NAME=<your-serving-endpoint-name>
```

## Setup and Installation

> **Note**: The following steps provide high-level guidance for setting up the Databricks AI Agent Bot. These instructions are not exhaustive and assume familiarity with Azure services, Databricks, and Microsoft Teams development. Additional configuration and troubleshooting may be required based on your specific environment and requirements.

### 1. Databricks Configuration

#### Create a Serving Endpoint
1. In your Databricks workspace, navigate to **Serving**
2. Create a new serving endpoint or use an existing one that supports the OpenAI Responses API
3. Note the endpoint name for the `SERVING_ENDPOINT_NAME` environment variable
4. Ensure the endpoint supports the OpenAI Responses API format

#### Configure OAuth Token Federation Policy
1. Follow this guide to configure federation policy: [Configure a federation policy - Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/cli/authentication#configure-a-federation-policy)
2. Test token exchange using this guide: [Authenticate with an identity provider token - Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-federation-exchange#exchange-a-federated-jwt-for-a-databricks-oauth-token)

### 2. Azure Bot Service Configuration

#### Create Bot Registration
1. Go to [Azure Portal](https://portal.azure.com) and create a new Bot Service
2. Configure the messaging endpoint: `https://<your-domain>/api/messages`
3. Enable the Microsoft Teams channel
4. Note the App ID and App Password for environment variables

#### Setup OAuth Connection
1. In the Bot Service, go to **Configuration** > **OAuth Connection Settings**
2. Create a new connection with:
   - **Name**: Use for `ConnectionName` environment variable
   - **Service Provider**: Microsoft Entra ID v2
   - **Scopes**: `access_as_user` (exposed API scope for V2 access token)
3. For scope creation reference: [Configure an application to expose a web API - Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis#add-a-scope)

### 3. Teams App Configuration

#### Update Manifest
1. Edit `appManifest/manifest.json`:
   - Replace `botId` with your Bot Service App ID
   - Update `validDomains` with your hosting domain
2. Create a ZIP file with `manifest.json`, `color.png`, and `outline.png`
3. Upload to Teams via **Apps** > **Manage your apps** > **Upload an app**

### 4. Local Development Setup

> Note: For local development, you need a tunneling solution as Teams needs to call into your bot.

#### Clone and Setup Project
   ```bash
# Clone the repository
git clone <your-repository-url>
cd DatabricksBotService

# Create and activate virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Configure Environment Variables
Create a `.env` file or export the following environment variables:
   ```bash
export MicrosoftAppId="<your-bot-app-id>"
export MicrosoftAppPassword="<your-bot-app-password>"
export MicrosoftAppType="MultiTenant"
export MicrosoftTenantId="<your-tenant-id>"
export ConnectionName="<your-oauth-connection-name>"
export DATABRICKS_HOST="https://<your-workspace>.cloud.databricks.com"
export SERVING_ENDPOINT_NAME="<your-endpoint-name>"
```

#### Setup Tunneling
**Using ngrok:**
    ```bash
ngrok http 8000 --host-header="localhost:8000"
```

**Using dev tunnels:**
```bash
devtunnel host -p 8000 --allow-anonymous
```

#### Run the Application
```bash
python app.py
```

The bot will start on port 8000 and be accessible at `/api/messages`.

## Usage

### First Time Setup
1. **Install the Bot**: Upload your app manifest to Microsoft Teams
2. **Start a Conversation**: Open the bot in Teams (personal or team scope)
3. **Authentication**: On first interaction, you'll be prompted to sign in with your Microsoft account

### Bot Commands and Interactions

#### Authentication
- **First Message**: Triggers OAuth authentication flow
- **`logout`**: Signs you out and clears your session

#### AI Agent Interactions
Once authenticated, you can:
- **Ask Questions**: Send any message to interact with the Databricks AI agent
- **Tool Usage**: The agent can call tools/functions, displayed as adaptive cards
- **Conversation Context**: Your conversation history is maintained across interactions

#### Example Interactions
```
User: "What can you help me with?"
Bot: [Connects to Databricks agent and provides AI-powered response]

User: "Analyze the sales data from last quarter"
Bot: [Agent processes request, may call tools, returns analysis]

User: logout
Bot: "You have been signed out."
```

### Features in Action

#### Authentication Flow
1. **Initial Prompt**: Bot requests Microsoft authentication
2. **OAuth Process**: User authenticates via Microsoft login
3. **Token Exchange**: Microsoft token is exchanged for Databricks token
4. **Ready State**: Bot is ready for AI agent interactions

#### Tool Calling with Adaptive Cards
When the AI agent uses tools or functions:
- **Tool Call Card**: Shows tool name, parameters, and results
- **Visual Feedback**: Adaptive cards provide rich formatting
- **Multiple Tools**: Supports multiple tool calls in a single conversation

#### Conversation Management
- **History Persistence**: Conversation context maintained per user
- **State Management**: User and conversation state handled separately
- **Error Handling**: Graceful handling of authentication and API failures

## Project Structure

```
DatabricksBotService/
├── app.py                     # Main application entry point
├── config.py                  # Configuration and environment variables
├── requirements.txt           # Python dependencies
├── appManifest/              # Teams app manifest and icons
│   ├── manifest.json         # Teams app configuration
│   ├── color.png            # App icon (color)
│   └── outline.png          # App icon (outline)
├── bots/                     # Bot implementation
│   ├── auth_bot.py          # Main bot class with Teams integration
│   └── dialog_bot.py        # Base dialog bot class
├── client/                   # External service clients
│   └── databricks_client.py # Databricks API client and token exchange
├── dialogs/                  # Dialog implementations
│   ├── main_dialog.py       # Core conversation and AI logic
│   └── logout_dialog.py     # Logout functionality
└── helpers/                  # Utility classes
    └── dialog_helper.py     # Dialog execution helpers
```

## Troubleshooting

### Common Issues

#### Authentication Problems
- **OAuth Timeout**: Check that `timeout=300000` is sufficient for your use case
- **Token Exchange Fails**: Verify Databricks OIDC configuration and Microsoft token scopes
- **Login Loop**: Clear browser cache or try incognito mode

#### Databricks Connection Issues
- **Endpoint Not Found**: Verify `SERVING_ENDPOINT_NAME` matches exactly (case-sensitive)
- **403 Forbidden**: Check Databricks workspace permissions and token exchange setup
- **Timeout Errors**: Increase `request_timeout` in DatabricksClient initialization

#### Teams Integration Issues
- **Bot Not Responding**: Check Bot Service messaging endpoint and ensure it's accessible
- **Manifest Upload Fails**: Verify JSON syntax and that app upload is enabled in Teams admin
- **Permission Denied**: Ensure proper OAuth scopes in Bot Service configuration

### Logging and Debugging
- Set logging level to DEBUG in `main_dialog.py`
- Check Azure App Service logs for production issues
- Use Bot Framework Emulator for local testing
- Monitor Databricks serving endpoint logs

## Security Considerations

- **Token Storage**: Tokens are stored in memory only, not persisted
- **HTTPS Required**: All communications must use HTTPS in production
- **Scope Limitation**: OAuth tokens have limited scopes for security
- **Token Expiration**: Implement proper token refresh handling
- **Input Validation**: Sanitize user inputs before sending to AI models

## Further Reading

- **[Bot Framework Documentation](https://docs.botframework.com)** - Core bot development concepts
- **[Databricks AI/ML Documentation](https://docs.databricks.com/machine-learning/)** - AI model serving and endpoints
- **[Microsoft Teams Platform](https://docs.microsoft.com/microsoftteams/platform/)** - Teams app development guide
- **[OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693)** - Token exchange specification
- **[Azure Bot Service](https://docs.microsoft.com/azure/bot-service/)** - Bot hosting and management
- **[Adaptive Cards](https://adaptivecards.io/)** - Rich card formatting for Teams