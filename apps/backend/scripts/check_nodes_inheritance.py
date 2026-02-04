"""Check nodes table structure"""
import asyncio
from sqlalchemy import inspect
from app.database import engine

async def check_nodes_structure():
    """Check the structure of nodes table."""
    
    async with engine.connect() as conn:
        def _inspect(connection):
            inspector = inspect(connection)
            
            # Get nodes table
            nodes_cols = inspector.get_columns('nodes')
            
            # Get data_nodes table
            data_nodes_cols = inspector.get_columns('data_nodes')
            
            # Get foreign keys
            data_nodes_fks = inspector.get_foreign_keys('data_nodes')
            
            return nodes_cols, data_nodes_cols, data_nodes_fks
        
        nodes_cols, data_nodes_cols, data_nodes_fks = await conn.run_sync(_inspect)
    
    print("\n" + "="*80)
    print("NODES TABLE (BASE)")
    print("="*80 + "\n")
    
    print(f"{'Column Name':<25} {'Type':<35} {'Nullable'}")
    print("-" * 80)
    
    for column in nodes_cols:
        col_name = column['name']
        col_type = str(column['type'])
        nullable = 'YES' if column['nullable'] else 'NO'
        print(f"{col_name:<25} {col_type:<35} {nullable}")
    
    print("\n" + "="*80)
    print("DATA_NODES TABLE (CHILD)")
    print("="*80 + "\n")
    
    print(f"{'Column Name':<25} {'Type':<35} {'Nullable'}")
    print("-" * 80)
    
    for column in data_nodes_cols:
        col_name = column['name']
        col_type = str(column['type'])
        nullable = 'YES' if column['nullable'] else 'NO'
        print(f"{col_name:<25} {col_type:<35} {nullable}")
    
    print("\n" + "="*80)
    print("FOREIGN KEYS")
    print("="*80 + "\n")
    
    for fk in data_nodes_fks:
        print(f"  {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(check_nodes_structure())
