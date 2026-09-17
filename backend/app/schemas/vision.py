from pydantic import BaseModel, Field


class VisionIdentifyResponse(BaseModel):
    description: str = Field(min_length=1)
    provider: str = "gemini"
