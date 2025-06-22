#!/bin/bash

source .venv/bin/activate

uv sync
mcpo --port 8000 -- uv run server.py
