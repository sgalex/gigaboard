"""Source Registry - central registry for all source type handlers.

Позволяет регистрировать и получать обработчики по типу источника.
"""
from typing import Type

from app.sources.base import BaseSource


class SourceRegistry:
    """Registry of source type handlers.
    
    Usage:
        # Register a handler
        SourceRegistry.register(CSVSource)
        
        # Get a handler
        handler = SourceRegistry.get("csv")
        result = await handler.extract(config)
    """
    
    _handlers: dict[str, BaseSource] = {}
    _handler_classes: dict[str, Type[BaseSource]] = {}
    
    @classmethod
    def register(cls, handler_class: Type[BaseSource]) -> None:
        """Register a source handler class.
        
        Args:
            handler_class: BaseSource subclass to register
        """
        handler = handler_class()
        cls._handlers[handler.source_type] = handler
        cls._handler_classes[handler.source_type] = handler_class
    
    @classmethod
    def get(cls, source_type: str) -> BaseSource | None:
        """Get handler instance by source type.
        
        Args:
            source_type: Type of source (csv, json, api, etc.)
            
        Returns:
            Handler instance or None if not found
        """
        return cls._handlers.get(source_type)
    
    @classmethod
    def get_all(cls) -> dict[str, BaseSource]:
        """Get all registered handlers.
        
        Returns:
            Dict of source_type -> handler instance
        """
        return cls._handlers.copy()
    
    @classmethod
    def get_vitrina_items(cls) -> list[dict]:
        """Get items for source vitrina (frontend display).
        
        Returns:
            List of dicts with source_type, display_name, icon, description
        """
        items = []
        for handler in cls._handlers.values():
            items.append({
                "source_type": handler.source_type,
                "display_name": handler.display_name,
                "icon": handler.icon,
                "description": handler.description,
            })
        return items
    
    @classmethod
    def is_registered(cls, source_type: str) -> bool:
        """Check if source type is registered.
        
        Args:
            source_type: Type to check
            
        Returns:
            True if registered
        """
        return source_type in cls._handlers


def get_source_handler(source_type: str) -> BaseSource:
    """Get source handler by type.
    
    Args:
        source_type: Type of source
        
    Returns:
        Handler instance
        
    Raises:
        ValueError: If source type is not registered
    """
    handler = SourceRegistry.get(source_type)
    if handler is None:
        raise ValueError(f"Unknown source type: {source_type}. "
                        f"Registered types: {list(SourceRegistry.get_all().keys())}")
    return handler
