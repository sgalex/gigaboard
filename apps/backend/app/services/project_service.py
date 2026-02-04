"""Project service."""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models import Project, Board
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
        """List all projects with boards count."""
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
        for project, boards_count in result:
            project_dict = ProjectWithBoardsResponse.from_orm(project).dict()
            project_dict['boards_count'] = boards_count
            projects_with_counts.append(project_dict)
        
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
