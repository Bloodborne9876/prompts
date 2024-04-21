@echo off

echo "directory>"
set /p targetPath=
echo inpus as %targetPath%

cd %targetPath%
mkdir "00_main\png"
mkdir "00_main\jpg"
mkdir "01_thumbnail"
mkdir "10_booth\01_data"
mkdir "11_dmm\01_data"
mkdir "11_dmm\01_thumbnail"
mkdir "12_gumroad\01_data"

pause