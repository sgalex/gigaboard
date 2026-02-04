from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import get_db
from ..models import User
from ..schemas import UserCreate, UserLogin, UserResponse, TokenResponse, ErrorResponse
from ..services.auth_service import AuthService
from ..middleware import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

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
    """Login user"""
    try:
        user_response, token_response = await AuthService.login_user(db, user_login)
        return token_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
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
    return UserResponse.from_orm(current_user)
