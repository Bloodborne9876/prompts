@echo off

echo "directory>"
set /p targetPath=
echo inpus as %targetPath%

cd %targetPath%
mkdir "00_main"
mkdir "01_trial"
mkdir "02_title"

pause