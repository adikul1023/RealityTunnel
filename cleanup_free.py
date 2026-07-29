import asyncio, traceback; from app.database import AsyncSessionLocal; from sqlalchemy import select; from app.models.account import Account; from app.models.provisioning import ProvisioningProfile; from app.services.provisioning.marzban import MarzbanProvisioningProvider  
async def main():  
    try:  
        async with AsyncSessionLocal() as session:  
            provider = MarzbanProvisioningProvider()  
            result = await session.execute(select(Account).where(Account.plan_id == 'free'))  
            accounts = result.scalars().all()  
            for acc in accounts:  
                if acc.marzban_username:  
                    print(f'Deleting {acc.marzban_username} from Marzban')  
                    try: await provider.delete_user(acc.marzban_username)  
                    except Exception as e: print(e)  
                    res2 = await session.execute(select(ProvisioningProfile).where(ProvisioningProfile.account_id == acc.id))  
                    prof = res2.scalar_one_or_none()  
                    if prof: await session.delete(prof)  
                    acc.marzban_username = None  
                    await session.commit()  
                    print(f'Cleaned up {acc.account_id}')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
