import asyncio, traceback; from app.database import AsyncSessionLocal; from sqlalchemy import select; from app.models.account import Account; from app.models.provisioning import ProvisioningProfile  
async def main():  
    try:  
        async with AsyncSessionLocal() as session:  
            result = await session.execute(select(Account).where(Account.id == '0ea43cc5-8a2b-426c-843e-79774659b85c'))  
            account = result.scalar_one_or_none()  
            if account:  
                print('Account found! account_id:', account.account_id, 'marzban_username:', account.marzban_username)  
            else: print('Account not found!')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
