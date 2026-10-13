# Starts Django and Vite in two windows. Close the windows to stop.
Set-Location $PSScriptRoot
if (-not (Test-Path backend\.venv)) { throw "Run setup.ps1 first." }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm run dev"
Write-Host "Backend: http://127.0.0.1:8000   Frontend: http://localhost:5173"
