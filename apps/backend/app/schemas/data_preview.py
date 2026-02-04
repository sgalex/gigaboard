"""
Schemas для data preview.

См. docs/DATA_NODE_SYSTEM.md
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DataPreviewResponse(BaseModel):
    """Ответ с preview данных."""
    
    data: List[Dict[str, Any]] = Field(description="Первые N строк данных")
    metadata: Dict[str, Any] = Field(description="Метаданные (columns, types, row_count)")
    
    model_config = {"from_attributes": True}


class ExecuteDataNodeRequest(BaseModel):
    """Запрос на выполнение DataNode (для получения свежих данных)."""
    
    parameters: Optional[Dict[str, Any]] = Field(None, description="Параметры для параметризованных запросов")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Максимальное количество строк")


class DataNodeExecutionResult(BaseModel):
    """Результат выполнения DataNode."""
    
    success: bool = Field(description="Успешно ли выполнен запрос")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Данные")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Метаданные")
    error: Optional[str] = Field(None, description="Сообщение об ошибке")
    execution_time_ms: Optional[int] = Field(None, description="Время выполнения в миллисекундах")
