import asyncio, traceback; from app.services.provisioning.marzban import MarzbanProvisioningProvider; from app.models.subscription_plan import QUARTERLY  
async def main():  
    try:  
        provider = MarzbanProvisioningProvider(); await provider._request_with_retry('PUT', f'/api/user/user_st-80g6-cl93', json={'data_limit': QUARTERLY.data_quota_bytes}, expected_statuses=(200,)); print('Successfully updated!')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
