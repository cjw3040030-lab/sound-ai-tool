Write-Host "Starting backend server..."

Start-Process powershell -ArgumentList "-NoExit", "-Command", "
cd 'C:\Users\WD\Desktop\sound-ai-tool\backend';
.\venv\Scripts\Activate.ps1;
python -m uvicorn main:app --reload
"

Write-Host "Starting frontend server..."

Start-Process powershell -ArgumentList "-NoExit", "-Command", "
cd 'C:\Users\WD\Desktop\sound-ai-tool\frontend';
npm run dev
"
