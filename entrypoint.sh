#!/bin/bash
set -e

# Run Gunicorn
exec gunicorn -b :5001 app:app