-- Delete the devices from the previous aborted setup attempts
DELETE FROM devices WHERE device_guid = 'st-regression-device-0001-000000000000';
