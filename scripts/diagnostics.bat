@echo off
echo ### Диагностика GB Text Extraction Framework
echo Версия: python main.py --version
echo OS: %OS%
echo Date: %DATE% %TIME%
echo Python version: python --version

if "%~1"=="" (
    echo Error: ROM file not specified
    echo Usage: %0 ^<rom_file^>
    exit /b 1
)

set ROM_FILE=%1
echo ROM file: %ROM_FILE%

REM Создаем каталог для логов
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set datetime=%%a
set LOG_DIR=diagnostics_%datetime:~0,8%_%datetime:~8,6%
mkdir "%LOG_DIR%"

echo === Collecting ROM information ===
python main.py "%ROM_FILE%" --output json > "%LOG_DIR%\rom_info.json" 2> "%LOG_DIR%\rom_errors.log"
echo ROM information saved to %LOG_DIR%\rom_info.json

echo === Attempting text extraction ===
python main.py "%ROM_FILE%" --output text > "%LOG_DIR%\extracted_text.txt" 2> "%LOG_DIR%\extract_errors.log"
echo Extraction results saved to %LOG_DIR%\extracted_text.txt

echo === System information ===
dir plugins > "%LOG_DIR%\system_info.txt" 2>&1
echo. >> "%LOG_DIR%\system_info.txt"
dir plugins\config >> "%LOG_DIR%\system_info.txt" 2>&1
echo. >> "%LOG_DIR%\system_info.txt"
pip freeze >> "%LOG_DIR%\system_info.txt" 2>&1

echo.
echo Diagnostic completed. All files saved to: %LOG_DIR%
echo To submit a GitHub issue, please attach the entire %LOG_DIR% folder