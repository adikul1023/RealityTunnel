import asyncio; from app.database import AsyncSessionLocal; from sqlalchemy import select; from app.models.account import Account; from app.services.provisioning.marzban import MarzbanProvisioningProvider  
async def main():  
    try:  
        provider = MarzbanProvisioningProvider()  
        u = await provider.get_user('user_st-0swg-qlrr')  
        print(u)  
    except Exception as e: print(e)  
asyncio.run(main())  
