import asyncio, traceback; from app.services.provisioning.marzban import MarzbanProvisioningProvider  
async def main():  
    try:  
        provider = MarzbanProvisioningProvider(); response = await provider._request_with_retry('GET', f'/api/user/user_st-80g6-cl93', expected_statuses=(200,)); print('RESPONSE:', response.json())  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
