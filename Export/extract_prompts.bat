@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================
echo  SD Prompt Extractor
echo ============================================
echo.

if "%~1"=="" (
    set /p INPUT_FOLDER="PNG Folder (drag and drop or type path): "
) else (
    set INPUT_FOLDER=%~1
)

echo.
set /p OUTPUT_FOLDER="Output Folder (Enter to use same as input): "
echo.
set /p IGNORE_STR="Extra ignore string (Enter to skip): "
echo.

set ARGS="%INPUT_FOLDER%"

if not "%OUTPUT_FOLDER%"=="" (
    set ARGS=%ARGS% --output "%OUTPUT_FOLDER%"
)

if not "%IGNORE_STR%"=="" (
    set ARGS=%ARGS% --ignore "%IGNORE_STR%"
)

echo Running...
echo.
python extract_prompts.py %ARGS%

echo.
pause
