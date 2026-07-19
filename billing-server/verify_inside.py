import asyncio
import httpx
import json
from app.security.admin_jwt import AdminJWTService

async def main():
    BASE_URL = 'http://localhost:8080/api'
    print('Generating Admin JWT...')
    jwt_svc = AdminJWTService()
    token = jwt_svc.issue_admin_token(
        admin_id='7bc4c345-c103-43f3-9dfe-a3fe53e77bb4',
        username='superadmin',
        is_super_admin=True
    )
    
    headers = {'Authorization': f'Bearer {token}'}

    async with httpx.AsyncClient() as client:
        print('\n=== 1. GET /api/admin/dashboard ===')
        res1 = await client.get(f'{BASE_URL}/admin/dashboard', headers=headers)
        print(f'Status: {res1.status_code}')
        print(json.dumps(res1.json(), indent=2))

        print('\n=== 2. GET /api/admin/subscriptions ===')
        res2 = await client.get(f'{BASE_URL}/admin/subscriptions', headers=headers)
        print(f'Status: {res2.status_code}')
        print(json.dumps(res2.json(), indent=2))

        print('\n=== 3. GET /api/admin/payments ===')
        res3 = await client.get(f'{BASE_URL}/admin/payments', headers=headers)
        print(f'Status: {res3.status_code}')
        print(json.dumps(res3.json(), indent=2))

        print('\n=== 4. GET /api/admin/audit-events ===')
        res4 = await client.get(f'{BASE_URL}/admin/audit-events', headers=headers)
        print(f'Status: {res4.status_code}')
        print(json.dumps(res4.json(), indent=2))

if __name__ == '__main__':
    asyncio.run(main())
