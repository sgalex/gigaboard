"""Check data_nodes table structure"""
import asyncio
from sqlalchemy import inspect
from app.database import engine

async def check_data_nodes_structure():
    """Check the structure of data_nodes table."""
    
    async with engine.connect() as conn:
        def _inspect(connection):
            inspector = inspect(connection)
            columns = inspector.get_columns('data_nodes')
            return columns
        
        columns = await conn.run_sync(_inspect)
    
    print("\n" + "="*60)
    print("DATA_NODES TABLE STRUCTURE")
    print("="*60 + "\n")
    
    print(f"{'Column Name':<20} {'Type':<30} {'Nullable'}")
    print("-" * 60)
    
    for column in columns:
        col_name = column['name']
        col_type = str(column['type'])
        nullable = 'YES' if column['nullable'] else 'NO'
        print(f"{col_name:<20} {col_type:<30} {nullable}")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(check_data_nodes_structure())
