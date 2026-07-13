#!/bin/bash
set -e
echo 'PasswordForYou' | sudo -S bash -c '
umask 077
wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey
cat <<EOF > /etc/wireguard/wg0.conf
[Interface]
PrivateKey = $(cat /etc/wireguard/privatekey)
ListenPort = 51820
Address = 10.8.0.1/24
EOF
'
