FROM gozargah/marzban:latest

# Install patch utility
RUN apt-get update && apt-get install -y patch && rm -rf /var/lib/apt/lists/*

COPY marzban-host.patch /tmp/marzban-host.patch

# Patch main.py to respect UVICORN_HOST instead of hardcoding 127.0.0.1.
# This patch will fail loudly if Marzban updates main.py significantly, 
# acting as a safety guard.
RUN patch /code/main.py < /tmp/marzban-host.patch
