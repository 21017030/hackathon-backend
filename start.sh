#!/bin/bash
cd "$(dirname "$0")"
pip install -q --user -r requirements.txt
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
echo "FastAPI 서버 시작됨 (PID: $!)"
