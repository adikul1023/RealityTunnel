import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from app.models import Payment
async def main():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Payment))
        print(type(result))
        scalars = result.scalars()
        print(type(scalars))
        all_res = scalars.all()
        print(type(all_res))
asyncio.run(main())
