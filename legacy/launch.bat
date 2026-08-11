@echo off
start "" "C:\Users\kmaje\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run "C:\Users\kmaje\Documents\job_application_assistant\app.py"
timeout /t 3 /nobreak >nul
start "" "http://localhost:8501"
