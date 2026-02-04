-- Fix orphaned source_nodes before running migration
-- This script handles foreign key violations

-- Step 1: Find orphaned source_nodes (those without matching content_nodes)
SELECT id, name FROM source_nodes 
WHERE id NOT IN (SELECT id FROM content_nodes);

-- Step 2: Delete orphaned source_nodes
DELETE FROM source_nodes 
WHERE id NOT IN (SELECT id FROM content_nodes);

-- Step 3: Now you can run: alembic upgrade head
