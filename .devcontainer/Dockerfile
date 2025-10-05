# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

# Install system deps for Home Assistant testing and aiohttp
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      git curl build-essential libffi-dev libssl-dev libatlas-base-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/hass-poolcop
