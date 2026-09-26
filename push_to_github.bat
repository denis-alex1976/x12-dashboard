@echo off
cd /d C:\X12
git add -A
git commit -m "Auto update %date% %time%"
git push
pause