@echo off

echo "directory>"
set /p targetPath=
echo inpus as %targetPath%

cd %targetPath%
mkdir "00_main"
mkdir "00_main\png"
mkdir "01_title"
mkdir "02_trial"

pause