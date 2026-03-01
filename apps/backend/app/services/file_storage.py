"""File storage service - abstract interface for database/local/S3 storage.

Архитектура:
- DatabaseFileStorage: хранение в PostgreSQL (по умолчанию, простота)
- LocalFileStorage: локальная файловая система (self-hosted)
- S3FileStorage: S3-совместимое хранилище (AWS S3, MinIO, Yandex Object Storage)
- Переключение через STORAGE_BACKEND env variable
"""
import logging
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from app.core.config import settings

logger = logging.getLogger(__name__)


class FileStorage(ABC):
    """Abstract file storage interface."""
    
    @abstractmethod
    async def save(self, file_id: str, file_data: BinaryIO, user_id: UUID, filename: str, **kwargs) -> str:
        """Save file and return storage path. kwargs may contain db session for DatabaseFileStorage."""
        pass
    
    @abstractmethod
    async def get(self, file_id: str, **kwargs) -> Path | str | bytes:
        """Get file path, URL, or bytes. kwargs may contain db session for DatabaseFileStorage."""
        pass
    
    @abstractmethod
    async def delete(self, file_id: str, **kwargs) -> bool:
        """Delete file. kwargs may contain db session for DatabaseFileStorage."""
        pass
    
    @abstractmethod
    async def exists(self, file_id: str, **kwargs) -> bool:
        """Check if file exists. kwargs may contain db session for DatabaseFileStorage."""
        pass


class DatabaseFileStorage(FileStorage):
    """Database storage (PostgreSQL BYTEA).
    
    Хранит файлы напрямую в БД.
    
    Преимущества:
    - Простота (не нужно управлять файловой системой)
    - Транзакционность (файл + метаданные атомарно)
    - Автоматический backup вместе с БД
    - Идеально для разработки
    
    Ограничения:
    - Рекомендуется до 100MB на файл
    - Для больших объёмов лучше S3
    """
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        logger.info("DatabaseFileStorage initialized (PostgreSQL BYTEA)")
    
    async def save(self, file_id: str, file_data: BinaryIO, user_id: UUID, filename: str, **kwargs) -> str:
        """Save file to database."""
        from app.models import UploadedFile
        
        # Read file content
        content = file_data.read()
        
        # Get DB session from kwargs
        db = kwargs.get('db')
        if not db:
            raise ValueError("Database session is required for DatabaseFileStorage.save(). Pass db=session.")
        
        # Create file record
        mime_type = kwargs.get('mime_type', 'application/octet-stream')
        uploaded_file = UploadedFile(
            id=UUID(file_id),
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
            content=content,
            uploaded_by=user_id
        )
        
        db.add(uploaded_file)
        await db.flush()  # Flush to assign ID, but don't commit (FastAPI handles transaction)
        
        logger.info(f"File saved to DB: {filename} ({len(content)} bytes)")
        return f"db://{file_id}"
    
    async def get(self, file_id: str, **kwargs) -> bytes:
        """Get file content from database."""
        from app.models import UploadedFile
        from sqlalchemy import select
        
        # Get DB session from kwargs
        db = kwargs.get('db')
        if not db:
            raise ValueError("Database session is required for DatabaseFileStorage.get(). Pass db=session.")
        
        result = await db.execute(
            select(UploadedFile).where(UploadedFile.id == UUID(file_id))
        )
        uploaded_file = result.scalar_one_or_none()
        
        if not uploaded_file:
            raise FileNotFoundError(f"File {file_id} not found in database")
        
        return uploaded_file.content
    
    async def delete(self, file_id: str, **kwargs) -> bool:
        """Delete file from database."""
        from app.models import UploadedFile
        from sqlalchemy import select
        
        # Get DB session from kwargs
        db = kwargs.get('db')
        if not db:
            raise ValueError("Database session is required for DatabaseFileStorage.delete(). Pass db=session.")
        
        result = await db.execute(
            select(UploadedFile).where(UploadedFile.id == UUID(file_id))
        )
        uploaded_file = result.scalar_one_or_none()
        
        if uploaded_file:
            await db.delete(uploaded_file)
            await db.flush()  # Flush changes, but don't commit (FastAPI handles transaction)
            logger.info(f"File deleted from DB: {file_id}")
            return True
        return False
    
    async def exists(self, file_id: str, **kwargs) -> bool:
        """Check if file exists in database."""
        from app.models import UploadedFile
        from sqlalchemy import select
        
        # Get DB session from kwargs
        db = kwargs.get('db')
        if not db:
            raise ValueError("Database session is required for DatabaseFileStorage.exists(). Pass db=session.")
        
        result = await db.execute(
            select(UploadedFile.id).where(UploadedFile.id == UUID(file_id))
        )
        return result.scalar_one_or_none() is not None


class LocalFileStorage(FileStorage):
    """Local filesystem storage.
    
    Структура:
    data/uploads/
        {user_id}/
            {year}/
                {month}/
                    {file_id}.{ext}
    """
    
    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path or settings.STORAGE_LOCAL_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalFileStorage initialized: {self.base_path.absolute()}")
    
    def _get_file_path(self, file_id: str, user_id: UUID, extension: str = "") -> Path:
        """Generate organized file path: {user_id}/{year}/{month}/{file_id}.{ext}"""
        now = datetime.utcnow()
        user_dir = self.base_path / str(user_id) / str(now.year) / f"{now.month:02d}"
        user_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{file_id}{extension}"
        return user_dir / filename
    
    async def save(self, file_id: str, file_data: BinaryIO, user_id: UUID, filename: str, **kwargs) -> str:
        """Save file to local storage."""
        extension = Path(filename).suffix
        file_path = self._get_file_path(file_id, user_id, extension)
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file_data, f)
        
        # Return relative path for storage
        relative_path = file_path.relative_to(self.base_path)
        logger.info(f"File saved: {relative_path}")
        return str(relative_path)
    
    async def get(self, file_id: str, **kwargs) -> Path:
        """Get file path by ID (searches in all subdirectories)."""
        # Search for file with any extension
        for file_path in self.base_path.rglob(f"{file_id}*"):
            if file_path.is_file():
                return file_path
        
        raise FileNotFoundError(f"File {file_id} not found")
    
    async def delete(self, file_id: str, **kwargs) -> bool:
        """Delete file by ID."""
        try:
            file_path = await self.get(file_id)
            file_path.unlink()
            logger.info(f"File deleted: {file_path}")
            return True
        except FileNotFoundError:
            return False
    
    async def exists(self, file_id: str, **kwargs) -> bool:
        """Check if file exists."""
        try:
            await self.get(file_id)
            return True
        except FileNotFoundError:
            return False


class S3FileStorage(FileStorage):
    """S3-compatible storage (AWS S3, MinIO, Yandex Object Storage).
    
    Требует: boto3 или aioboto3
    Структура ключей: {user_id}/{year}/{month}/{file_id}.{ext}
    """
    
    def __init__(self):
        # Import only if S3 backend is used
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ImportError(
                "S3 storage requires boto3. Install: pip install boto3"
            )
        
        self.bucket_name = settings.S3_BUCKET_NAME
        
        # Initialize S3 client
        s3_config = Config(
            region_name=settings.S3_REGION,
            signature_version='s3v4',
        )
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=s3_config
        )
        
        logger.info(f"S3FileStorage initialized: bucket={self.bucket_name}")
    
    def _get_object_key(self, file_id: str, user_id: UUID, extension: str = "") -> str:
        """Generate S3 object key: {user_id}/{year}/{month}/{file_id}.{ext}"""
        now = datetime.utcnow()
        return f"{user_id}/{now.year}/{now.month:02d}/{file_id}{extension}"
    
    async def save(self, file_id: str, file_data: BinaryIO, user_id: UUID, filename: str, **kwargs) -> str:
        """Upload file to S3."""
        extension = Path(filename).suffix
        object_key = self._get_object_key(file_id, user_id, extension)
        
        # Upload file
        self.s3_client.upload_fileobj(
            file_data,
            self.bucket_name,
            object_key,
            ExtraArgs={'ContentDisposition': f'attachment; filename="{filename}"'}
        )
        
        logger.info(f"File uploaded to S3: {object_key}")
        return object_key
    
    async def get(self, file_id: str, **kwargs) -> str:
        """Get presigned URL for file download."""
        # Search for object with file_id prefix
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=file_id
        )
        
        if 'Contents' not in response or len(response['Contents']) == 0:
            raise FileNotFoundError(f"File {file_id} not found in S3")
        
        object_key = response['Contents'][0]['Key']
        
        # Generate presigned URL (valid for 1 hour)
        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': object_key},
            ExpiresIn=3600
        )
        
        return url
    
    async def delete(self, file_id: str, **kwargs) -> bool:
        """Delete file from S3."""
        try:
            # Find object key
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=file_id
            )
            
            if 'Contents' in response and len(response['Contents']) > 0:
                object_key = response['Contents'][0]['Key']
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)
                logger.info(f"File deleted from S3: {object_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_id} from S3: {e}")
            return False
    
    async def exists(self, file_id: str, **kwargs) -> bool:
        """Check if file exists in S3."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=file_id,
                MaxKeys=1
            )
            return 'Contents' in response and len(response['Contents']) > 0
        except Exception:
            return False


# Factory function
def get_file_storage() -> FileStorage:
    """Get file storage instance based on configuration."""
    backend = settings.STORAGE_BACKEND.lower()
    
    if backend == "database" or backend == "db":
        return DatabaseFileStorage()
    elif backend == "s3":
        return S3FileStorage()
    elif backend == "local":
        return LocalFileStorage()
    else:
        raise ValueError(f"Unknown storage backend: {backend}")


# Global storage instance
_storage_instance: FileStorage | None = None


def get_storage() -> FileStorage:
    """Get global storage instance (singleton)."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = get_file_storage()
    return _storage_instance
