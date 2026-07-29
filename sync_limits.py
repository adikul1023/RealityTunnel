import asyncio, traceback; from app.database import AsyncSessionLocal; from sqlalchemy import select; from app.models.account import Account; from app.models.subscription_plan import PLANS_REGISTRY; from app.services.provisioning.marzban import MarzbanProvisioningProvider  
async def main():  
    try:  
        async with AsyncSessionLocal() as session:  
            provider = MarzbanProvisioningProvider()  
            result = await session.execute(select(Account))  
            accounts = result.scalars().all()  
            for acc in accounts:  
                if acc.marzban_username and acc.plan_id in PLANS_REGISTRY:  
                    plan = PLANS_REGISTRY[acc.plan_id]  
                    try: await provider.update_user(acc.marzban_username, data_limit=plan.data_quota_bytes); print(f'Updated limit for {acc.marzban_username} to {plan.data_quota_bytes}')  
                    except Exception as e: print(f'Failed {acc.marzban_username}: {e}')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
