from pydantic import BaseModel, ConfigDict, Field


class MajorCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)


class MajorUpdate(BaseModel):
    name: str | None = None


class MajorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
