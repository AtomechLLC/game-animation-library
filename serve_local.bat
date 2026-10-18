@echo off
REM Double-click to open the local review copy of the atlas and mark bad GIFs (saved to marks.json).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py serve_local.py) else (python serve_local.py)
pause
