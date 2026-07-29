import asyncio, traceback; from app.services.provisioning.marzban import MarzbanProvisioningProvider; from app.models.subscription_plan import QUARTERLY  
async def main():  
    try:  
        provider = MarzbanProvisioningProvider(); await provider.update_user('0ea43cc5-8a2b-426c-843e-79774659b85c', data_limit_bytes=QUARTERLY.data_quota_bytes); print('Successfully updated!')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
