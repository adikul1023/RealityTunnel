import jwt
import datetime

private_key = open(r"d:\My projects\VPN\OverREALITY\billing-server\dev_keys\ed25519_private.pem", "rb").read()
now = datetime.datetime.utcnow()
payload = {
    "sub": "00000000-0000-0000-0000-000000000000",
    "username": "superadmin",
    "role": "super_admin",
    "iss": "RealityTunnel Admin",
    "aud": "RealityTunnel Admin Panel",
    "iat": now,
    "nbf": now,
    "exp": now + datetime.timedelta(days=1),
}
token = jwt.encode(payload, private_key, algorithm="EdDSA")
print(token)
