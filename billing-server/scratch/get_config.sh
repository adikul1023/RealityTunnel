#!/bin/bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/admin/token" -H "Content-Type: application/x-www-form-urlencoded" -d "username=testadmin&password=testpass" | grep -oP "(?<=\"access_token\":\")[^\"]+")
curl -s -X GET "http://127.0.0.1:8000/api/core/config" -H "Authorization: Bearer $TOKEN"
