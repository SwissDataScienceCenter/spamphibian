#!/bin/sh

SERVICES="event_service verification_service retrieval_service classification_service notification_service"

for service in $SERVICES; do
    status=$(supervisorctl status $service | awk '{print $2}')
    if [ "$status" != "RUNNING" ]; then
        echo "$service is not running"
        exit 1
    fi

done

check_health() {
    python3 - <<END
import http.client
import sys

conn = http.client.HTTPConnection("localhost", 8001)
try:
    conn.request("GET", "/health")
    response = conn.getresponse()
    if response.status != 200:
        print(f"Health check failed (HTTP {response.status})")
        sys.exit(1)
except Exception as e:
    print(f"Health check failed: {str(e)}")
    sys.exit(1)
sys.exit(0)
END
}

#if ! check_health ; then
#    echo "verification_service flask health check failed"
#    exit 1
#fi

echo "All services are running"
exit 0
