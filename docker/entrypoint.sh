#!/bin/sh
# First start on an empty data volume: publish the datasets baked into the image as the
# first release, so the server has data before any refresh has run.
set -e

DATA_ROOT="${HOOPGRID_DATA_ROOT:-/data}"
if [ ! -e "$DATA_ROOT/current" ]; then
    mkdir -p "$DATA_ROOT/releases/seed"
    cp /app/backend/data/*.json "$DATA_ROOT/releases/seed/"
    ln -s releases/seed "$DATA_ROOT/current"
    echo "Data volume seeded from the image."
fi

exec "$@"
