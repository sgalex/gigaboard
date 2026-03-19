/**
 * Утилиты для умного размещения нодов на канвасе.
 * 
 * Алгоритм размещения:
 * 1. Для VISUALIZATION связей - размещаем вертикально под source node
 * 2. Проверяем коллизии с существующими нодами
 * 3. Ищем ближайшее свободное место
 * 4. Учитываем размеры нодов
 */

export interface NodePosition {
    x: number
    y: number
}

export interface NodeBounds {
    id: string
    x: number
    y: number
    width: number
    height: number
}

interface FindPositionParams {
    sourceNode: NodePosition & { width?: number; height?: number }
    targetWidth: number
    targetHeight: number
    existingNodes: NodeBounds[]
    connectionType?: 'visualization' | 'transformation'
    padding?: number
}

const DEFAULT_PADDING = 40 // Отступ между нодами
const VERTICAL_SPACING = 150 // Вертикальное расстояние для visualization
const HORIZONTAL_SPACING = 400 // Горизонтальное расстояние для transformation
const MIN_STEP = 10 // Минимальный шаг поиска для точного позиционирования

/**
 * Проверяет, пересекаются ли два прямоугольника (AABB collision detection)
 */
function checkCollision(
    bounds1: { x: number; y: number; width: number; height: number },
    bounds2: { x: number; y: number; width: number; height: number },
    padding: number = 0
): boolean {
    return !(
        bounds1.x + bounds1.width + padding < bounds2.x ||
        bounds1.x > bounds2.x + bounds2.width + padding ||
        bounds1.y + bounds1.height + padding < bounds2.y ||
        bounds1.y > bounds2.y + bounds2.height + padding
    )
}

/**
 * Проверяет, занята ли позиция каким-либо нодом
 */
function isPositionOccupied(
    position: NodePosition,
    targetWidth: number,
    targetHeight: number,
    existingNodes: NodeBounds[],
    padding: number
): boolean {
    const targetBounds = {
        x: position.x,
        y: position.y,
        width: targetWidth,
        height: targetHeight
    }

    return existingNodes.some(node =>
        checkCollision(targetBounds, node, padding)
    )
}

/**
 * Находит оптимальную позицию для нового нода с учетом коллизий.
 * 
 * Для VISUALIZATION: размещает вертикально под source node
 * Для TRANSFORMATION: размещает горизонтально справа от source node
 * 
 * Если позиция занята - ищет ближайшее свободное место методом спирального поиска
 */
export function findOptimalNodePosition({
    sourceNode,
    targetWidth,
    targetHeight,
    existingNodes,
    connectionType = 'visualization',
    padding = DEFAULT_PADDING
}: FindPositionParams): NodePosition {
    const sourceWidth = sourceNode.width || 320
    const sourceHeight = sourceNode.height || 200

    // Определяем предпочтительную позицию в зависимости от типа связи
    let preferredPosition: NodePosition

    if (connectionType === 'visualization') {
        // Вертикально под source node (по центру)
        preferredPosition = {
            x: sourceNode.x + (sourceWidth / 2) - (targetWidth / 2),
            y: sourceNode.y + sourceHeight + VERTICAL_SPACING
        }
    } else {
        // Горизонтально справа от source node
        preferredPosition = {
            x: sourceNode.x + sourceWidth + HORIZONTAL_SPACING,
            y: sourceNode.y
        }
    }

    // Проверяем предпочтительную позицию
    if (!isPositionOccupied(preferredPosition, targetWidth, targetHeight, existingNodes, padding)) {
        console.log('✅ Preferred position is free:', preferredPosition)
        return preferredPosition
    }

    // Если предпочтительная позиция занята - ищем свободное место
    console.warn('⚠️ Preferred position is occupied, searching for free space...')
    // Используем спиральный поиск вокруг предпочтительной позиции
    const step = padding + 20 // Шаг поиска
    const maxAttempts = 100 // Максимум попыток

    for (let attempt = 1; attempt < maxAttempts; attempt++) {
        const searchRadius = attempt * step

        // Проверяем позиции по спирали
        const candidatePositions: NodePosition[] = []

        if (connectionType === 'visualization') {
            // Для visualization - сначала пробуем вертикально в разных позициях
            candidatePositions.push(
                { x: preferredPosition.x - searchRadius, y: preferredPosition.y },
                { x: preferredPosition.x + searchRadius, y: preferredPosition.y },
                { x: preferredPosition.x, y: preferredPosition.y + searchRadius },
                { x: preferredPosition.x - searchRadius, y: preferredPosition.y + searchRadius },
                { x: preferredPosition.x + searchRadius, y: preferredPosition.y + searchRadius }
            )
        } else {
            // Для transformation - пробуем горизонтально
            candidatePositions.push(
                { x: preferredPosition.x + searchRadius, y: preferredPosition.y },
                { x: preferredPosition.x, y: preferredPosition.y + searchRadius },
                { x: preferredPosition.x, y: preferredPosition.y - searchRadius },
                { x: preferredPosition.x + searchRadius, y: preferredPosition.y + searchRadius },
                { x: preferredPosition.x + searchRadius, y: preferredPosition.y - searchRadius }
            )
        }

        // Проверяем каждую кандидатуру
        for (const candidate of candidatePositions) {
            // Не размещаем ноды с отрицательными координатами
            if (candidate.x < 0 || candidate.y < 0) continue

            if (!isPositionOccupied(candidate, targetWidth, targetHeight, existingNodes, padding)) {
                console.log(`✅ Found free position at attempt ${attempt}:`, candidate)
                return candidate
            }
        }
    }

    // Если не нашли свободное место - возвращаем предпочтительную позицию
    // (лучше перекрытие, чем полное отсутствие позиции)
    console.warn('❌ Could not find non-overlapping position after', maxAttempts, 'attempts, using preferred position')
    return preferredPosition
}

/**
 * Находит ближайшее свободное место для ноды, которая была вручную перемещена
 * и пересекается с другой нодой.
 * 
 * В отличие от findOptimalNodePosition, эта функция:
 * - Ищет МИНИМАЛЬНЫЙ сдвиг от текущей позиции
 * - Не использует большие offset'ы
 * - Проверяет все направления равномерно
 */
export function findNearestFreePosition(
    currentPosition: NodePosition,
    nodeWidth: number,
    nodeHeight: number,
    existingNodes: NodeBounds[],
    padding: number = DEFAULT_PADDING
): NodePosition {
    // Сначала проверяем, нужен ли вообще сдвиг
    if (!isPositionOccupied(currentPosition, nodeWidth, nodeHeight, existingNodes, padding)) {
        return currentPosition
    }

    console.log('🔍 Finding nearest free position from:', currentPosition)

    // Используем мелкий шаг для точного позиционирования
    const step = MIN_STEP
    const maxAttempts = 50

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        const offset = attempt * step

        // Проверяем 8 направлений равномерно (по часовой стрелке)
        const candidates: NodePosition[] = [
            { x: currentPosition.x + offset, y: currentPosition.y },           // право
            { x: currentPosition.x + offset, y: currentPosition.y + offset },  // право-вниз
            { x: currentPosition.x, y: currentPosition.y + offset },           // вниз
            { x: currentPosition.x - offset, y: currentPosition.y + offset },  // лево-вниз
            { x: currentPosition.x - offset, y: currentPosition.y },           // лево
            { x: currentPosition.x - offset, y: currentPosition.y - offset },  // лево-вверх
            { x: currentPosition.x, y: currentPosition.y - offset },           // вверх
            { x: currentPosition.x + offset, y: currentPosition.y - offset },  // право-вверх
        ]

        for (const candidate of candidates) {
            // Не размещаем с отрицательными координатами
            if (candidate.x < 0 || candidate.y < 0) continue

            if (!isPositionOccupied(candidate, nodeWidth, nodeHeight, existingNodes, padding)) {
                console.log(`✅ Found nearest free position at offset ${offset}px:`, candidate)
                return candidate
            }
        }
    }

    // Fallback: если не нашли за 50 попыток (500px), вернуть текущую позицию
    console.warn('❌ Could not find free position within reasonable distance')
    return currentPosition
}

/**
 * Вспомогательная функция для преобразования React Flow нодов в NodeBounds
 */
export function convertNodesToBounds(nodes: Array<{
    id: string
    position: { x: number; y: number }
    width?: number
    height?: number
}>): NodeBounds[] {
    return nodes.map(node => ({
        id: node.id,
        x: node.position.x,
        y: node.position.y,
        width: node.width || 320,
        height: node.height || 200
    }))
}
