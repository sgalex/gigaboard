"""Helpers for project ownership vs collaborator access (viewer / editor / admin)."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectCollaborator, User

ProjectAccessLevel = Literal["owner", "viewer", "editor", "admin"]

FORBIDDEN_VIEW_ONLY = "Недостаточно прав: нужен доступ на изменение или полный доступ"
FORBIDDEN_SHARE = "Управление участниками доступно только владельцу и пользователям с полным доступом"


class ProjectAccessService:
    @staticmethod
    async def _is_admin_user(db: AsyncSession, user_id: UUID) -> bool:
        r = await db.execute(select(User.role).where(User.id == user_id))
        role = r.scalar_one_or_none()
        return role == "admin"

    @staticmethod
    async def get_access_level(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> ProjectAccessLevel | None:
        r = await db.execute(select(Project.user_id).where(Project.id == project_id))
        owner_id = r.scalar_one_or_none()
        if owner_id is None:
            return None
        if owner_id == user_id:
            return "owner"
        r2 = await db.execute(
            select(ProjectCollaborator.role).where(
                ProjectCollaborator.project_id == project_id,
                ProjectCollaborator.user_id == user_id,
            )
        )
        role = r2.scalar_one_or_none()
        if role is None:
            return None
        if role not in ("viewer", "editor", "admin"):
            return "editor"
        return role  # type: ignore[return-value]

    @staticmethod
    async def get_project_if_accessible(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> Project | None:
        if await ProjectAccessService.get_access_level(db, project_id, user_id) is None:
            return None
        r = await db.execute(select(Project).where(Project.id == project_id))
        return r.scalar_one_or_none()

    @staticmethod
    async def require_project_view_access(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> Project:
        """Любой доступ: владелец или соавтор (любая роль)."""
        p = await ProjectAccessService.get_project_if_accessible(db, project_id, user_id)
        if not p:
            # Глобальный системный admin может просматривать любой проект.
            if await ProjectAccessService._is_admin_user(db, user_id):
                r = await db.execute(select(Project).where(Project.id == project_id))
                p = r.scalar_one_or_none()
            if not p:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
        return p

    @staticmethod
    async def require_project_edit_access(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> Project:
        """Изменение досок/дашбордов/данных: владелец, editor или admin (не viewer)."""
        p = await ProjectAccessService.require_project_view_access(db, project_id, user_id)
        level = await ProjectAccessService.get_access_level(db, project_id, user_id)
        # Системный admin может смотреть любые проекты, но не редактировать
        # проекты, где он не владелец/соавтор.
        if level is None or level == "viewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=FORBIDDEN_VIEW_ONLY,
            )
        return p

    @staticmethod
    async def require_project_share_access(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> Project:
        """Приглашение/исключение участников: владелец или admin-соавтор."""
        p = await ProjectAccessService.require_project_view_access(db, project_id, user_id)
        level = await ProjectAccessService.get_access_level(db, project_id, user_id)
        if level not in ("owner", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=FORBIDDEN_SHARE,
            )
        return p

    @staticmethod
    async def require_project_access(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> Project:
        """Alias: просмотр и навигация (совместимо со старым кодом)."""
        return await ProjectAccessService.require_project_view_access(db, project_id, user_id)

    @staticmethod
    async def require_project_owner(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> Project:
        r = await db.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        p = r.scalar_one_or_none()
        if not p:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        return p

    @staticmethod
    async def is_project_owner(
        db: AsyncSession, project_id: UUID, user_id: UUID
    ) -> bool:
        r = await db.execute(
            select(Project.id).where(Project.id == project_id, Project.user_id == user_id)
        )
        return r.scalar_one_or_none() is not None
