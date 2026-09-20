@echo off 
cd /d "C:\X12" 
python sync_to_gsheets.py >> sync_log.txt 2>&1
