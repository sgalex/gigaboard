import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import asyncpg

from ..core import get_db, settings
from ..core.database import async_session_maker
from ..models import User
from ..schemas import UserCreate, UserLogin, UserResponse, TokenResponse, ErrorResponse
from ..services.auth_service import AuthService
from ..middleware import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

def _is_connection_error(exc: BaseException) -> bool:
    """Временные сбои соединения с БД (Docker/сеть)."""
    e = exc
    while e:
        if isinstance(e, (asyncpg.exceptions.ConnectionDoesNotExistError, ConnectionError, ConnectionResetError)):
            return True
        msg = getattr(e, "message", "") or str(e)
        if "connection was closed" in msg or "Connection reset" in msg or "10054" in msg:
            return True
        e = getattr(e, "__cause__", None)
    return False

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}}
)
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register new user"""
    try:
        user_response, token_response = await AuthService.register_user(db, user_create)
        return token_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}}
)
async def login(
    user_login: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login user. При сбое соединения с БД — до 3 попыток с увеличивающейся задержкой (Docker/сеть)."""
    log = logging.getLogger(__name__)
    delays = (0.5, 1.0)  # пауза перед 2-й и 3-й попыткой (сек)
    for attempt in range(3):
        try:
            if attempt == 0:
                user_response, token_response = await AuthService.login_user(db, user_login)
            else:
                async with async_session_maker() as new_session:
                    user_response, token_response = await AuthService.login_user(new_session, user_login)
            admin_email = (getattr(settings, "ADMIN_EMAIL", "") or "").strip().lower()
            log.info(
                "[LOGIN] current_user: id=%s email=%s username=%s role=%s | admin_from_env: ADMIN_EMAIL=%s match=%s",
                user_response.id,
                user_response.email,
                user_response.username,
                getattr(user_response, "role", "?"),
                admin_email or "(not set)",
                user_response.email.strip().lower() == admin_email if admin_email else False,
            )
            return token_response
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        except Exception as e:
            if attempt < 2 and _is_connection_error(e):
                delay = delays[attempt] if attempt < len(delays) else 1.0
                log.warning(
                    "Login attempt %s failed (connection error), retry in %.1fs: %s",
                    attempt + 1, delay, e,
                )
                await asyncio.sleep(delay)
                continue
            log.exception("Login failed (exception): %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed"
            )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Login failed"
    )

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user (invalidate token on client side)"""
    return {"message": "Successfully logged out"}

@router.get(
    "/me",
    response_model=UserResponse
)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse.model_validate(current_user)
