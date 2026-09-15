from typing import Generator
from uuid import uuid4

from databricks.sdk import WorkspaceClient
from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)


GENIE_SPACE_ID = "01f1b0efb5c211b2b08b9571d261f0ef"


class TeamsDemoAgent(ResponsesAgent):
    def _last_user_question(self, request: ResponsesAgentRequest) -> str:
        for item in reversed(request.input):
            if item.role == "user" and isinstance(item.content, str):
                return item.content
        raise ValueError("A user question is required.")

    def _ask_genie(self, question: str) -> str:
        message = WorkspaceClient().genie.start_conversation_and_wait(
            GENIE_SPACE_ID,
            question,
        )
        for attachment in reversed(message.attachments or []):
            text = attachment.as_dict().get("text")
            if text and text.get("content"):
                return text["content"]
        raise RuntimeError("Genie completed without a text answer.")

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        answer = self._ask_genie(self._last_user_question(request))
        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=answer, id=str(uuid4()))],
            custom_outputs=request.custom_inputs,
        )

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        response = self.predict(request)
        yield ResponsesAgentStreamEvent(
            type="response.output_item.done",
            item=response.output[0],
        )


set_model(TeamsDemoAgent())