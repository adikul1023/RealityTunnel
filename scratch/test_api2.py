import jwt
import datetime
import urllib.request

secret = '4020a5de542bb12ab1253e7f41f0217a32b005e83011400bc192e48e89f81cb4'
payload = {
    'sub': 'test-account',
    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
}
token = jwt.encode(payload, secret, algorithm='HS256')
req = urllib.request.Request('https://api.reviewbook.biz/api/client/config', headers={'Authorization': 'Bearer ' + token, 'X-Device-ID': 'test-device', 'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code, e.read().decode())
