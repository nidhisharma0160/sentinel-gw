from pydantic import BaseModel, field_validator
from typing import List


class Message(BaseModel):
    role: str
    content: str


class LLMRequest(BaseModel):
    model: str
    max_tokens: int
    messages: List[Message]

    @field_validator("messages")
    @classmethod
    def messages_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("messages list cannot be empty")
        return v

    @field_validator("max_tokens")
    @classmethod
    def max_tokens_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("max_tokens must be greater than 0")
        return v
