from typing import Any, List

from fastapi import APIRouter, HTTPException
from sqlmodel import select, func

from app.api.deps import CurrentUser, SessionDep
from app.models.system_setting import (
    SystemSetting,
    SystemSettingUpdate,
    SystemSettingPublic,
)
from app.models.user import UserRole

router = APIRouter(tags=["settings"])


@router.get("/", response_model=List[SystemSettingPublic])
def read_settings(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve system settings.
    """
    count_statement = select(func.count()).select_from(SystemSetting)
    count = session.exec(count_statement).one()

    statement = select(SystemSetting).offset(skip).limit(limit)
    settings = session.exec(statement).all()

    return settings


@router.put("/{key}", response_model=SystemSettingPublic)
def update_setting(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    key: str,
    setting_in: SystemSettingUpdate,
) -> Any:
    """
    Update a system setting. Superuser only.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    setting = session.get(SystemSetting, key)
    if not setting:
        # Auto-create if not exists for flexibility
        setting = SystemSetting(
            key=key, value=setting_in.value, description=setting_in.description
        )
        session.add(setting)
    else:
        if setting_in.value is not None:
            setting.value = setting_in.value
        if setting_in.description is not None:
            setting.description = setting_in.description
        session.add(setting)

    session.commit()
    session.refresh(setting)
    return setting
