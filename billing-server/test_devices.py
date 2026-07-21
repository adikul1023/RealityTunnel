import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Device

async def main():
    async with AsyncSessionLocal() as session:
        devs = (await session.execute(select(Device))).scalars().all()
        for d in devs:
            print(f"Device: {d.guid}, Account: {d.account_id}")

if __name__ == "__main__":
    asyncio.run(main())
