@echo off
cd /d %~dp0
call venv\Scripts\activate
python pifuhd_server.py
pause
