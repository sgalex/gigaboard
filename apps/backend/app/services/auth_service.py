from datetime import datetime, timedelta
from typing import Optional
import hashlib
import jwt
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
import uuid
import logging

from ..core import settings
from ..models import User, UserSession
from ..schemas import UserCreate, UserLogin, UserResponse, TokenResponse

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        # Bcrypt has a 72 byte limit, truncate if necessary
        if len(password.encode('utf-8')) > 72:
            password = password[:72]
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash token using SHA256 (for session storage)"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def create_access_token(user_id: str, username: str) -> tuple[str, datetime]:
        """Create JWT token"""
        expires_at = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
        to_encode = {
            "sub": str(user_id),
            "username": username,
            "exp": expires_at,
            "iat": datetime.utcnow(),
        }
        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt, expires_at
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    async def register_user(
        db: AsyncSession,
        user_create: UserCreate
    ) -> tuple[UserResponse, TokenResponse]:
        """Register new user"""
        # Check if user already exists
        result = await db.execute(
            select(User).where(
                (User.email == user_create.email) | (User.username == user_create.username)
            )
        )
        if result.scalar_one_or_none():
            raise ValueError("User with this email or username already exists")
        
        # Create new user
        user = User(
            email=user_create.email,
            username=user_create.username,
            password_hash=AuthService.hash_password(user_create.password)
        )
        
        db.add(user)
        await db.flush()
        
        # Create token
        token, expires_at = AuthService.create_access_token(str(user.id), user.username)
        
        # Create session
        session = UserSession(
            user_id=user.id,
            token_hash=AuthService.hash_token(token),
            expires_at=expires_at
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(user)
        
        user_response = UserResponse.model_validate(user)
        token_response = TokenResponse(
            access_token=token,
            user=user_response,
            expires_in=settings.JWT_EXPIRATION_HOURS * 3600
        )
        
        return user_response, token_response
    
    @staticmethod
    async def login_user(
        db: AsyncSession,
        user_login: UserLogin
    ) -> tuple[UserResponse, TokenResponse]:
        """Login user (поиск по email без учёта регистра)."""
        result = await db.execute(
            select(User).where(func.lower(User.email) == user_login.email.strip().lower())
        )
        user = result.scalar_one_or_none()
        
        if not user or not AuthService.verify_password(user_login.password, user.password_hash):
            raise ValueError("Invalid email or password")
        
        # Create token
        token, expires_at = AuthService.create_access_token(str(user.id), user.username)
        
        # Create session
        session = UserSession(
            user_id=user.id,
            token_hash=AuthService.hash_token(token),
            expires_at=expires_at
        )
        
        db.add(session)
        await db.commit()
        
        user_response = UserResponse.model_validate(user)
        token_response = TokenResponse(
            access_token=token,
            user=user_response,
            expires_in=settings.JWT_EXPIRATION_HOURS * 3600
        )
        
        return user_response, token_response
    
    @staticmethod
    async def get_current_user(
        db: AsyncSession,
        token: str
    ) -> Optional[User]:
        """Get current user from token"""
        payload = AuthService.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        return user

    @staticmethod
    async def ensure_admin_user(db: AsyncSession) -> None:
        """
        Если заданы ADMIN_EMAIL и ADMIN_PASSWORD в env — создаёт или обновляет
        пользователя с role=admin (см. docs/ADMIN_AND_SYSTEM_LLM.md).
        """
        if not getattr(settings, "ADMIN_EMAIL", "") or not getattr(settings, "ADMIN_PASSWORD", ""):
            return
        email = (settings.ADMIN_EMAIL or "").strip()
        password = settings.ADMIN_PASSWORD or ""
        if not email or not password:
            return
        # Поиск без учёта регистра (в БД email мог быть сохранён в другом регистре)
        result = await db.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        user = result.scalar_one_or_none()
        if user is None:
            # Генерируем уникальный username из email (до @)
            base_username = (email.split("@")[0] or "admin").replace(".", "_")[:200]
            username = base_username
            n = 0
            while True:
                r = await db.execute(select(User).where(User.username == username))
                if r.scalar_one_or_none() is None:
                    break
                n += 1
                username = f"{base_username}_{n}"
            user = User(
                email=email,
                username=username,
                password_hash=AuthService.hash_password(password),
                role="admin",
            )
            db.add(user)
            await db.commit()
            logging.getLogger(__name__).info("Admin user created from ADMIN_EMAIL: %s", email)
            return
        user.role = "admin"
        user.password_hash = AuthService.hash_password(password)
        await db.commit()
        await db.refresh(user)
        logging.getLogger(__name__).info(
            "Existing user updated to admin (email=%s, id=%s)", email, user.id
        )
