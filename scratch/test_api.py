import requests

url = 'https://api.stealthy.co.in/api/auth/login'
payload = {
    'account_id': 'ST-V9SF-IHCU',
    'master_token': 'cc79bac3bb1c38850d3f65afe3676dd3c1221e7753bc191665f5a7e8febddbe8',
    'device_guid': '00000000-0000-0000-0000-000000000000'
}
headers = {'Content-Type': 'application/json'}

try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
