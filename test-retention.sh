#!/bin/bash
# Usage: bash test-retention.sh <CRON_SECRET>
# Posts to the retention endpoint and prints status + body.

set -e

SECRET="$1"

if [ -z "$SECRET" ]; then
    echo "ERROR: missing argument."
    echo "Run as:  bash test-retention.sh <your-cron-secret>"
    exit 1
fi

URL="https://velib-wizard-api.onrender.com/api/cron/retention"

echo "POST $URL"
echo "---"

curl -sS -o /tmp/retention_body.json \
     -w "HTTP %{http_code}   time=%{time_total}s\n" \
     -X POST \
     -H "X-Cron-Secret: $SECRET" \
     "$URL"

echo ""
echo "--- response body ---"
cat /tmp/retention_body.json
echo ""
