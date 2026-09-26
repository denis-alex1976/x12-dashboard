@echo off
cd /d C:\X12
echo Local IP:
ipconfig | findstr IPv4
echo.
echo Server will be available at http://<YOUR-IP>:8501
echo.
streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
pause