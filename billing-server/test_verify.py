import asyncio
from app.security import JWTService
from app.config import settings

token = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyNTYyZTQxYy1hMzY0LTRlNTktYTZkMS0zMzVmNTQ4MTY5OTMiLCJhY2NvdW50IjoiU1QtUUtTSC02M0dLIiwiZGV2aWNlIjoiMTIzNDU2NzgtMTIzNC0xMjM0LTEyMzQtMTIzNDU2Nzg5MDEyIiwiaXNzIjoiUmVhbGl0eVR1bm5lbCBCaWxsaW5nL0F1dGgiLCJhdWQiOiJSZWFsaXR5VHVubmVsIENsaWVudCIsImlhdCI6MTc4NDQ3NDc1NiwibmJmIjoxNzg0NDc0NzU2LCJleHAiOjE3ODQ0NzU2NTYsImp0aSI6IjMxYWUzZGNhZDNmYjFlODkzMjRkYTM0M2MzZTMyNDE2In0.kC-WHg_4PwfplbOmQ7NSe258y42y_6BpA4bJ-zu8rcng9hh89GAB32XaT38EbAU6BVsYcdAWgQIbNUkH1UhqCw"

def main():
    service = JWTService(settings.jwt_private_key_path, settings.jwt_public_key_path)
    try:
        claims = service.verify_access_token(token)
        print("Claims:", claims)
    except Exception as e:
        print("Exception:", type(e), str(e))

if __name__ == "__main__":
    main()
