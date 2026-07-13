import asyncio
import sys
sys.path.insert(0, r'd:\My projects\VPN\OverREALITY\billing-server')
from app.routers.client import get_client_me
from app.models.account import Account
from app.database import AsyncSessionLocal
from sqlalchemy import select

async def test():
    async with AsyncSessionLocal() as session:
        acc = (await session.execute(select(Account).where(Account.account_id == 'ST-HTI8-N1ND'))).scalar_one()
        me = await get_client_me(current_account=acc, db=session)
        print(me)

asyncio.run(test())
