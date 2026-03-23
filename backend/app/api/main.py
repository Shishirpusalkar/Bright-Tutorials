from fastapi import APIRouter

from app.api.routes import (
    attempts,
    items,
    login,
    omr,
    payments,
    private,  # Keep private as it's used later
    questions,
    tests,
    users,
    utils,
    omega,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(payments.router, tags=["payments"])
api_router.include_router(utils.router, tags=["utils"])
api_router.include_router(items.router, tags=["items"])
api_router.include_router(tests.router, tags=["tests"])
api_router.include_router(attempts.router, tags=["attempts"])
api_router.include_router(omr.router, tags=["omr"])
api_router.include_router(questions.router, tags=["questions"])
api_router.include_router(omega.router, prefix="/omega", tags=["omega"])


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
