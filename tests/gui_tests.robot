*** Settings ***
Documentation     Robot Framework tests for GB2Text GUI interactions
Library            Process
Library            OperatingSystem
Library            String

*** Variables ***
${APP_PATH}        main.py
${ROM_PATH}        test_roms/test.gb
${OUTPUT_DIR}     test_logs

*** Test Cases ***
Test GUI Can Start
    [Documentation]    Проверяет что приложение может запуститься
    Start Process    python    ${APP_PATH}    alias=gb2text
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

Test Main Window Has Required Methods
    [Documentation]    Проверяет наличие основных методов
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    def _

Test Editor Has Required Methods
    [Documentation]    Проверяет наличие методов редактора
    ${content}=    Get File    gui/editor.py
    Should Contain    ${content}    def next_entry
    Should Contain    ${content}    def prev_entry
    Should Contain    ${content}    def undo
    Should Contain    ${content}    def redo

Test ROM Validation Functions Exist
    [Documentation]    Проверяет наличие функций валидации ROM
    ${content}=    Get File    core/rom.py
    Should Contain    ${content}    validate_rom_file

Test Plugin Manager Integration
    [Documentation]    Проверяет интеграцию PluginManager
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    PluginManager

Test I18n Integration
    [Documentation]    Проверяет интеграцию i18n
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    I18N

Test Guide Manager Integration
    [Documentation]    Проверяет интеграцию GuideManager
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    GuideManager

Test TMX Handler Integration
    [Documentation]    Проверяет интеграцию TMXHandler
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    TMXHandler

Test ROM Cache Exists
    [Documentation]    Проверяет наличие ROMCache
    ${content}=    Get File    core/rom_cache.py
    Should Contain    ${content}    class ROMCache

Test Export Functionality Exists
    [Documentation]    Проверяет наличие функций экспорта
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    export_csv
    Should Contain    ${content}    export_json

Test Import Functionality Exists
    [Documentation]    Проверяет наличие функций импорта
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    import_csv

Test Batch Processing Exists
    [Documentation]    Проверяет наличие пакетной обработки
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    batch_process

Test Progress Bar Integration
    [Documentation]    Проверяет интеграцию progress bar
    ${content}=    Get File    gui/main_window.py
    Should Contain    ${content}    progress

Test All Core Modules Importable
    [Documentation]    Проверяет импортируемость всех core модулей
    ${output}=    Run    python -c "from core import rom, scanner, decoder, extractor, injector, guide, i18n, plugin_manager, tmx, translation_validator, translation_filler"
    Should Be Empty    ${output}

Test All Plugin Modules Importable
    [Documentation]    Проверяет импортируемость всех plugin модулей
    ${output}=    Run    python -c "from plugins import auto_detect, generic"
    Should Be Empty    ${output}

Test GUI Modules Importable
    [Documentation]    Проверяет импортируемость GUI модулей
    ${output}=    Run    python -c "from gui import main_window, editor"
    Should Be Empty    ${output}

Test Requirements File Exists
    [Documentation]    Проверяет наличие requirements.txt
    File Should Exist    requirements.txt

Test Requirements Content
    [Documentation]    Проверяет содержимое requirements.txt
    ${content}=    Get File    requirements.txt
    Should Contain    ${content}    tkinter
    Should Contain    ${content}    pytest

Test Version File Exists
    [Documentation]    Проверяет наличие VERSION файла
    File Should Exist    VERSION

Test Readme Exists
    [Documentation]    Проверяет наличие README
    File Should Exist    README.md

Test Locales Directory Structure
    [Documentation]    Проверяет структуру директории локалей
    Directory Should Exist    locales
    Directory Should Exist    locales/en
    Directory Should Exist    locales/ru
    Directory Should Exist    locales/ja
    Directory Should Exist    locales/zh

Test Plugins Config Directory
    [Documentation]    Проверяет директорию конфигов плагинов
    Directory Should Exist    plugins/config
    File Should Exist    plugins/config/_template_game.json

Test Guides Directory
    [Documentation]    Проверяет директорию гайдов
    Directory Should Exist    guides

Test Scripts Directory
    [Documentation]    Проверяет наличие скриптов
    Directory Should Exist    scripts
    File Should Exist    scripts/diagnostics.py

Test Docs Directory
    [Documentation]    Проверяет документацию
    Directory Should Exist    docs

Test CI Workflows Exist
    [Documentation]    Проверяет наличие CI workflow
    File Should Exist    .github/workflows/tests.yml

Test Tests Directory Structure
    [Documentation]    Проверяет структуру директории тестов
    Directory Should Exist    tests
    File Should Exist    tests/test_rom.py
    File Should Exist    tests/test_scanner.py
    File Should Exist    tests/test_decoder.py

Test Benchmark Tests Exist
    [Documentation]    Проверяет наличие benchmark тестов
    File Should Exist    tests/benchmarks/test_performance.py

Test Coverage Configuration Exists
    [Documentation]    Проверяет конфигурацию coverage
    File Should Exist    .coveragerc

Test Pytest Configuration Exists
    [Documentation]    Проверяет конфигурацию pytest
    File Should Exist    pytest.ini

Test Ruff Configuration Exists
    [Documentation]    Проверяет конфигурацию ruff
    File Should Exist    ruff.toml

Test MyPy Configuration Exists
    [Documentation]    Проверяет конфигурацию mypy
    File Should Exist    mypy.ini

*** Keywords ***
# Запуск с указанием директории для результатов:
# .venv\Scripts\robot --outputdir test_logs tests/gui_tests.robot
