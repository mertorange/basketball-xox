#!/bin/sh
# Publish the datasets baked into the image when the data volume has not seen them yet:
# on the first start, and after an image update (its code may expect new fields). Restarting
# the same image keeps whatever the last data refresh published.
set -e

python /app/backend/scripts/refresh_data.py --publish-image-data /app/backend/data

exec "$@"
