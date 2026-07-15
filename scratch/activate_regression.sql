-- Activate regression account and set subscription to 10 years
UPDATE accounts
SET status = 'active',
    subscription_expires_at = NOW() + INTERVAL '3650 days',
    updated_at = NOW()
WHERE account_id = 'ST-QVJS-I94M';

-- Verify
SELECT account_id, status, subscription_expires_at FROM accounts WHERE account_id = 'ST-QVJS-I94M';
