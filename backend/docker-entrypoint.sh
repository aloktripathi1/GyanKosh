#!/bin/sh
# Render's Free tier doesn't support the Pre-Deploy Command feature, so
# migrations run here instead — before either the web server or the worker
# starts, regardless of which one Render invokes. Safe to run on every
# container start: alembic upgrade head is a no-op once already at head.
set -e
alembic upgrade head
exec "$@"
