import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Account, Subscription

async def main():
    async with AsyncSessionLocal() as session:
        accs = (await session.execute(select(Account))).scalars().all()
        print('Accounts:', len(accs))
        for a in accs:
            print(f"ID: {a.id}, AccID: {a.account_id}, Status: {a.status}, Exp: {a.subscription_expires_at}")
        
        subs = (await session.execute(select(Subscription))).scalars().all()
        print('Subscriptions:', len(subs))
        for s in subs:
            print(f"ID: {s.id}, AccID: {s.account_id}, Status: {s.status}")

if __name__ == "__main__":
    asyncio.run(main())
