"""
Утилиты для умного размещения нодов на канвасе.

Алгоритм размещения:
1. Для VISUALIZATION связей - размещаем вертикально под source node
2. Для TRANSFORMATION - размещаем горизонтально справа от source node
3. Проверяем коллизии с существующими нодами
4. Ищем ближайшее свободное место
5. Учитываем размеры нодов
"""

from typing import Dict, List, Tuple, Literal, Optional
from dataclasses import dataclass

# Константы размещения
DEFAULT_PADDING = 40  # Отступ между нодами
VERTICAL_SPACING = 150  # Вертикальное расстояние для visualization
HORIZONTAL_SPACING = 400  # Горизонтальное расстояние для transformation

# Размеры нодов по умолчанию
DEFAULT_SIZES = {
    "ContentNode": {"width": 320.0, "height": 200.0},
    "WidgetNode": {"width": 400.0, "height": 300.0},
    "SourceNode": {"width": 280.0, "height": 150.0},
    "CommentNode": {"width": 300.0, "height": 180.0},
}


@dataclass
class NodeBounds:
    """Границы нода на канвасе"""
    id: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class NodePosition:
    """Позиция нода"""
    x: float
    y: float


def check_collision(
    bounds1: Dict[str, float],
    bounds2: Dict[str, float],
    padding: float = 0
) -> bool:
    """
    Проверяет, пересекаются ли два прямоугольника (AABB collision detection).
    
    Args:
        bounds1: Первый прямоугольник {x, y, width, height}
        bounds2: Второй прямоугольник {x, y, width, height}
        padding: Дополнительный отступ для проверки
        
    Returns:
        True если прямоугольники пересекаются
    """
    return not (
        bounds1["x"] + bounds1["width"] + padding < bounds2["x"] or
        bounds1["x"] > bounds2["x"] + bounds2["width"] + padding or
        bounds1["y"] + bounds1["height"] + padding < bounds2["y"] or
        bounds1["y"] > bounds2["y"] + bounds2["height"] + padding
    )


def is_position_occupied(
    position: Dict[str, float],
    target_width: float,
    target_height: float,
    existing_nodes: List[NodeBounds],
    padding: float
) -> bool:
    """
    Проверяет, занята ли позиция каким-либо нодом.
    
    Args:
        position: Позиция для проверки {x, y}
        target_width: Ширина проверяемого нода
        target_height: Высота проверяемого нода
        existing_nodes: Список существующих нодов
        padding: Минимальный отступ между нодами
        
    Returns:
        True если позиция занята
    """
    target_bounds = {
        "x": position["x"],
        "y": position["y"],
        "width": target_width,
        "height": target_height
    }
    
    return any(
        check_collision(
            target_bounds,
            {"x": node.x, "y": node.y, "width": node.width, "height": node.height},
            padding
        )
        for node in existing_nodes
    )


def find_optimal_node_position(
    source_node: Dict[str, float],
    target_width: float,
    target_height: float,
    existing_nodes: List[NodeBounds],
    connection_type: Literal["visualization", "transformation"] = "transformation",
    padding: float = DEFAULT_PADDING
) -> Dict[str, float]:
    """
    Находит оптимальную позицию для нового нода с учетом коллизий.
    
    Для VISUALIZATION: размещает вертикально под source node
    Для TRANSFORMATION: размещает горизонтально справа от source node
    
    Если позиция занята - ищет ближайшее свободное место методом спирального поиска.
    
    Args:
        source_node: Исходный нод {x, y, width, height}
        target_width: Ширина нового нода
        target_height: Высота нового нода
        existing_nodes: Список существующих нодов для проверки коллизий
        connection_type: Тип связи ('visualization' или 'transformation')
        padding: Минимальный отступ между нодами
        
    Returns:
        Оптимальная позиция {x, y}
    """
    source_width = source_node.get("width", 320)
    source_height = source_node.get("height", 200)
    
    # Определяем предпочтительную позицию в зависимости от типа связи
    if connection_type == "visualization":
        # Вертикально под source node (по центру)
        preferred_position = {
            "x": source_node["x"] + (source_width / 2) - (target_width / 2),
            "y": source_node["y"] + source_height + VERTICAL_SPACING
        }
    else:
        # Горизонтально справа от source node
        preferred_position = {
            "x": source_node["x"] + source_width + HORIZONTAL_SPACING,
            "y": source_node["y"]
        }
    
    # Проверяем предпочтительную позицию
    if not is_position_occupied(preferred_position, target_width, target_height, existing_nodes, padding):
        print(f"✅ Preferred position is free: {preferred_position}")
        return preferred_position
    
    # Если предпочтительная позиция занята - ищем свободное место
    print(f"⚠️ Preferred position is occupied, searching for free space...")
    # Используем спиральный поиск вокруг предпочтительной позиции
    step = padding + 20  # Шаг поиска
    max_attempts = 100  # Максимум попыток
    
    for attempt in range(1, max_attempts):
        search_radius = attempt * step
        
        # Проверяем позиции по спирали
        candidate_positions = []
        
        if connection_type == "visualization":
            # Для visualization - сначала пробуем вертикально в разных позициях
            candidate_positions = [
                {"x": preferred_position["x"] - search_radius, "y": preferred_position["y"]},
                {"x": preferred_position["x"] + search_radius, "y": preferred_position["y"]},
                {"x": preferred_position["x"], "y": preferred_position["y"] + search_radius},
                {"x": preferred_position["x"] - search_radius, "y": preferred_position["y"] + search_radius},
                {"x": preferred_position["x"] + search_radius, "y": preferred_position["y"] + search_radius},
            ]
        else:
            # Для transformation - пробуем горизонтально
            candidate_positions = [
                {"x": preferred_position["x"] + search_radius, "y": preferred_position["y"]},
                {"x": preferred_position["x"], "y": preferred_position["y"] + search_radius},
                {"x": preferred_position["x"], "y": preferred_position["y"] - search_radius},
                {"x": preferred_position["x"] + search_radius, "y": preferred_position["y"] + search_radius},
                {"x": preferred_position["x"] + search_radius, "y": preferred_position["y"] - search_radius},
            ]
        
        # Проверяем каждую кандидатуру
        for candidate in candidate_positions:
            # Не размещаем ноды с отрицательными координатами
            if candidate["x"] < 0 or candidate["y"] < 0:
                continue
            
            if not is_position_occupied(candidate, target_width, target_height, existing_nodes, padding):
                print(f"✅ Found free position at attempt {attempt}: {candidate}")
                return candidate
    
    # Если не нашли свободное место - возвращаем предпочтительную позицию
    # (лучше перекрытие, чем полное отсутствие позиции)
    print(f"❌ Could not find non-overlapping position after {max_attempts} attempts, using preferred position")
    return preferred_position


def find_nearest_free_position(
    current_position: Dict[str, float],
    node_width: float,
    node_height: float,
    existing_nodes: List[NodeBounds],
    padding: float = DEFAULT_PADDING
) -> Dict[str, float]:
    """
    Находит ближайшее свободное место для ноды, которая пересекается с другой.
    
    В отличие от find_optimal_node_position, эта функция:
    - Ищет МИНИМАЛЬНЫЙ сдвиг от текущей позиции
    - Не использует большие offset'ы
    - Проверяет все направления равномерно
    
    Args:
        current_position: Текущая позиция {x, y}
        node_width: Ширина ноды
        node_height: Высота ноды
        existing_nodes: Список существующих нодов
        padding: Минимальный отступ между нодами
        
    Returns:
        Ближайшая свободная позиция {x, y}
    """
    # Сначала проверяем, нужен ли вообще сдвиг
    if not is_position_occupied(current_position, node_width, node_height, existing_nodes, padding):
        return current_position
    
    print(f"🔍 Finding nearest free position from: {current_position}")
    
    # Используем мелкий шаг для точного позиционирования
    step = 10  # MIN_STEP
    max_attempts = 50
    
    for attempt in range(1, max_attempts + 1):
        offset = attempt * step
        
        # Проверяем 8 направлений равномерно (по часовой стрелке)
        candidates = [
            {"x": current_position["x"] + offset, "y": current_position["y"]},           # право
            {"x": current_position["x"] + offset, "y": current_position["y"] + offset},  # право-вниз
            {"x": current_position["x"], "y": current_position["y"] + offset},           # вниз
            {"x": current_position["x"] - offset, "y": current_position["y"] + offset},  # лево-вниз
            {"x": current_position["x"] - offset, "y": current_position["y"]},           # лево
            {"x": current_position["x"] - offset, "y": current_position["y"] - offset},  # лево-вверх
            {"x": current_position["x"], "y": current_position["y"] - offset},           # вверх
            {"x": current_position["x"] + offset, "y": current_position["y"] - offset},  # право-вверх
        ]
        
        for candidate in candidates:
            # Не размещаем с отрицательными координатами
            if candidate["x"] < 0 or candidate["y"] < 0:
                continue
            
            if not is_position_occupied(candidate, node_width, node_height, existing_nodes, padding):
                print(f"✅ Found nearest free position at offset {offset}px: {candidate}")
                return candidate
    
    # Fallback: если не нашли за 50 попыток (500px), вернуть текущую позицию
    print("❌ Could not find free position within reasonable distance")
    return current_position


def get_node_default_size(node_type: str) -> Dict[str, float]:
    """
    Возвращает размер нода по умолчанию для заданного типа.
    
    Args:
        node_type: Тип нода (ContentNode, WidgetNode, etc.)
        
    Returns:
        Размеры {width, height}
    """
    return DEFAULT_SIZES.get(node_type, {"width": 320.0, "height": 200.0})
