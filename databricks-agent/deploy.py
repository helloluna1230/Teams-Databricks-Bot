import mlflow
from databricks import agents
from mlflow.models.resources import DatabricksGenieSpace, DatabricksSQLWarehouse


UC_MODEL_NAME = "databricksdemo.default.teams_demo_agent"
GENIE_SPACE_ID = "01f1b0efb5c211b2b08b9571d261f0ef"
SQL_WAREHOUSE_ID = "eca894b403d9f424"


mlflow.set_tracking_uri("databricks")
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment("/Shared/teams-demo-agent")

with mlflow.start_run():
    logged_agent = mlflow.pyfunc.log_model(
        name="agent",
        python_model="agent.py",
        resources=[
            DatabricksGenieSpace(
                genie_space_id=GENIE_SPACE_ID,
                on_behalf_of_user=True,
            ),
            DatabricksSQLWarehouse(
                warehouse_id=SQL_WAREHOUSE_ID,
                on_behalf_of_user=True,
            ),
        ],
        pip_requirements=[
            "mlflow>=3.1.3",
            "databricks-sdk>=0.58.0",
        ],
    )

registered_agent = mlflow.register_model(logged_agent.model_uri, UC_MODEL_NAME)
deployment = agents.deploy(
    UC_MODEL_NAME,
    registered_agent.version,
    scale_to_zero=True,
)

print(f"model={UC_MODEL_NAME}")
print(f"version={registered_agent.version}")
print(f"endpoint={deployment.endpoint_name}")