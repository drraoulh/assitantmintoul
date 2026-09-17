from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str = Field(examples=["Cameroon AI Tour Guide"])
