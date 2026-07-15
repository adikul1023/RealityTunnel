import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import sys

async def test_db():
    engine = create_async_engine("postgresql+asyncpg://billing:9771b91899a0ebe123482f42b5b69a948e58b906eb81518825ca55cbed49962e@144.24.153.180:5434/billing")
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT account_id FROM accounts WHERE account_id LIKE 'test_loc_%' OR account_id LIKE 'test_prod_%';"))
            for row in result:
                print("FOUND IN PROD DB:", row[0])
    except Exception as e:
        print("PROD DB ERR:", e)

    engine_loc = create_async_engine("postgresql+asyncpg://billing:billingdev123@127.0.0.1:5433/billing")
    try:
        async with engine_loc.begin() as conn:
            result = await conn.execute(text("SELECT account_id FROM accounts WHERE account_id LIKE 'test_loc_%' OR account_id LIKE 'test_prod_%';"))
            for row in result:
                print("FOUND IN LOCAL DB:", row[0])
    except Exception as e:
        print("LOC DB ERR:", e)

asyncio.run(test_db())
