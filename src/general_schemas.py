from pydantic import BaseModel, ConfigDict, Field


class StatusResponse(BaseModel):
    status: str = Field(..., description="Operation result status", examples=["ok"])

    model_config = ConfigDict(from_attributes=True)
