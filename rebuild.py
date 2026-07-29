import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('144.24.153.180', username='ubuntu', key_filename=r'd:\My projects\VPN\AWSKEY\ssh-key-2026-03-01.key')
cmd = '''cd /opt/realitytunnel/releases/oracle-update-2026-07-10 && sudo git checkout docker-compose.prod.yml && sudo sed -i 's/.*image: \${DOCKER_IMAGE.*/# &/' docker-compose.prod.yml && sudo docker compose -f docker-compose.prod.yml build billing-api && sudo docker compose -f docker-compose.prod.yml up -d billing-api'''
stdin, stdout, stderr = client.exec_command(cmd)
for line in stdout: print(line, end='')
for line in stderr: print(line, end='')
client.close()
