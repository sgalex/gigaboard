"""Share service — manage dashboard sharing (public links, passwords)."""
import secrets
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models import Dashboard, DashboardShare
from app.schemas.dashboard import DashboardShareCreate
from app.services.project_access_service import ProjectAccessService


def _hash_password(password: str) -> str:
    """Simple hash for share passwords (not user auth — bcrypt overkill)."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


class ShareService:
    """Service for dashboard sharing."""

    @staticmethod
    async def create_or_update_share(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID, data: DashboardShareCreate
    ) -> DashboardShare:
        result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
        dashboard = result.scalar_one_or_none()
        if not dashboard:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
        await ProjectAccessService.require_project_edit_access(db, dashboard.project_id, user_id)

        # Check for existing share
        result = await db.execute(
            select(DashboardShare).where(DashboardShare.dashboard_id == dashboard_id)
        )
        share = result.scalar_one_or_none()

        if share:
            # Update existing
            share.share_type = data.share_type or share.share_type
            if data.password:
                share.password_hash = _hash_password(data.password)
            elif data.share_type == "public":
                share.password_hash = None
            share.expires_at = data.expires_at
            share.max_views = data.max_views
            share.allow_download = data.allow_download if data.allow_download is not None else share.allow_download
            if data.branding is not None:
                share.branding = data.branding
        else:
            # Create new
            share = DashboardShare(
                dashboard_id=dashboard_id,
                share_type=data.share_type or "public",
                share_token=secrets.token_urlsafe(32),
                password_hash=_hash_password(data.password) if data.password else None,
                expires_at=data.expires_at,
                max_views=data.max_views,
                branding=data.branding or {},
                allow_download=data.allow_download if data.allow_download is not None else False,
            )
            db.add(share)

        await db.commit()
        await db.refresh(share)
        return share

    @staticmethod
    async def get_share(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID
    ) -> DashboardShare:
        result = await db.execute(
            select(DashboardShare, Dashboard.project_id)
            .join(Dashboard, Dashboard.id == DashboardShare.dashboard_id)
            .where(DashboardShare.dashboard_id == dashboard_id)
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
        share, project_id = row[0], row[1]
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)
        return share

    @staticmethod
    async def delete_share(
        db: AsyncSession, dashboard_id: UUID, user_id: UUID
    ) -> None:
        share = await ShareService.get_share(db, dashboard_id, user_id)
        await db.delete(share)
        await db.commit()

    @staticmethod
    async def get_public_dashboard(
        db: AsyncSession, token: str, password: str | None = None
    ) -> Dashboard:
        """Fetch dashboard by share token — no auth required."""
        result = await db.execute(
            select(DashboardShare).where(DashboardShare.share_token == token)
        )
        share = result.scalar_one_or_none()
        if not share:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")

        # Check expiry
        if share.expires_at and share.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share link has expired")

        # Check max views
        if share.max_views and share.view_count >= share.max_views:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Max views reached")

        # Check password
        if share.password_hash:
            if not password:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password required")
            if _hash_password(password) != share.password_hash:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

        # Increment view count
        share.view_count = (share.view_count or 0) + 1
        await db.commit()

        # Fetch dashboard with items
        result = await db.execute(
            select(Dashboard)
            .where(Dashboard.id == share.dashboard_id)
            .options(selectinload(Dashboard.items))
        )
        dashboard = result.scalar_one_or_none()
        if not dashboard:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
        return dashboard
