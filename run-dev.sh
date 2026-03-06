#!/bin/zsh

source .venv/bin/activate || exit 1

cd backend || exit 1
python -m uvicorn main:app --reload &

cd ../frontend || exit 1
npm run dev &

wait