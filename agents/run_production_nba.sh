#!/bin/bash

# NBA Production Workflow Runner
# This script sets up the environment and runs the production NBA workflow

# Set working directory to the agents folder
cd "$(dirname "$0")"

# Add current timestamp to log
echo "$(date): Starting NBA Production Workflow" >> nba_production.log

# Set Python path to include blitz src
export PYTHONPATH="$PYTHONPATH:$(pwd)/../blitz/src"

# Run the production NBA workflow
python3 production_ready_nba.py >> nba_production.log 2>&1

# Log completion
echo "$(date): NBA Production Workflow completed" >> nba_production.log
echo "----------------------------------------" >> nba_production.log 