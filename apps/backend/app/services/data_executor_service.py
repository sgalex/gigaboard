"""
Data Executor Service - выполнение запросов и загрузка данных из различных источников.

См. docs/DATA_NODE_SYSTEM.md
"""
import logging
import json
from typing import Any, Dict, List, Optional, Tuple
from io import StringIO, BytesIO
import pandas as pd
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DataExecutorService:
    """
    Сервис для выполнения запросов к различным источникам данных.
    
    Поддерживает:
    - SQL queries (через текущую БД или внешние подключения)
    - REST API calls (GET/POST/PUT/DELETE)
    - File parsing (CSV, JSON, Excel)
    """
    
    MAX_PREVIEW_ROWS = 100
    
    @staticmethod
    async def execute_sql_query(
        db: AsyncSession,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        limit: int = MAX_PREVIEW_ROWS
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Выполнить SQL запрос и вернуть результат + метаданные.
        
        Args:
            db: Database session
            query: SQL запрос (SELECT, WITH, etc.)
            parameters: Параметры для параметризованного запроса
            limit: Максимальное количество строк для preview
            
        Returns:
            (data, metadata) где:
                - data: список словарей с результатами
                - metadata: {columns, row_count, total_row_count, column_types}
                
        Raises:
            ValueError: если запрос невалидный
            Exception: при ошибке выполнения
        """
        try:
            # Безопасность: разрешаем только SELECT и WITH queries
            query_upper = query.strip().upper()
            if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
                raise ValueError("Only SELECT and WITH queries are allowed")
            
            # Добавляем LIMIT если его нет
            if "LIMIT" not in query_upper:
                query = f"{query.rstrip(';')} LIMIT {limit}"
            
            # Выполняем запрос
            stmt = text(query)
            if parameters:
                result = await db.execute(stmt, parameters)
            else:
                result = await db.execute(stmt)
            
            # Получаем результаты
            rows = result.fetchall()
            columns = list(result.keys()) if rows else []
            
            # Преобразуем в список словарей
            data = [dict(zip(columns, row)) for row in rows]
            
            # Собираем метаданные
            metadata = {
                "columns": columns,
                "row_count": len(data),
                "total_row_count": len(data),  # TODO: COUNT(*) для точного числа
                "column_types": _infer_column_types(data, columns) if data else {},
                "query": query,
            }
            
            logger.info(f"SQL query executed: {len(data)} rows, {len(columns)} columns")
            return data, metadata
            
        except ValueError as e:
            logger.error(f"Invalid SQL query: {e}")
            raise
        except Exception as e:
            logger.error(f"Error executing SQL query: {e}")
            raise Exception(f"Failed to execute SQL query: {str(e)}")
    
    @staticmethod
    async def execute_api_call(
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Выполнить HTTP запрос к API и вернуть результат.
        
        Args:
            url: API endpoint URL
            method: HTTP метод (GET, POST, PUT, DELETE)
            headers: HTTP заголовки
            params: Query параметры
            body: Request body для POST/PUT
            timeout: Timeout в секундах
            
        Returns:
            (data, metadata) где:
                - data: распарсенный JSON ответ (список или преобразованный объект)
                - metadata: {status_code, headers, response_time, url}
        """
        try:
            import time
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, params=params, json=body)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, params=params, json=body)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                # Парсим JSON
                response_json = response.json()
                
                # Если ответ - список, используем как есть
                if isinstance(response_json, list):
                    data = response_json[:DataExecutorService.MAX_PREVIEW_ROWS]
                # Если объект с массивом внутри (типа {data: [...], meta: {}})
                elif isinstance(response_json, dict):
                    # Ищем ключи типа "data", "items", "results", "records"
                    for key in ["data", "items", "results", "records", "rows"]:
                        if key in response_json and isinstance(response_json[key], list):
                            data = response_json[key][:DataExecutorService.MAX_PREVIEW_ROWS]
                            break
                    else:
                        # Если не нашли массив, оборачиваем сам объект
                        data = [response_json]
                else:
                    # Скалярное значение
                    data = [{"value": response_json}]
                
                # Метаданные
                elapsed = time.time() - start_time
                metadata = {
                    "status_code": response.status_code,
                    "response_time_ms": int(elapsed * 1000),
                    "url": str(response.url),
                    "method": method.upper(),
                    "row_count": len(data),
                    "columns": list(data[0].keys()) if data else [],
                    "column_types": _infer_column_types(data, list(data[0].keys()) if data else []),
                }
                
                logger.info(f"API call successful: {url} - {len(data)} records")
                return data, metadata
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"API call failed: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Failed to reach API: {str(e)}")
        except Exception as e:
            logger.error(f"Error executing API call: {e}")
            raise Exception(f"API call failed: {str(e)}")
    
    @staticmethod
    def parse_csv_data(
        file_content: bytes,
        file_name: str,
        encoding: str = "utf-8",
        delimiter: str = ",",
        limit: int = MAX_PREVIEW_ROWS
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Распарсить CSV файл и вернуть данные.
        
        Args:
            file_content: Байты файла
            file_name: Имя файла (для логирования)
            encoding: Кодировка файла
            delimiter: Разделитель (,|;|\t)
            limit: Максимальное количество строк
            
        Returns:
            (data, metadata)
        """
        try:
            # Используем pandas для парсинга
            df = pd.read_csv(
                BytesIO(file_content),
                encoding=encoding,
                delimiter=delimiter,
                nrows=limit
            )
            
            # Заполняем NaN значения
            df = df.fillna("")
            
            # Преобразуем в список словарей
            data = df.to_dict(orient="records")
            
            # Метаданные
            metadata = {
                "columns": list(df.columns),
                "row_count": len(df),
                "total_row_count": len(df),  # TODO: узнать реальное число строк без загрузки всего файла
                "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "file_name": file_name,
                "file_size": len(file_content),
            }
            
            logger.info(f"CSV parsed: {file_name} - {len(df)} rows, {len(df.columns)} columns")
            return data, metadata
            
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            raise Exception(f"Failed to parse CSV file: {str(e)}")
    
    @staticmethod
    def parse_json_data(
        file_content: bytes,
        file_name: str,
        encoding: str = "utf-8",
        limit: int = MAX_PREVIEW_ROWS
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Распарсить JSON файл и вернуть данные.
        
        Args:
            file_content: Байты файла
            file_name: Имя файла
            encoding: Кодировка
            limit: Максимальное количество строк
            
        Returns:
            (data, metadata)
        """
        try:
            # Парсим JSON
            json_str = file_content.decode(encoding)
            json_data = json.loads(json_str)
            
            # Если это список, используем как есть
            if isinstance(json_data, list):
                data = json_data[:limit]
            # Если объект с массивом внутри
            elif isinstance(json_data, dict):
                for key in ["data", "items", "results", "records", "rows"]:
                    if key in json_data and isinstance(json_data[key], list):
                        data = json_data[key][:limit]
                        break
                else:
                    # Если не нашли массив, оборачиваем сам объект
                    data = [json_data]
            else:
                # Скалярное значение
                data = [{"value": json_data}]
            
            # Метаданные
            columns = list(data[0].keys()) if data else []
            metadata = {
                "columns": columns,
                "row_count": len(data),
                "total_row_count": len(data),
                "column_types": _infer_column_types(data, columns),
                "file_name": file_name,
                "file_size": len(file_content),
            }
            
            logger.info(f"JSON parsed: {file_name} - {len(data)} records")
            return data, metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            raise Exception(f"Invalid JSON file: {str(e)}")
        except Exception as e:
            logger.error(f"Error parsing JSON: {e}")
            raise Exception(f"Failed to parse JSON file: {str(e)}")


def _infer_column_types(data: List[Dict[str, Any]], columns: List[str]) -> Dict[str, str]:
    """
    Определить типы колонок по первым N строкам.
    
    Args:
        data: Список словарей с данными
        columns: Список названий колонок
        
    Returns:
        Словарь {column_name: type_name}
    """
    if not data or not columns:
        return {}
    
    types = {}
    
    for col in columns:
        # Берем первое непустое значение
        sample_value = None
        for row in data[:10]:  # Смотрим первые 10 строк
            if col in row and row[col] not in (None, "", "null"):
                sample_value = row[col]
                break
        
        if sample_value is None:
            types[col] = "string"
        elif isinstance(sample_value, bool):
            types[col] = "boolean"
        elif isinstance(sample_value, int):
            types[col] = "integer"
        elif isinstance(sample_value, float):
            types[col] = "float"
        elif isinstance(sample_value, (list, tuple)):
            types[col] = "array"
        elif isinstance(sample_value, dict):
            types[col] = "object"
        else:
            types[col] = "string"
    
    return types
