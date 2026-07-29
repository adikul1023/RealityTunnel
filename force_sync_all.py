import asyncio, traceback; from app.database import AsyncSessionLocal; from sqlalchemy import select; from app.models.account import Account; from app.services.provisioning.service import ProvisioningService; from app.dependencies import get_marzban_provider  
async def main():  
    try:  
        async with AsyncSessionLocal() as session:  
            provider = get_marzban_provider()  
            service = ProvisioningService(session, provider)  
            result = await session.execute(select(Account))  
            accounts = result.scalars().all()  
            for acc in accounts:  
                try: await service.synchronize(acc.id); print(f'Synced {acc.account_id}')  
                except Exception as e: print(f'Failed {acc.account_id}: {e}')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
