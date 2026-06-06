from pydantic import BaseModel


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
