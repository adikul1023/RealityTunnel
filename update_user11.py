import asyncio, traceback; from app.services.provisioning.marzban import MarzbanProvisioningProvider; from app.models.subscription_plan import QUARTERLY  
async def main():  
    try:  
        provider = MarzbanProvisioningProvider(); await provider.update_user('user_st-80g6-cl93', data_limit=QUARTERLY.data_quota_bytes); print('Successfully updated!')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
