Start-Process powershell -ArgumentList "-NoExit","-Command","cd backend; python -m uvicorn main:app --reload"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd frontend; npm run dev"