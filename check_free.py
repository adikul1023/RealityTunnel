import asyncio; from app.database import AsyncSessionLocal; from sqlalchemy import select; from app.models.account import Account; from app.models.provisioning import ProvisioningProfile  
async def main():  
    try:  
        async with AsyncSessionLocal() as session:  
            result = await session.execute(select(Account).where(Account.plan_id == 'free'))  
            accounts = result.scalars().all()  
            print(f'Free accounts: {len(accounts)}')  
            for acc in accounts:  
                if acc.marzban_username: print(f'Provisioned: {acc.account_id}')  
    except Exception as e: print(e)  
asyncio.run(main())  
