import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import uuid

async def inspect():
    engine = create_async_engine("postgresql+asyncpg://billing:9771b91899a0ebe123482f42b5b69a948e58b906eb81518825ca55cbed49962e@144.24.153.180:5434/billing")
    async with engine.begin() as conn:
        print("=== ACCOUNTS ST-WNKB-QI79 ===")
        res = await conn.execute(text("SELECT id, account_id, plan_id, created_at FROM accounts WHERE account_id = 'ST-WNKB-QI79';"))
        for row in res:
            print(dict(row._mapping))
            acc_uuid = row.id

        print("\n=== EVERY ROW IN devices FOR ACCOUNT ST-WNKB-QI79 ===")
        res2 = await conn.execute(text(f"SELECT account_id, device_guid, friendly_name, is_active, first_seen_at, last_seen_at FROM devices WHERE account_id = '{acc_uuid}';"))
        for row in res2:
            print(dict(row._mapping))

        print("\n=== DEVICE af652649-9ad0-4784-8b07-a0d4b44bd047 ACROSS ALL ACCOUNTS ===")
        res3 = await conn.execute(text("SELECT d.account_id, a.account_id as acc_str, d.device_guid, d.is_active, d.first_seen_at, d.last_seen_at FROM devices d JOIN accounts a ON d.account_id = a.id WHERE d.device_guid = 'af652649-9ad0-4784-8b07-a0d4b44bd047';"))
        for row in res3:
            print(dict(row._mapping))

asyncio.run(inspect())
