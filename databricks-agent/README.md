# Teams Demo Agent（可选）

本目录是 MLflow `ResponsesAgent` 的学习示例，调用 Genie 后返回文本答案。它**不是当前 Teams Bot 默认主链路的部署前提**；默认 Bot 直接访问 Genie，不需要 Model Serving endpoint。

## 部署前必须修改

| 文件 | 配置 | 说明 |
| --- | --- | --- |
| [agent.py](agent.py) | `GENIE_SPACE_ID` | 修改为自己的 Genie Space ID |
| [deploy.py](deploy.py) | `GENIE_SPACE_ID` | 必须与 Agent 中的值一致 |
| [deploy.py](deploy.py) | `SQL_WAREHOUSE_ID` | 修改为该 Space 使用的 Warehouse ID |
| [deploy.py](deploy.py) | `UC_MODEL_NAME` | 默认 `databricksdemo.default.teams_demo_agent`，改为自己的 Unity Catalog 模型注册路径 |
| [deploy.py](deploy.py) | MLflow experiment 路径 | 默认 `/Shared/teams-demo-agent`，确认部署账号可以创建或写入该实验 |

目标 catalog/schema 必须存在，部署账号必须有模型注册、实验写入、Model Serving 部署及相关资源访问权限。部署会产生计算或存储费用；`scale_to_zero=True` 不代表没有费用。

## 身份限制

[deploy.py](deploy.py) 对 Genie 和 Warehouse 的 MLflow resource 声明了 `on_behalf_of_user=True`。这与主 README 的共享 M2M 调用链路不能直接等同。调用 endpoint 的身份、Agent 运行时下游身份和资源授权都需要按 Databricks 支持的方案验证；仅设置 `SERVING_ENDPOINT_NAME` 不会解决下游委托问题。

Agent 使用 `WorkspaceClient()`，不在代码中显式指定认证；其凭据来自部署 / 运行环境。部署人员本地能访问 Genie，不代表托管 endpoint 运行时也具备同样权限。

## 部署流程

1. 修改上述硬编码值，完成权限和下游认证设计。
2. 在本目录创建独立虚拟环境，并安装 [requirements.txt](requirements.txt)。不要与 Bot 的虚拟环境混用。
3. 配置部署账号的 Databricks SDK / MLflow 认证，例如组织允许的 OAuth 或 CLI profile；若测试使用 `DATABRICKS_TOKEN`，不要写入代码或 Git。
4. 在本目录运行 `python deploy.py`，脚本会写入 MLflow 实验、注册新的模型版本并部署 endpoint，输出模型名、版本和 endpoint 名称。
5. 先直接验证 endpoint 返回文本且能访问下游 Genie，再为 Bot 服务主体授予 endpoint 的 `CAN QUERY`。
6. 在 App Service 清空 `GENIE_SPACE_ID`、设置 `SERVING_ENDPOINT_NAME` 并保存，之后再执行 Teams 端到端测试。

脚本中的 `python_model="agent.py"` 是相对路径，因此不要直接从仓库根目录运行脚本。仓库中的 `mlflow.db` 不是部署必需文件，也不是托管 endpoint 的凭据来源；不要随 Bot 代码上传。

## 当前限制

- 只提取最后一条用户文本问题，每次创建新的 Genie 会话，不提供多轮上下文。
- 只返回 Genie 文本附件，不提取完整 SQL 查询结果表格。
- `predict_stream` 在完整答案生成后才发送一个事件，不是逐 token 的实时流式输出。
- 此目录提供代码示例，不代表模型已在新环境部署或已验证兼容当前 M2M 链路。

默认部署与平台权限请先阅读[项目主 README](../README.md)。