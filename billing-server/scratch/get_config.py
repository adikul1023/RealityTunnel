import urllib.request
import urllib.parse
import json

data = urllib.parse.urlencode({'username': 'testadmin', 'password': 'testpass'}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8000/api/admin/token", data=data)
response = urllib.request.urlopen(req)
token_data = json.loads(response.read().decode('utf-8'))
token = token_data['access_token']

req2 = urllib.request.Request("http://127.0.0.1:8000/api/core/config", headers={'Authorization': f'Bearer {token}'})
response2 = urllib.request.urlopen(req2)
print(response2.read().decode('utf-8'))
