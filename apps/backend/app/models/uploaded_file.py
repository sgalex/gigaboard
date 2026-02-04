"""UploadedFile model - хранение загруженных файлов в БД."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, Integer, LargeBinary, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base


class UploadedFile(Base):
    """Загруженный файл.
    
    Хранит файл в БД (BYTEA в PostgreSQL).
    Альтернатива файловой системе или S3.
    
    Преимущества БД:
    - Транзакционность (файл + метаданные атомарно)
    - Автоматический backup (вместе с БД)
    - Не нужно управлять файловой системой
    - Проще для разработки
    
    Ограничения:
    - Рекомендуемый размер: до 100MB
    - Для больших файлов используйте S3 storage
    """
    
    __tablename__ = "uploaded_files"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # File content (BYTEA in PostgreSQL)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Owner and timestamps
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<UploadedFile(id={self.id}, filename={self.filename}, size={self.size_bytes})>"
