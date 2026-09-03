import asyncio
import os
import sys

# Setup environment to use local sqlite db
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///platform/safelane.db"

project_root = os.path.dirname(os.path.abspath("."))
platform_path = os.path.join(project_root, "SafeLane/platform")
sys.path.insert(0, platform_path)

from server.services.db import engine, async_session, Registration
from sqlalchemy import select, delete

async def main():
    async with async_session() as session:
        # Delete the registration since its token is invalid
        result = await session.execute(delete(Registration).where(Registration.repo == 'SafeLane_Demo-Video'))
        await session.commit()
        print(f"Deleted {result.rowcount} invalid registrations.")

asyncio.run(main())
