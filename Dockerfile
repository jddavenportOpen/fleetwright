# Fleetwright bridge — optional Docker image
# The bridge normally runs on the host (to access claude CLI + tmux + git).
# Use this image only if you mount the claude binary into the container.
#
# docker build -t fleetwright-bridge .
# docker run -v /opt/homebrew/bin/claude:/usr/local/bin/claude \
#            -p 8787:8787 --env-file .env fleetwright-bridge

FROM python:3.12-slim

WORKDIR /app

# Install system deps (tmux for fleet, git for worktrees)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux git && rm -rf /var/lib/apt/lists/*

# Install Python package
COPY pyproject.toml ./
COPY fleetwright/ ./fleetwright/
COPY config/ ./config/
COPY agents/ ./agents/

RUN pip install --no-cache-dir -e .

EXPOSE 8787

ENV HOST=0.0.0.0
ENV PORT=8787

CMD ["fleetwright-bridge", "--host", "0.0.0.0", "--port", "8787"]
