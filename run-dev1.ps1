$projectRoot = "D:\SoundTools\sound-ai-tool"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$projectRoot\backend'; .\venv\Scripts\Activate.ps1; python -m uvicorn main:app --reload"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$projectRoot\frontend'; npm run dev"