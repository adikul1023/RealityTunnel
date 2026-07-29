import asyncio, traceback; from app.database import AsyncSessionLocal; from sqlalchemy import select; from app.models.account import Account  
async def main():  
    try:  
        async with AsyncSessionLocal() as session:  
            result = await session.execute(select(Account))  
            accounts = result.scalars().all()  
            for acc in accounts: print(f'ID: {acc.id}, Account ID: {acc.account_id}, Marzban Username: {acc.marzban_username}, Plan: {acc.plan_id}')  
    except Exception as e: traceback.print_exc()  
asyncio.run(main())  
