"""Project sharing — collaborators with roles (viewer / editor / admin)."""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Project, ProjectCollaborator, User
from app.services.project_access_service import ProjectAccessService

COLLAB_ROLES = frozenset({"viewer", "editor", "admin"})


class ProjectShareService:
    @staticmethod
    async def search_users(
        db: AsyncSession,
        query: str,
        current_user_id: UUID,
        *,
        limit: int = 20,
    ) -> list[dict]:
        q = (query or "").strip()
        if len(q) < 2:
            return []
        pattern = f"%{q}%"
        result = await db.execute(
            select(User.id, User.username, User.email)
            .where(User.deleted_at.is_(None))
            .where(User.id != current_user_id)
            .where(or_(User.username.ilike(pattern), User.email.ilike(pattern)))
            .order_by(User.username)
            .limit(limit)
        )
        return [
            {"id": row[0], "username": row[1], "email": row[2]}
            for row in result.all()
        ]

    @staticmethod
    async def list_collaborators(
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID,
    ) -> list[dict]:
        """Все участники доступа: владелец первым, затем приглашённые."""
        await ProjectAccessService.require_project_view_access(db, project_id, user_id)
        result = await db.execute(
            select(Project)
            .options(selectinload(Project.user))
            .where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        owner = project.user
        out: list[dict] = [
            {
                "user_id": project.user_id,
                "username": owner.username if owner else "",
                "email": owner.email if owner else "",
                "role": "owner",
                "created_at": project.created_at,
            }
        ]

        c_result = await db.execute(
            select(ProjectCollaborator, User)
            .join(User, User.id == ProjectCollaborator.user_id)
            .where(ProjectCollaborator.project_id == project_id)
            .where(User.deleted_at.is_(None))
            .order_by(ProjectCollaborator.created_at)
        )
        for pc, u in c_result.all():
            out.append(
                {
                    "user_id": pc.user_id,
                    "username": u.username,
                    "email": u.email,
                    "role": pc.role,
                    "created_at": pc.created_at,
                }
            )
        return out

    @staticmethod
    async def add_collaborator(
        db: AsyncSession,
        project_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        role: str,
    ) -> None:
        if role not in COLLAB_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недопустимая роль: используйте viewer, editor или admin",
            )

        project = await ProjectAccessService.require_project_share_access(db, project_id, actor_id)

        if target_user_id == actor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя добавить себя как соавтора",
            )
        if target_user_id == project.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Владелец проекта уже имеет полный доступ",
            )

        u_result = await db.execute(
            select(User.id).where(User.id == target_user_id, User.deleted_at.is_(None))
        )
        if u_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )

        ex = await db.execute(
            select(ProjectCollaborator.user_id).where(
                ProjectCollaborator.project_id == project_id,
                ProjectCollaborator.user_id == target_user_id,
            )
        )
        if ex.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь уже добавлен",
            )

        db.add(
            ProjectCollaborator(project_id=project_id, user_id=target_user_id, role=role)
        )
        await db.commit()

    @staticmethod
    async def update_collaborator_role(
        db: AsyncSession,
        project_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        new_role: str,
    ) -> None:
        if new_role not in COLLAB_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недопустимая роль",
            )
        project = await ProjectAccessService.require_project_share_access(db, project_id, actor_id)
        if target_user_id == project.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Роль владельца изменить нельзя",
            )
        result = await db.execute(
            select(ProjectCollaborator).where(
                ProjectCollaborator.project_id == project_id,
                ProjectCollaborator.user_id == target_user_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Участник не найден")
        row.role = new_role
        await db.commit()

    @staticmethod
    async def remove_collaborator(
        db: AsyncSession,
        project_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
    ) -> None:
        project = await ProjectAccessService.require_project_share_access(db, project_id, actor_id)
        if target_user_id == project.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя отозвать доступ у владельца",
            )
        exists = await db.execute(
            select(ProjectCollaborator.user_id).where(
                ProjectCollaborator.project_id == project_id,
                ProjectCollaborator.user_id == target_user_id,
            )
        )
        if exists.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Соавтор не найден",
            )
        await db.execute(
            delete(ProjectCollaborator).where(
                ProjectCollaborator.project_id == project_id,
                ProjectCollaborator.user_id == target_user_id,
            )
        )
        await db.commit()
