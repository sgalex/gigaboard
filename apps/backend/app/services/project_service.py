"""Project service."""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models import (
    Project,
    Board,
    Dashboard,
    ProjectWidget,
    ProjectTable,
    Dimension,
    FilterPreset,
)
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectWithBoardsResponse


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
        """Get project by ID (user must be owner)."""
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        return project
    
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
        user_id: UUID
    ) -> list[dict]:
        """List all projects with boards, dashboards, sources, widgets, tables counts."""
        result = await db.execute(
            select(
                Project,
                func.count(Board.id).label('boards_count')
            )
            .outerjoin(Board, Board.project_id == Project.id)
            .where(Project.user_id == user_id)
            .group_by(Project.id)
            .order_by(Project.updated_at.desc())
        )
        projects_with_counts = []
        project_ids = []
        for project, boards_count in result:
            project_dict = ProjectWithBoardsResponse.model_validate(project).model_dump()
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

        return projects_with_counts
    
    @staticmethod
    async def update_project(
        db: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        project_data: ProjectUpdate
    ) -> Project:
        """Update project."""
        project = await ProjectService.get_project(db, project_id, user_id)
        
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
        """Delete project (cascades to boards and widgets)."""
        project = await ProjectService.get_project(db, project_id, user_id)
        
        await db.delete(project)
        await db.commit()
