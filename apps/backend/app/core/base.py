"""SQLAlchemy Base for models - separate file to avoid circular imports and engine creation during imports."""

from sqlalchemy.orm import declarative_base

# Base class for all models
Base = declarative_base()
