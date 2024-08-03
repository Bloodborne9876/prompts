@echo off

echo "directory>"
set /p targetPath=
echo inpus as %targetPath%

cd %targetPath%
mkdir "00_main\png"
mkdir "01_thumbnail"
mkdir "02_title
mkdir "03_check"

pause