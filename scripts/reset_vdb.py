import asyncio
import os
os.environ['PYTHONPATH'] = '.'
from app.config import get_settings
from app.db.vector_store import get_vector_store

async def reset_vdb():
    print("Resetting vector db...")
    s = get_settings()
    v = get_vector_store()
    try:
        await v.client.delete_collection(s.vector_collection)
        print("Deleted collection")
    except Exception as e:
        print("Error deleting collection:", e)
    await v.ensure_collection(s.vector_collection, s.EMBEDDING_DIM)
    print("Recreated collection")

if __name__ == "__main__":
    asyncio.run(reset_vdb())
