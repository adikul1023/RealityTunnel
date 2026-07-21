import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.account import Account
from app.models.base import AccountStatus

async def main():
    engine = create_async_engine('postgresql+asyncpg://billing:billing@127.0.0.1:5434/billing')
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(select(Account).limit(1))
        account = result.scalar_one_or_none()
        print('Account:', account)
        if account:
            print('Status type:', type(account.status))
            print('Status value:', account.status)
            print('Status enum == ACTIVE?', account.status == AccountStatus.ACTIVE)
            print('Status str == ACTIVE?', account.status == 'ACTIVE')

asyncio.run(main())
