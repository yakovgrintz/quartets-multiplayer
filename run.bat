@echo off
echo Checking and installing requirements...
pip install -r requirements.txt -q

echo Starting Quartets Multiplayer Server locally...

:: פותח שני חלונות דפדפן ברקע עם השהיה של 2 שניות כדי שהשרת יספיק לעלות
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000 & start http://127.0.0.1:8000"

python -m uvicorn main:app --reload
pause