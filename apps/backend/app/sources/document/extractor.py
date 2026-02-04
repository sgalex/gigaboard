"""Document Source Extractor - PDF/DOCX/TXT with multi-agent extraction.

Поддержка:
- PDF (включая сканированные через GigaChat vision)
- DOCX
- TXT

Использует мультиагент для интеллектуального извлечения текста и таблиц.
"""
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
)


class DocumentSource(BaseSource):
    """Document file source handler (PDF/DOCX/TXT)."""
    
    source_type = "document"
    display_name = "Документ"
    icon = "📄"
    description = "PDF, DOCX, TXT с AI-извлечением"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate document source config."""
        errors = []
        
        if not config.get("file_id") and not config.get("filename"):
            errors.append("Необходимо указать file_id или filename")
        
        document_type = config.get("document_type")
        if document_type and document_type not in ["pdf", "docx", "txt"]:
            errors.append(f"Неподдерживаемый тип документа: {document_type}")
        
        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()
    
    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Extract data from document using multi-agent."""
        start_time = time.time()
        
        if file_content is None:
            return ExtractionResult.failure("Содержимое файла не предоставлено")
        
        try:
            document_type = config.get("document_type", "txt")
            filename = config.get("filename", "document")
            
            # Extract text based on document type
            if document_type == "pdf":
                text, tables = await self._extract_pdf(file_content, config)
            elif document_type == "docx":
                text, tables = await self._extract_docx(file_content, config)
            else:  # txt
                text = file_content.decode("utf-8")
                tables = []
            
            extraction_time = int((time.time() - start_time) * 1000)
            
            return ExtractionResult(
                success=True,
                text=text,
                tables=tables,
                extraction_time_ms=extraction_time,
                metadata={
                    "document_type": document_type,
                    "filename": filename,
                    "text_length": len(text),
                    "table_count": len(tables),
                }
            )
            
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка извлечения из документа: {str(e)}")
    
    async def _extract_pdf(self, content: bytes, config: dict[str, Any]) -> tuple[str, list[TableData]]:
        """Extract text and tables from PDF.
        
        TODO: Implement with PyPDF2/pdfplumber + GigaChat vision for scanned PDFs.
        """
        # Placeholder implementation
        try:
            import io
            from PyPDF2 import PdfReader
            
            reader = PdfReader(io.BytesIO(content))
            text_parts = []
            
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            text = "\n\n".join(text_parts)
            
            # TODO: Table extraction with pdfplumber
            # TODO: OCR for scanned PDFs via GigaChat vision
            
            return text, []
            
        except ImportError:
            return "PDF extraction requires PyPDF2", []
        except Exception as e:
            return f"Error extracting PDF: {str(e)}", []
    
    async def _extract_docx(self, content: bytes, config: dict[str, Any]) -> tuple[str, list[TableData]]:
        """Extract text and tables from DOCX.
        
        TODO: Implement with python-docx.
        """
        try:
            import io
            from docx import Document
            
            doc = Document(io.BytesIO(content))
            
            # Extract paragraphs
            text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(text_parts)
            
            # Extract tables
            tables = []
            for i, table in enumerate(doc.tables):
                rows = []
                columns = []
                
                for j, row in enumerate(table.rows):
                    row_data = [cell.text for cell in row.cells]
                    
                    if j == 0:
                        # First row as headers
                        columns = [{"name": h, "type": "text"} for h in row_data]
                    else:
                        row_dict = {columns[k]["name"]: val for k, val in enumerate(row_data) if k < len(columns)}
                        rows.append(row_dict)
                
                if columns:
                    tables.append(TableData(
                        id=f"table_{i+1}",
                        name=f"Таблица {i+1}",
                        columns=columns,
                        rows=rows,
                    ))
            
            return text, tables
            
        except ImportError:
            return "DOCX extraction requires python-docx", []
        except Exception as e:
            return f"Error extracting DOCX: {str(e)}", []
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for document dialog."""
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "file",
                    "accept": ".pdf,.docx,.txt",
                    "title": "Документ",
                },
                "extraction_prompt": {
                    "type": "string",
                    "title": "Что извлечь",
                    "description": "Опишите, какие данные нужно извлечь из документа",
                },
            },
        }
