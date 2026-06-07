from pydantic import BaseModel, Field


class ModelOut(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = ""


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelOut]


class OpenAIError(BaseModel):
    message: str
    type: str = "api_error"
    code: str = "internal_error"


class OpenAIErrorResponse(BaseModel):
    error: OpenAIError


class ChatMessage(BaseModel):
    role: str = Field(min_length=1)
    content: str | list[dict] = Field(default="")


class ChatCompletionRequest(BaseModel):
    """Minimal validation for chat completion proxy requests."""
    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1, max_length=1024)
    max_tokens: int | None = Field(default=None, ge=1, le=131072)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    stream: bool = False
    # Pass-through: any extra fields go to upstream unchanged
    model_config = {"extra": "allow"}


class EmbeddingRequest(BaseModel):
    """Minimal validation for embedding requests."""
    model: str = Field(min_length=1)
    input: str | list[str] = Field(min_length=1)
    model_config = {"extra": "allow"}
