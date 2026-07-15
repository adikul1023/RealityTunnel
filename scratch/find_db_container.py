import subprocess

SSH_KEY = r"d:\My projects\VPN\AWSKEY\ssh-key-2026-03-01.key"
SSH_HOST = "ubuntu@144.24.153.180"

cmd = ["ssh", "-o", "ConnectTimeout=15", "-i", SSH_KEY, SSH_HOST, "sudo docker ps --format '{{.Names}}'"]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
