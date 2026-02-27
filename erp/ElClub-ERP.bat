@echo off
title El Club ERP
cd /d "%~dp0"

:: Kill any existing Streamlit on port 8502
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8502" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Seed teams if needed
python -c "from seed import seed_teams; seed_teams()" 2>nul

:: Launch Streamlit
start "" "C:\Users\Diego\AppData\Local\Programs\Python\Python311\Scripts\streamlit.exe" run app.py --server.port 8502 --server.address 0.0.0.0 --server.headless true

:: Wait for server
timeout /t 4 /nobreak >nul

:: Open as standalone app window
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:8502 --window-size=1400,900

echo.
echo El Club ERP corriendo en http://localhost:8502
echo Para acceso desde celular: http://[tu-ip-local]:8502
echo.
echo Presiona cualquier tecla para cerrar...
pause >nul
