@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Premiere installation, patientez quelques minutes...
  py -3 -m venv .venv || python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install -q -r requirements.txt
echo.
echo ================================================
echo   Quiz Party demarre : http://localhost:8000
echo   (fermez cette fenetre pour arreter)
echo ================================================
echo.
start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
