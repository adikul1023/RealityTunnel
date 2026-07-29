import asyncio, traceback; from app.database import async_session_maker; from sqlalchemy import select; from app.models.provisioning import ProvisioningProfile; from app.services.provisioning.marzban import MarzbanProvisioningProvider; from app.models.subscription_plan import QUARTERLY  
async def main():  
    try:  
        async with async_session_maker() as session:  
            result = await session.execute(select(ProvisioningProfile).where(ProvisioningProfile.account_id == '0ea43cc5-8a2b-426c-843e-79774659b85c'))  
            profile = result.scalar_one_or_none()  
            if profile:  
                print('Remote User ID:', profile.remote_user_id)  
                provider = MarzbanProvisioningProvider()  
                await provider.update_user(profile.remote_user_id, data_limit=QUARTERLY.data_quota_bytes)  
                print('Successfully updated!')  
            else: print('Profile not found!')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
