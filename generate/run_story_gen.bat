@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 使い方:
REM   run_story_gen.bat                    -- 全幕生成
REM   run_story_gen.bat --start 3          -- 幕3から再開
REM   run_story_gen.bat --hires            -- Hires.fix ON
REM   run_story_gen.bat --no-hires         -- Hires.fix OFF
REM   run_story_gen.bat --config my.json   -- 別の設定ファイル
REM   run_story_gen.bat --dry-run          -- プロンプト確認のみ

REM python story_gen.py %*
python story_gen.py %* --config config.jsonc

pause
