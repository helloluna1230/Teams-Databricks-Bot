# Teams Databricks Bot

本目录是当前 Demo 的 Python Bot。完整资源创建、权限、Bot ID 获取、部署和验证步骤以[项目主 README](../README.md)为准。

## 默认认证与请求链路

```text
Teams → Azure Bot → App Service Python Bot → Databricks Genie
```

- **Teams / Bot Framework 身份**：Azure Bot 与 App Service 使用同一个用户分配托管身份，类型为 `UserAssignedMSI`。
- **Databricks 身份**：独立 Databricks 服务主体通过 OAuth M2M 获取令牌，不使用上述托管身份或 Teams 用户身份。
- 所有获准使用 Bot 的用户共享该服务主体的数据权限和审计身份。跨租户 Teams 安装仍需单独验证，M2M 认证本身不保证应用在其他租户可用。

## 必需配置

在 App Service 应用设置中填写实际值；下面是配置模板，不应将真实 secret 写入文件或命令历史。

```text
MicrosoftAppId=<azure-bot-managed-identity-client-id>
MicrosoftAppType=UserAssignedMSI
MicrosoftTenantId=<azure-bot-tenant-id>
DATABRICKS_HOST=https://<workspace-host>
DATABRICKS_AUTH_TYPE=oauth-m2m
DATABRICKS_CLIENT_ID=<databricks-service-principal-client-id>
DATABRICKS_CLIENT_SECRET=<databricks-oauth-secret-or-key-vault-reference>
GENIE_SPACE_ID=<genie-space-id>
SCM_DO_BUILD_DURING_DEPLOYMENT=True
```

`MicrosoftAppId` 必须与 Azure Bot 的 Microsoft App ID、附加身份的 Client ID 及 [manifest](appManifest/manifest.json) 中的 `bots[].botId` 一致。`DATABRICKS_CLIENT_ID` 属于另一套身份。

当前方案不需要 `MicrosoftAppPassword`、`ConnectionName`、`DATABRICKS_TOKEN` 或 `DATABRICKS_AZURE_*` 设置。代码保留 PAT 和 Azure 托管身份兼容路径，但这些不是本文的默认部署方案；尤其不能遗漏 `DATABRICKS_AUTH_TYPE=oauth-m2m`。

配置了 `GENIE_SPACE_ID` 时优先调用 Genie。只有清空该值并设置 `SERVING_ENDPOINT_NAME` 才切换到 Model Serving；还需单独部署并授权 endpoint，以及验证下游资源身份，见[可选 Agent 说明](../databricks-agent/README.md)。

## 文件与部署包

- [app.py](app.py)：启动 aiohttp 服务，监听 `0.0.0.0:8000`，只注册 `POST /api/messages`。
- [config.py](config.py)：从环境变量读取配置，不自动加载 `.env`。
- [client/databricks_client.py](client/databricks_client.py)：认证、Genie 调用和可选 Model Serving 调用。
- [dialogs/main_dialog.py](dialogs/main_dialog.py)：选择调用路径并将答案发回 Teams。
- [appManifest](appManifest)：Teams manifest 和图标，不是 Bot 运行代码。

代码部署 ZIP 与 Teams 安装 ZIP 是两种不同的包。前者部署到 App Service，后者由 manifest 和两个图标生成并上传 Teams；具体命令见[主 README](../README.md)。Teams ZIP 被 Git 忽略，克隆后需自行生成。

## 本地检查与限制

在本目录使用 Python 3.13 创建虚拟环境并安装已有依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

可按主 README 的独立 Databricks 验证脚本测试 M2M 和 Genie，不需要先启动 Teams Bot。完整 Bot 本地调试还需要 Bot Framework 配置、可达的 HTTPS 转发端点，以及可用的 Bot 身份认证；本机不能直接使用 App Service 的托管身份。

在具备运行条件且配置已注入时，使用 `python app.py` 启动。访问 `/api/messages` 的 GET 返回 405 只说明路由可达，不等于 Teams 认证和 Databricks 问答已通过。项目目前没有自动化测试套件或专门的健康检查 GET 端点。

当前 Genie 调用每次新建会话，只返回文本，不支持连续上下文或完整查询结果表格。历史使用进程内存保存，重启丢失；`clear` 只清除对话状态、不清空历史，欢迎语的 `logout` 为旧示例遗留。频道和群聊默认需要 @Bot，代码未显式移除 mention。详见主 README 的“当前能力与限制”。

当前依赖的 Bot Framework SDK 已归档，并自 2025 年 12 月 31 日起停止处理支持工单。新生产项目应评估 Microsoft 365 Agents SDK；本目录尚未实现该迁移。