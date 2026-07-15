import subprocess

SSH_KEY = r"d:\My projects\VPN\AWSKEY\ssh-key-2026-03-01.key"
SSH_HOST = "ubuntu@144.24.153.180"

def run_prod_sql(sql_query):
    cmd = [
        "ssh", "-o", "ConnectTimeout=15", "-i", SSH_KEY, SSH_HOST,
        "sudo docker exec -i billing-server-db-1 psql -U billing -d billing"
    ]
    res = subprocess.run(cmd, input=sql_query, capture_output=True, text=True)
    return f"RC: {res.returncode}\nOUT:\n{res.stdout}\nERR: {res.stderr}"

print(run_prod_sql("SELECT count(*) FROM accounts;"))
print(run_prod_sql("SELECT d.device_guid, a.account_id, d.is_active FROM devices d JOIN accounts a ON d.account_id = a.id WHERE d.device_guid = 'af652649-9ad0-4784-8b07-a0d4b44bd047';"))
