from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    text: str = Field(min_length=1)
    language: str | None = None
    provider: str = "whisper"


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
