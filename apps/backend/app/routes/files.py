"""File upload routes."""
import logging
import csv
import io
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core import get_db
from app.core.config import settings
from app.models import User
from app.routes.auth import get_current_user
from app.services.file_storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/files", tags=["files"])

# Max file size from settings
MAX_FILE_SIZE = settings.STORAGE_MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload")
async def upload_file(
    file: Annotated[UploadFile, File()],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a file and return file metadata.
    
    Supports local filesystem or S3-compatible storage (MinIO, AWS S3, Yandex Object Storage).
    Storage backend configured via STORAGE_BACKEND env variable.
    
    Returns:
        {
            "file_id": "uuid",
            "filename": "original_name.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12345,
            "storage_path": "user_id/2026/01/uuid.pdf"
        }
    """
    try:
        # Validate file size by reading chunks
        file_size = 0
        chunks = []
        
        while chunk := await file.read(8192):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max size: {settings.STORAGE_MAX_FILE_SIZE_MB}MB"
                )
            chunks.append(chunk)
        
        # Generate unique file ID
        file_id = str(uuid4())
        
        # Save file using storage service
        storage = get_storage()
        
        # Create a file-like object from chunks
        import io
        file_data = io.BytesIO(b"".join(chunks))
        
        storage_path = await storage.save(
            file_id=file_id,
            file_data=file_data,
            user_id=current_user.id,  # type: ignore
            filename=file.filename or "unknown",
            db=db
        )
        
        # Commit transaction to persist file in database
        await db.commit()
        
        logger.info(f"File uploaded: {file.filename} ({file_size} bytes) by user {current_user.id}")
        
        return {
            "file_id": file_id,
            "filename": file.filename or "unknown",
            "mime_type": file.content_type or "application/octet-stream",
            "size_bytes": file_size,
            "storage_path": storage_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download a file by ID.
    
    For database storage: returns file directly via Response with bytes
    For local storage: returns file directly via FileResponse
    For S3 storage: returns presigned URL (redirect)
    """
    try:
        storage = get_storage()
        
        # Check if file exists (pass db for DatabaseFileStorage)
        if not await storage.exists(file_id, db=db):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Get file content/path/URL (pass db for DatabaseFileStorage)
        file_location = await storage.get(file_id, db=db)
        
        # For database storage, file_location is bytes
        if isinstance(file_location, bytes):
            from fastapi.responses import Response
            from app.models import UploadedFile
            from sqlalchemy import select
            from uuid import UUID
            
            # Get file metadata for proper response
            result = await db.execute(
                select(UploadedFile).where(UploadedFile.id == UUID(file_id))
            )
            uploaded_file = result.scalar_one_or_none()
            
            return Response(
                content=file_location,
                media_type=uploaded_file.mime_type if uploaded_file else "application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{uploaded_file.filename if uploaded_file else file_id}"'
                }
            )
        
        # For S3 storage, file_location is a presigned URL
        if settings.STORAGE_BACKEND == "s3":
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=str(file_location))
        
        # For local storage, file_location is a Path object
        from pathlib import Path
        if isinstance(file_location, (str, Path)):
            return FileResponse(
                path=str(file_location),
                filename=Path(file_location).name,
                media_type="application/octet-stream"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid storage response"
        )
        
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    except Exception as e:
        logger.error(f"File download failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File download failed: {str(e)}"
        )


# CSV Analysis Response Schema
class CSVAnalysisResult(BaseModel):
    """CSV analysis result."""
    delimiter: str
    encoding: str
    has_header: bool
    rows_count: int
    columns: list[dict]
    preview_rows: list[dict]


@router.post("/{file_id}/analyze-csv", response_model=CSVAnalysisResult)
async def analyze_csv_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyze CSV file and detect encoding, delimiter, columns.
    
    Uses Python csv.Sniffer for delimiter detection and chardet for encoding.
    Returns structure similar to frontend analysis but more accurate.
    """
    try:
        storage = get_storage()
        
        # Download file content
        file_content = await storage.get(
            file_id=file_id,
            db=db
        )
        
        # Detect encoding using chardet
        try:
            import chardet
            detected = chardet.detect(file_content[:100000])
            encoding = detected['encoding'] or 'utf-8'
            confidence = detected['confidence']
            
            # If confidence is low, try common encodings
            if confidence < 0.7:
                for fallback_enc in ['utf-8', 'windows-1251', 'cp1251', 'latin1']:
                    try:
                        file_content.decode(fallback_enc)
                        encoding = fallback_enc
                        break
                    except UnicodeDecodeError:
                        continue
        except ImportError:
            # chardet not installed, fallback logic
            encoding = 'utf-8'
            try:
                file_content.decode('utf-8')
            except UnicodeDecodeError:
                encoding = 'windows-1251'
        
        # Decode content
        try:
            content_str = file_content.decode(encoding)
        except UnicodeDecodeError:
            # Last resort
            content_str = file_content.decode('utf-8', errors='replace')
            encoding = 'utf-8'
        
        # Detect delimiter using csv.Sniffer
        sniffer = csv.Sniffer()
        sample = content_str[:4096]
        
        try:
            dialect = sniffer.sniff(sample, delimiters=',;\t|')
            delimiter = dialect.delimiter
        except csv.Error:
            # Fallback: count occurrences
            delimiters = {',': 0, ';': 0, '\t': 0, '|': 0}
            first_line = content_str.split('\n')[0] if content_str else ''
            for delim in delimiters:
                delimiters[delim] = first_line.count(delim)
            delimiter = max(delimiters, key=delimiters.get)
        
        # Detect if first row is header
        lines = content_str.split('\n')
        lines = [l for l in lines if l.strip()]
        
        if len(lines) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file is too small to analyze"
            )
        
        # Try to detect header using Sniffer
        try:
            has_header = sniffer.has_header(sample)
        except csv.Error:
            has_header = True  # Assume header by default
        
        # Parse CSV
        reader = csv.reader(io.StringIO(content_str), delimiter=delimiter)
        rows_list = list(reader)
        
        if not rows_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file is empty"
            )
        
        # Extract headers and data
        if has_header:
            headers = rows_list[0]
            data_rows = rows_list[1:min(11, len(rows_list))]  # First 10 data rows
        else:
            headers = [f"Column {i+1}" for i in range(len(rows_list[0]))]
            data_rows = rows_list[:10]
        
        # Clean headers
        headers = [h.strip().replace('"', '').replace("'", '') for h in headers]
        
        # Build preview rows
        preview_rows = []
        for row in data_rows:
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            preview_rows.append(row_dict)
        
        # Detect column types
        columns = []
        for i, header in enumerate(headers):
            samples = [row[i] for row in data_rows if i < len(row) and row[i].strip()]
            
            # Type detection
            is_numeric = all(val.replace('.', '', 1).replace('-', '', 1).isdigit() for val in samples if val)
            is_date = any(
                val.count('-') == 2 and len(val.split('-')[0]) == 4 
                for val in samples if val
            )
            
            col_type = 'дата' if is_date else ('число' if is_numeric else 'текст')
            
            columns.append({
                'name': header,
                'type': col_type,
                'sample_values': samples[:3]
            })
        
        # Convert delimiter back to display format
        delimiter_display = 'tab' if delimiter == '\t' else delimiter
        
        return CSVAnalysisResult(
            delimiter=delimiter_display,
            encoding=encoding,
            has_header=has_header,
            rows_count=len(rows_list) - (1 if has_header else 0),
            columns=columns,
            preview_rows=preview_rows
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSV analysis failed: {str(e)}"
        )
