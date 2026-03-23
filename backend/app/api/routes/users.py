import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.core.utils import export_users_to_excel
from sqlmodel import col, delete, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    get_current_active_staff,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/export-excel",
    dependencies=[Depends(get_current_active_superuser)],
)
def export_excel(session: SessionDep) -> Any:
    """
    Export all users to an Excel file.
    """
    output = export_users_to_excel(session)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=users_report.xlsx"},
    )


@router.get(
    "/export-csv",
    dependencies=[Depends(get_current_active_superuser)],
)
def export_csv(session: SessionDep) -> Any:
    """
    Export all users to a CSV file.
    """
    from app.core.utils import export_users_to_csv

    output = export_users_to_csv(session)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_report.csv"},
    )


@router.get(
    "/",
    response_model=UsersPublic,
)
def read_users(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve users.
    """
    if not current_user.is_superuser and current_user.role != "teacher":
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )

    statement = select(User)
    if current_user.role == "teacher" and not current_user.is_superuser:
        # Teachers can see students and teachers, but NEVER superusers
        statement = statement.where(col(User.role).in_(["student", "teacher"])).where(
            not col(User.is_superuser)
        )

    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    statement = (
        statement.order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    return UsersPublic(data=users, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_staff)], response_model=UserPublic
)
def create_user(
    *, session: SessionDep, user_in: UserCreate, current_user: CurrentUser
) -> Any:
    """
    Create new user.
    """
    # Teacher permission check
    if not current_user.is_superuser:
        if user_in.is_superuser:
            raise HTTPException(
                status_code=403, detail="Teachers cannot create superusers"
            )
        if user_in.role != "student":
            raise HTTPException(
                status_code=403, detail="Teachers can only create student accounts"
            )

    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post("/heartbeat", response_model=UserPublic)
def user_heartbeat(*, session: SessionDep, current_user: CurrentUser, path: str) -> Any:
    """
    Update user's last active timestamp and current path.
    """
    current_user.last_active_at = datetime.now(timezone.utc)
    current_user.current_path = path
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    # Security: Ensure no one can register themselves as superuser
    user_create.is_superuser = False
    user = crud.create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user

    # Permission check for reading others
    if not current_user.is_superuser:
        if current_user.role == "teacher":
            # Teachers can read students and other teachers (if not superusers)
            if user and (user.role not in ["student", "teacher"] or user.is_superuser):
                raise HTTPException(
                    status_code=403,
                    detail="Teachers can only view student and teacher profiles (excluding superusers)",
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_staff)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )

    # Permission checks for update
    if not current_user.is_superuser:
        if db_user.is_superuser:
            raise HTTPException(
                status_code=403, detail="Teachers cannot update superusers"
            )
        if db_user.role != "student":
            raise HTTPException(
                status_code=403, detail="Teachers can only update student accounts"
            )
        # Prevent unauthorized modifications to premium status
        if user_in.is_premium is not None or user_in.premium_expiry is not None:
            raise HTTPException(
                status_code=403, detail="Only superusers can modify premium status"
            )
        # Prevent privilege escalation
        # UserUpdate schema does not allow changing is_superuser, so we don't need to check it here.
        if user_in.role and user_in.role != "student":
            raise HTTPException(
                status_code=403, detail="Teachers cannot elevate user roles"
            )

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.patch("/{user_id}/fee-management", response_model=UserPublic)
def update_user_fee(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    fee_override: float | None = None,
    is_fee_exempt: bool | None = None,
) -> Any:
    """
    Update fee settings for a student. Superuser only.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if fee_override is not None:
        db_user.fee_override = fee_override
    if is_fee_exempt is not None:
        db_user.is_fee_exempt = is_fee_exempt

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.get("/stats/admin", dependencies=[Depends(get_current_active_superuser)])
def get_admin_stats(session: SessionDep) -> Any:
    """
    Get statistics for the superuser dashboard.
    """
    from app.models.test import Test
    from app.models.attempt import Attempt

    total_tests = session.exec(select(func.count(Test.id))).one()
    total_attempts = session.exec(select(func.count(Attempt.id))).one()

    # Active users in last 5 minutes
    five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    active_now = session.exec(
        select(func.count(User.id)).where(User.last_active_at >= five_min_ago)
    ).one()

    return {
        "total_tests": total_tests,
        "total_attempts": total_attempts,
        "active_now": active_now,
    }


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_staff)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Permission checks for delete
    if not current_user.is_superuser:
        if user.is_superuser:
            raise HTTPException(
                status_code=403, detail="Teachers cannot delete superusers"
            )
        if user.role != "student":
            raise HTTPException(
                status_code=403, detail="Teachers can only delete student accounts"
            )

    if user == current_user:
        raise HTTPException(
            status_code=403,
            detail="Users are not allowed to delete themselves from this endpoint",
        )

    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)  # type: ignore
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")
