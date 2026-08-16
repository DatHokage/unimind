from pydantic import BaseModel


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    student_id: int | None = None
    lecturer_id: int | None = None


LoginResponse.model_rebuild()
