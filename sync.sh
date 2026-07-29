#!/bin/bash
sudo docker exec 09a78c2b9503db66b6ac31aed64f650faba94d67-postgres-1 psql -U billing -d billing -t -A -c "SELECT id FROM vpn_profiles;" > /tmp/ids.txt
while read id; do
  echo "Syncing $id"
  curl -s -X POST -H "Authorization: Bearer superadmin" "http://localhost:8000/api/admin/billing/provisioning/$id/sync"
  echo ""
done < /tmp/ids.txt
