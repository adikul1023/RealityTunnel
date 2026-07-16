import jwt, datetime, os
private_key = open("/app/dev_keys/admin/admin_ed25519_private.pem", "rb").read()
import uuid
now = datetime.datetime.now(datetime.timezone.utc)
token = jwt.encode({"sub": "00000000-0000-0000-0000-000000000000", "username": "superadmin", "role": "super_admin", "iss": "RealityTunnel Admin", "aud": "RealityTunnel Admin Panel", "iat": now, "nbf": now, "exp": now + datetime.timedelta(days=1), "jti": str(uuid.uuid4())}, private_key, algorithm="EdDSA")
print(token)
