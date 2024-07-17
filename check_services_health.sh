#!/bin/sh

SERVICES="event_service verification_service retrieval_service classification_service notification_service"

for service in $SERVICES; do
    status=$(supervisorctl status $service | awk '{print $2}')
    if [ "$status" != "RUNNING" ]; then
        echo "$service is not running"
        exit 1
    fi

done

echo "All services are running"
exit 0
