*** Settings ***
Documentation     Robot Framework tests for GB2Text GUI
Library            Process
Library            OperatingSystem

*** Variables ***
${APP_PATH}        main.py
${ROM_PATH}        test_roms/test.gb
${OUTPUT_DIR}     test_logs

*** Test Cases ***
Test GUI Can Start
    [Documentation]    Проверяет что приложение может запуститься
    Start Process    python.exe    ${APP_PATH}    alias=gb2text
    Sleep    2
    Process Should Be Running    gb2text
    Terminate Process    gb2text

Test App File Exists
    [Documentation]    Проверяет что главный файл существует
    File Should Exist    main.py
    File Should Exist    gui/main_window.py

Test Test ROM Directory
    [Documentation]    Проверяет директорию тестовых ROM
    Directory Should Exist    test_roms

Test GUI Module Structure
    [Documentation]    Проверяет структуру GUI модуля
    File Should Exist    gui/__init__.py
    File Should Exist    gui/editor.py
    File Should Exist    gui/main_window.py

Test Main Window Has GBTextExtractorGUI Class
    [Documentation]    Проверяет наличие класса в main_window
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    class GBTextExtractorGUI

Test Editor Has TextEditorFrame Class
    [Documentation]    Проверяет наличие класса в editor
    ${content}=    Get File    gui/editor.py
    Should Contain    ${content}    class TextEditorFrame

Test Python Exists
    [Documentation]    Проверяет наличие Python
    ${output}=    Run    python --version
    Log    ${output}

*** Keywords ***
# Запуск с указанием директории для результатов:
# .venv\Scripts\robot --outputdir test_logs tests/gui_tests.robot