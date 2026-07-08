# Manual Recovery Runbook

This guide details the procedure for manually restoring a database backup. An automated restore API does not currently exist due to the complexity of safely performing partial restores and handling concurrent-write hazards.

## Prerequisites
- A valid backup snapshot retrieved from the backup storage directory.
- Database credentials with sufficient privileges to restore tables and sequences.
- `psql` and `gunzip` utilities installed.

## Recovery Procedure

### 1. Stop the Application
Before performing a restore, ensure the billing server and any background workers are stopped to prevent concurrent writes during the restoration process.
```bash
systemctl stop billing-server
# OR
docker-compose stop billing-server
```

### 2. Prepare the Backup Archive
Locate the target backup directory and extract the `database.sql.gz` file.
```bash
cp backups/<backup_id>/database.sql.gz /tmp/database.sql.gz
gunzip /tmp/database.sql.gz
```

### 3. Restore the Database
Use `psql` to import the decompressed SQL file. The generated SQL dumps automatically account for foreign key constraints, provided you restore the entire database dump as-is.

```bash
psql -U billing -d billing -f /tmp/database.sql
```

> **Note:** If you are performing a partial restore, ensure you respect foreign key constraints. Specifically, `accounts` must be restored before `provisioning_profiles`, `subscriptions`, and `devices`.

### 4. Restart the Application
Once the `psql` import completes successfully without constraint violations, restart the billing server.
```bash
systemctl start billing-server
# OR
docker-compose start billing-server
```

### 5. Verify the Restore
Ensure the application is healthy and able to connect to the restored database.
```bash
curl -I http://localhost:8000/health
```
You should receive an HTTP 200 OK response. Check the logs for any startup errors.
