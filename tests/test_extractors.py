"""Тесты для extractors системы.

Проверяет работу всех extractors: File, Manual, API, Database, Prompt, Stream.
"""
import asyncio
import io
import json
from typing import Any

import pandas as pd

# Manual testing без async session для быстрой проверки


def test_manual_extractor_text():
    """Тест ManualExtractor с текстом."""
    from app.services.extractors.manual_extractor import ManualExtractor
    
    extractor = ManualExtractor()
    config = {
        "data": "Hello, World!",
        "format": "text"
    }
    
    result = asyncio.run(extractor.extract(config, {}))
    
    assert result.is_success
    assert result.text == "Hello, World!"
    assert len(result.errors) == 0


def test_manual_extractor_json():
    """Тест ManualExtractor с JSON массивом."""
    from app.services.extractors.manual_extractor import ManualExtractor
    
    extractor = ManualExtractor()
    config = {
        "data": [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ],
        "format": "json"
    }
    
    result = asyncio.run(extractor.extract(config, {}))
    
    assert result.is_success
    assert len(result.tables) == 1
    assert result.tables[0]["name"] == "manual_data"
    col_names = [c["name"] for c in result.tables[0]["columns"]]
    assert col_names == ["name", "age"]
    assert len(result.tables[0]["rows"]) == 2


def test_manual_extractor_table():
    """Тест ManualExtractor с таблицей."""
    from app.services.extractors.manual_extractor import ManualExtractor
    
    extractor = ManualExtractor()
    config = {
        "data": {
            "columns": ["product", "price", "quantity"],
            "rows": [
                ["Apple", 1.5, 10],
                ["Banana", 0.8, 20]
            ]
        },
        "format": "table"
    }
    
    result = asyncio.run(extractor.extract(config, {}))
    
    assert result.is_success
    assert len(result.tables) == 1
    col_names = [c["name"] for c in result.tables[0]["columns"]]
    assert col_names == ["product", "price", "quantity"]
    assert len(result.tables[0]["rows"]) == 2


def test_manual_extractor_csv():
    """Тест ManualExtractor с CSV строкой."""
    from app.services.extractors.manual_extractor import ManualExtractor
    
    extractor = ManualExtractor()
    csv_data = """name,age,city
Alice,30,New York
Bob,25,London
Charlie,35,Paris"""
    
    config = {
        "data": csv_data,
        "format": "csv"
    }
    
    result = asyncio.run(extractor.extract(config, {}))
    
    assert result.is_success
    assert len(result.tables) == 1
    col_names = [c["name"] for c in result.tables[0]["columns"]]
    assert col_names == ["name", "age", "city"]
    assert len(result.tables[0]["rows"]) == 3


def test_file_extractor_validation():
    """Тест валидации FileExtractor."""
    from app.services.extractors.file_extractor import FileExtractor
    
    extractor = FileExtractor()
    
    # Valid config
    config = {
        "file_id": "123e4567-e89b-12d3-a456-426614174000",
        "filename": "data.csv",
        "mime_type": "text/csv",
        "size_bytes": 1024
    }
    
    is_valid, errors = extractor.validate_config(config)
    assert is_valid
    assert len(errors) == 0
    
    # Invalid: missing file_id
    config_invalid = {
        "filename": "data.csv"
    }
    
    is_valid, errors = extractor.validate_config(config_invalid)
    assert not is_valid
    assert "file_id is required" in errors


def test_api_extractor_validation():
    """Тест валидации APIExtractor."""
    from app.services.extractors.api_extractor import APIExtractor
    
    extractor = APIExtractor()
    
    # Valid config
    config = {
        "url": "https://api.example.com/data",
        "method": "GET"
    }
    
    is_valid, errors = extractor.validate_config(config)
    assert is_valid
    assert len(errors) == 0
    
    # Invalid: missing url
    config_invalid = {
        "method": "GET"
    }
    
    is_valid, errors = extractor.validate_config(config_invalid)
    assert not is_valid
    assert "url is required" in errors
    
    # Invalid: unsupported method
    config_invalid2 = {
        "url": "https://api.example.com/data",
        "method": "INVALID"
    }
    
    is_valid, errors = extractor.validate_config(config_invalid2)
    assert not is_valid


def test_database_extractor_validation():
    """Тест валидации DatabaseExtractor."""
    from app.services.extractors.database_extractor import DatabaseExtractor
    
    extractor = DatabaseExtractor()
    
    # Valid config
    config = {
        "connection_string": "postgresql://user:pass@localhost/db",
        "query": "SELECT * FROM users LIMIT 10",
        "database_type": "postgresql"
    }
    
    is_valid, errors = extractor.validate_config(config)
    assert is_valid
    assert len(errors) == 0
    
    # Invalid: dangerous query
    config_dangerous = {
        "connection_string": "postgresql://user:pass@localhost/db",
        "query": "DROP TABLE users",
        "database_type": "postgresql"
    }
    
    is_valid, errors = extractor.validate_config(config_dangerous)
    assert not is_valid
    assert any("dangerous" in err.lower() for err in errors)


def test_prompt_extractor_validation():
    """Тест валидации PromptExtractor."""
    from app.services.extractors.prompt_extractor import PromptExtractor
    
    extractor = PromptExtractor()
    
    # Valid config
    config = {
        "prompt": "Generate 5 random user records with name, age, city"
    }
    
    is_valid, errors = extractor.validate_config(config)
    assert is_valid
    assert len(errors) == 0
    
    # Invalid: missing prompt
    config_invalid = {}
    
    is_valid, errors = extractor.validate_config(config_invalid)
    assert not is_valid
    assert "prompt is required" in errors


def test_stream_extractor_validation():
    """Тест валидации StreamExtractor."""
    from app.services.extractors.stream_extractor import StreamExtractor
    
    extractor = StreamExtractor()
    
    # Valid config
    config = {
        "stream_url": "wss://stream.example.com/data",
        "stream_type": "websocket"
    }
    
    is_valid, errors = extractor.validate_config(config)
    assert is_valid
    assert len(errors) == 0
    
    # Invalid: missing stream_url
    config_invalid = {
        "stream_type": "websocket"
    }
    
    is_valid, errors = extractor.validate_config(config_invalid)
    assert not is_valid
    assert "stream_url is required" in errors


def test_extraction_result_to_content_dict():
    """Тест преобразования ExtractionResult в ContentNode format."""
    from app.services.extractors.base import ExtractionResult
    
    result = ExtractionResult()
    result.text = "Test data"
    result.tables = [
        {
            "name": "test_table",
            "columns": [{"name": "col1", "type": "int"}, {"name": "col2", "type": "int"}],
            "rows": [{"col1": 1, "col2": 2}, {"col1": 3, "col2": 4}]
        }
    ]
    
    content_dict = result.to_content_dict()
    
    assert "text" in content_dict
    assert "tables" in content_dict
    assert "extracted_at" in content_dict
    assert content_dict["text"] == "Test data"
    assert len(content_dict["tables"]) == 1


if __name__ == "__main__":
    # Запуск тестов без pytest
    print("🧪 Running extractor tests...\n")
    
    tests = [
        ("Manual Extractor - Text", test_manual_extractor_text),
        ("Manual Extractor - JSON", test_manual_extractor_json),
        ("Manual Extractor - Table", test_manual_extractor_table),
        ("Manual Extractor - CSV", test_manual_extractor_csv),
        ("File Extractor - Validation", test_file_extractor_validation),
        ("API Extractor - Validation", test_api_extractor_validation),
        ("Database Extractor - Validation", test_database_extractor_validation),
        ("Prompt Extractor - Validation", test_prompt_extractor_validation),
        ("Stream Extractor - Validation", test_stream_extractor_validation),
        ("ExtractionResult - to_content_dict", test_extraction_result_to_content_dict),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"🔥 {name}: {e}")
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
