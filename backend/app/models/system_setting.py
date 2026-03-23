from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from typing import Optional


class SystemSettingBase(SQLModel):
    key: str = Field(primary_key=True)
    value: str  # Stored as JSON string for flexibility
    description: Optional[str] = None


class SystemSetting(SystemSettingBase, table=True):
    pass


class SystemSettingCreate(SystemSettingBase):
    pass


class SystemSettingUpdate(SQLModel):
    value: Optional[str] = None
    description: Optional[str] = None


class SystemSettingPublic(SystemSettingBase):
    pass
