from sqlmodel import Field, SQLModel  # ty:ignore[unresolved-import]


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
