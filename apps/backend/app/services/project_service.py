"""Project service."""
from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Board,
    Dashboard,
    Dimension,
    FilterPreset,
    Project,
    ProjectCollaborator,
    ProjectTable,
    ProjectWidget,
    User,
)
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectWithBoardsResponse
from app.services.project_access_service import ProjectAccessService


class ProjectService:
    """Service for managing projects."""
    
    @staticmethod
    async def create_project(
        db: AsyncSession,
        user_id: UUID,
        project_data: ProjectCreate
    ) -> Project:
        """Create a new project."""
        project = Project(
            user_id=user_id,
            name=project_data.name,
            description=project_data.description
        )
        
        db.add(project)
        await db.commit()
        await db.refresh(project)
        
        return project
    
    @staticmethod
    async def get_project(
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID
    ) -> Project:
        """Get project by ID (owner or collaborator)."""
        return await ProjectAccessService.require_project_access(db, project_id, user_id)
    
    @staticmethod
    async def list_projects(
        db: AsyncSession,
        user_id: UUID
    ) -> list[Project]:
        """List all projects for user."""
        result = await db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc())
        )
        projects = result.scalars().all()
        
        return list(projects)
    
    @staticmethod
    async def list_projects_with_counts(
        db: AsyncSession,
        user_id: UUID,
        *,
        owner_user_id: UUID | None = None,
        requester_is_admin: bool = False,
    ) -> list[dict]:
        """List all projects with boards, dashboards, sources, widgets, tables counts."""
        if owner_user_id is not None:
            if not requester_is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required",
                )
            accessible = Project.user_id == owner_user_id
        else:
            accessible = or_(
                Project.user_id == user_id,
                Project.id.in_(
                    select(ProjectCollaborator.project_id).where(
                        ProjectCollaborator.user_id == user_id
                    )
                ),
            )
        result = await db.execute(
            select(
                Project,
                func.count(Board.id).label('boards_count')
            )
            .outerjoin(Board, Board.project_id == Project.id)
            .where(accessible)
            .group_by(Project.id)
            .order_by(Project.updated_at.desc())
        )
        projects_with_counts = []
        project_ids = []
        for project, boards_count in result:
            project_dict = ProjectWithBoardsResponse.model_validate(project).model_dump()
            is_own = project.user_id == user_id
            project_dict['is_owner'] = is_own
            project_dict['my_access'] = 'owner' if is_own else 'editor'
            project_dict['boards_count'] = boards_count
            project_dict['dashboards_count'] = 0
            project_dict['sources_count'] = 0
            project_dict['content_nodes_count'] = 0
            project_dict['widgets_count'] = 0
            project_dict['tables_count'] = 0
            project_dict['dimensions_count'] = 0
            project_dict['filters_count'] = 0
            projects_with_counts.append(project_dict)
            project_ids.append(project.id)

        if not project_ids:
            return projects_with_counts

        acc_rows = await db.execute(
            select(ProjectCollaborator.project_id, ProjectCollaborator.role)
            .where(ProjectCollaborator.user_id == user_id)
            .where(ProjectCollaborator.project_id.in_(project_ids))
        )
        collab_access = {row[0]: row[1] for row in acc_rows}
        for p in projects_with_counts:
            if not p['is_owner']:
                p['my_access'] = collab_access.get(p['id'], 'editor')

        # Dashboards count per project
        dash_result = await db.execute(
            select(Dashboard.project_id, func.count(Dashboard.id).label('c'))
            .where(Dashboard.project_id.in_(project_ids))
            .group_by(Dashboard.project_id)
        )
        dash_map = {row[0]: row[1] for row in dash_result}

        # Project widgets count per project
        w_result = await db.execute(
            select(ProjectWidget.project_id, func.count(ProjectWidget.id).label('c'))
            .where(ProjectWidget.project_id.in_(project_ids))
            .group_by(ProjectWidget.project_id)
        )
        w_map = {row[0]: row[1] for row in w_result}

        # Dimensions count per project
        dim_result = await db.execute(
            select(Dimension.project_id, func.count(Dimension.id).label('c'))
            .where(Dimension.project_id.in_(project_ids))
            .group_by(Dimension.project_id)
        )
        dim_map = {row[0]: row[1] for row in dim_result}

        # Filter presets count per project
        filt_result = await db.execute(
            select(FilterPreset.project_id, func.count(FilterPreset.id).label('c'))
            .where(FilterPreset.project_id.in_(project_ids))
            .group_by(FilterPreset.project_id)
        )
        filt_map = {row[0]: row[1] for row in filt_result}

        # Content nodes count: all rows in content_nodes for project boards (no polymorphic filter:
        # ORM ContentNode filters node_type='content_node' and would exclude SourceNodes)
        from sqlalchemy import text
        cn_result = await db.execute(
            text("""
                SELECT b.project_id, COUNT(cn.id)::bigint AS c
                FROM content_nodes cn
                JOIN nodes n ON n.id = cn.id
                JOIN boards b ON b.id = n.board_id
                WHERE b.project_id = ANY(:project_ids)
                GROUP BY b.project_id
            """),
            {"project_ids": list(project_ids)},
        )
        cn_map = {row[0]: int(row[1]) for row in cn_result}

        # Tables count: sum of len(content.tables) for all ContentNodes in project boards
        t_result = await db.execute(
            text("""
                SELECT b.project_id, COALESCE(SUM(
                    COALESCE(jsonb_array_length(cn.content->'tables'), 0)
                ), 0)::bigint AS c
                FROM content_nodes cn
                JOIN nodes n ON n.id = cn.id
                JOIN boards b ON b.id = n.board_id
                WHERE b.project_id = ANY(:project_ids)
                GROUP BY b.project_id
            """),
            {"project_ids": list(project_ids)},
        )
        t_map = {row[0]: int(row[1]) for row in t_result}

        # Sources count: all rows in source_nodes for project boards (raw SQL to avoid ORM polymorphic filter)
        src_result = await db.execute(
            text("""
                SELECT b.project_id, COUNT(sn.id)::bigint AS c
                FROM source_nodes sn
                JOIN nodes n ON n.id = sn.id
                JOIN boards b ON b.id = n.board_id
                WHERE b.project_id = ANY(:project_ids)
                GROUP BY b.project_id
            """),
            {"project_ids": list(project_ids)},
        )
        src_map = {row[0]: int(row[1]) for row in src_result}

        for p in projects_with_counts:
            pid = p['id']
            p['dashboards_count'] = dash_map.get(pid, 0)
            p['content_nodes_count'] = cn_map.get(pid, 0)
            p['widgets_count'] = w_map.get(pid, 0)
            p['tables_count'] = t_map.get(pid, 0)
            p['sources_count'] = src_map.get(pid, 0)
            p['dimensions_count'] = dim_map.get(pid, 0)
            p['filters_count'] = filt_map.get(pid, 0)

        # Участники доступа: число и превью для плашки (владелец + соавторы), до 10 строк в popover
        _PREVIEW_CAP = 10
        cc_rows = await db.execute(
            select(ProjectCollaborator.project_id, func.count().label("c"))
            .where(ProjectCollaborator.project_id.in_(project_ids))
            .group_by(ProjectCollaborator.project_id)
        )
        collab_n = {row[0]: int(row[1]) for row in cc_rows}

        own_rows = await db.execute(
            select(Project.id, User.id, User.username)
            .join(User, User.id == Project.user_id)
            .where(Project.id.in_(project_ids))
        )
        owner_by_pid = {row[0]: (row[1], row[2]) for row in own_rows}

        cd_rows = await db.execute(
            select(
                ProjectCollaborator.project_id,
                User.id,
                User.username,
                ProjectCollaborator.role,
                ProjectCollaborator.created_at,
            )
            .join(User, User.id == ProjectCollaborator.user_id)
            .where(ProjectCollaborator.project_id.in_(project_ids))
            .order_by(ProjectCollaborator.project_id, ProjectCollaborator.created_at)
        )
        collabs_by_pid: dict = defaultdict(list)
        for row in cd_rows:
            collabs_by_pid[row[0]].append(
                {"user_id": row[1], "username": row[2], "role": row[3]}
            )

        for p in projects_with_counts:
            pid = p['id']
            n_collab = collab_n.get(pid, 0)
            p["access_user_count"] = 1 + n_collab
            uid_un = owner_by_pid.get(pid)
            preview: list[dict] = []
            if uid_un:
                preview.append(
                    {"user_id": uid_un[0], "username": uid_un[1], "role": "owner"}
                )
            for c in collabs_by_pid.get(pid, []):
                if len(preview) >= _PREVIEW_CAP:
                    break
                preview.append(c)
            p["access_members_preview"] = preview

        return projects_with_counts
    
    @staticmethod
    async def update_project(
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        project_data: ProjectUpdate
    ) -> Project:
        """Update project (owner only)."""
        project = await ProjectAccessService.require_project_owner(db, project_id, user_id)
        
        # Update only provided fields
        if project_data.name is not None:
            project.name = project_data.name
        if project_data.description is not None:
            project.description = project_data.description
        
        await db.commit()
        await db.refresh(project)
        
        return project
    
    @staticmethod
    async def delete_project(
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID
    ) -> None:
        """Delete project (cascades to boards and widgets); owner only."""
        project = await ProjectAccessService.require_project_owner(db, project_id, user_id)
        
        await db.delete(project)
        await db.commit()
