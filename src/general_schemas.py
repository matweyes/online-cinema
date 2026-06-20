from pydantic import BaseModel, ConfigDict


class StatusResponse(BaseModel):
    status: str

    model_config = ConfigDict(from_attributes=True)
