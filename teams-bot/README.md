# Teams Databricks Bot

本目录是当前 Demo 的 Python Bot。完整资源创建、权限、Bot ID 获取、部署和验证步骤以[项目主 README](../README.md)为准。

## 当前状态

截至 **2026-10-12**，使用 Microsoft 365 Agents SDK **1.8.0** 的 App Service 部署和 Teams 客户端问答均已验证通过。线上使用 Python 3.13，本地 Python 3.12 环境中的 **27 项测试通过**。Demo 的行程数量问题返回 **21,932**；结果与部署记录见[主 README](../README.md#当前-demo-问答结果)。

当前使用 SDK 的通用 `ActivityHandler` 处理消息与成员加入事件，Bot 认证采用用户分配托管身份，Databricks 认证采用独立的 OAuth M2M 服务主体。

## 默认认证与请求链路

```text
Teams → Azure Bot → App Service Python Bot → Databricks Genie
```

- **Teams / Bot 身份**：Azure Bot 与 App Service 使用同一个用户分配托管身份。Azure Bot 资源类型为 `UserAssignedMSI`，Microsoft 365 Agents SDK 认证类型为 `UserManagedIdentity`。入站消息由 JWT 中间件验证。
- **Databricks 身份**：独立 Databricks 服务主体通过 OAuth M2M 获取令牌，不使用上述托管身份或 Teams 用户身份。
- 所有获准使用 Bot 的用户共享该服务主体的数据权限和审计身份。跨租户 Teams 安装仍需单独验证，M2M 认证本身不保证应用在其他租户可用。

## 必需配置

在 App Service 应用设置中填写实际值；下面是配置模板，`<botid>` 与主 README 的 Bot Microsoft App ID 占位符一致。请替换所有 `<...>`，不要保留尖括号，不应将真实 secret 写入文件或命令历史。

```text
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID=<botid>
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE=UserManagedIdentity
DATABRICKS_HOST=https://<workspace-host>
DATABRICKS_AUTH_TYPE=oauth-m2m
DATABRICKS_CLIENT_ID=<databricks-service-principal-client-id>
DATABRICKS_CLIENT_SECRET=<databricks-oauth-secret-or-key-vault-reference>
GENIE_SPACE_ID=<genie-space-id>
SCM_DO_BUILD_DURING_DEPLOYMENT=True
```

service connection 的 `CLIENTID` 必须与 Azure Bot 的 Microsoft App ID、附加身份的 Client ID 及 [manifest](appManifest/manifest.json) 中的 `bots[].botId` 一致。`DATABRICKS_CLIENT_ID` 属于另一套身份。

缺少 service connection 的 `CLIENTID` / `AUTHTYPE` 会导致启动失败。生产环境禁止 `ANONYMOUS_ALLOWED=True`。

`DATABRICKS_AUTH_TYPE=oauth-m2m` 必须显式设置。Databricks 客户端保留 PAT 和 Azure 托管身份兼容路径，但这些不是本文的默认部署方案。

配置了 `GENIE_SPACE_ID` 时优先调用 Genie。只有清空该值并设置 `SERVING_ENDPOINT_NAME` 才切换到 Model Serving；还需单独部署并授权 endpoint，以及验证下游资源身份，见[可选 Agent 说明](../databricks-agent/README.md)。

## 文件与部署包

- [app.py](app.py)：启动 aiohttp 服务，监听 `0.0.0.0:8000`，只注册 `POST /api/messages`。
- [config.py](config.py)：从环境变量读取配置，不自动加载 `.env`。
- [client/databricks_client.py](client/databricks_client.py)：认证、Genie 调用和可选 Model Serving 调用。
- [bots/databricks_bot.py](bots/databricks_bot.py)：Agents SDK `ActivityHandler`，选择调用路径并将文本与工具调用卡片发回 Teams。
- [tests](tests)：使用标准库 unittest 的配置、消息和 HTTP 认证测试。
- [appManifest](appManifest)：Teams manifest 和图标，不是 Bot 运行代码。

代码部署 ZIP 与 Teams 安装 ZIP 是两种不同的包。前者部署到 App Service，后者由 manifest 和两个图标生成并上传 Teams；具体命令见[主 README](../README.md)。Teams ZIP 被 Git 忽略，克隆后需自行生成。

已有 App Service 若只更新代码且 Bot ID、域名和 scopes 不变，不必重新上传 Teams 包。新部署或资源变更则需同步核对 manifest、service connection 和 Azure Bot 配置。

## 本地开发与测试

在本目录创建独立虚拟环境并安装依赖。本地已在 Python 3.12 测试，部署运行时为 Python 3.13；请勿将虚拟环境上传或提交：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m pip check
```

这些测试不要求配置运行凭据。它们覆盖配置、JWT、真实 SDK Adapter 的消息处理、Genie / Model Serving 路由、模型历史和文本 / 卡片回复；外部公钥、Azure token 和 Databricks 调用使用测试替身。

可按主 README 的独立 Databricks 验证脚本测试 M2M 和 Genie，不需要先启动 Teams Bot。完整 Bot 本地调试还需要 Agents SDK 认证配置、可达的 HTTPS 转发端点，以及可用的 Bot 身份认证；本机不能直接使用 App Service 的托管身份。

在具备运行条件且配置已注入时，使用 `python app.py` 启动，默认端口 8000，也可设置 `PORT`。访问 `/api/messages` 的 GET 返回 405 只说明路由可达，不等于 Teams 认证和 Databricks 问答已通过。POST 缺少或包含无效 JWT 时返回 401；项目没有专门的健康检查 GET 端点。

## 已知限制

- Genie 每次新建会话，只返回文本，不支持连续上下文或完整查询结果表格。
- 历史使用进程内存，按 channel / conversation 保存，重启丢失；没有多人按用户隔离或同会话并发控制。
- `clear` 只删除残留 Dialog 状态、不清空历史；`logout` 没有专用处理，会作为问题发给后端。
- 频道和群聊默认需要 @Bot，代码未显式移除 mention。
- 长查询仍在 HTTP 请求内等待；线上 Direct Line 测试出现过超时后收到答案的情况，但没有保证最终回复的后台任务机制。

新环境或后续发布的配置、部署、验证与排障步骤见[主 README](../README.md)。