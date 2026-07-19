import requests

res = requests.post('http://127.0.0.1:8000/api/admin/login', json={'username': 'admin', 'password': 'super_admin'})
if res.status_code == 200:
    token = res.json()['access_token']
    plans_res = requests.get('http://127.0.0.1:8000/api/admin/plans', headers={'Authorization': f'Bearer {token}'})
    print('Status:', plans_res.status_code)
    print('Data:', plans_res.text)
else:
    print('Login failed:', res.text)
