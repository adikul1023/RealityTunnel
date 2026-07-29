import asyncio, traceback; from app.services.provisioning.marzban import MarzbanProvisioningProvider  
async def main():  
    try:  
        provider = MarzbanProvisioningProvider(); users = await provider.get_users()  
        for user in users: print(user.username)  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
