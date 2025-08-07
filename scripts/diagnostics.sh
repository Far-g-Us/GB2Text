# Диагностический скрипт для GB Text Extraction Framework
# Использование: ./diagnostics.sh ваш_файл.gb

echo "### Диагностика GB Text Extraction Framework"
echo "Версия: $(python main.py --version 2>/dev/null || echo 'не установлена')"
echo "ОС: $(uname -a)"
echo "Дата: $(date)"
echo "Python версия: $(python --version 2>&1)"

if [ -z "$1" ]; then
    echo "Ошибка: Не указан ROM-файл"
    echo "Использование: $0 <rom_file>"
    exit 1
fi

ROM_FILE="$1"

if [ ! -f "$ROM_FILE" ]; then
    echo "Ошибка: Файл '$ROM_FILE' не существует"
    exit 1
fi

echo "ROM файл: $ROM_FILE"
echo "Хэш ROM (SHA-1): $(sha1sum "$ROM_FILE" 2>/dev/null || echo 'sha1sum не установлен')"
echo "Размер ROM: $(ls -lh "$ROM_FILE" | awk '{print $5}')"

# Создаем каталог для логов, если его нет
LOG_DIR="diagnostics_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

echo "=== Сбор информации о ROM ==="
python main.py "$ROM_FILE" --output json > "$LOG_DIR/rom_info.json" 2>&1
echo "Информация о ROM сохранена в $LOG_DIR/rom_info.json"

echo "=== Попытка извлечения текста ==="
python main.py "$ROM_FILE" --output text > "$LOG_DIR/extracted_text.txt" 2>"$LOG_DIR/extract_errors.log"
echo "Результаты извлечения сохранены в $LOG_DIR/extracted_text.txt"
echo "Ошибки сохранены в $LOG_DIR/extract_errors.log"

echo "=== Информация о системе ==="
echo "Содержимое папки plugins:" > "$LOG_DIR/system_info.txt"
ls -l plugins >> "$LOG_DIR/system_info.txt" 2>&1
echo "" >> "$LOG_DIR/system_info.txt"
echo "Содержимое папки plugins/config:" >> "$LOG_DIR/system_info.txt"
ls -l plugins/config >> "$LOG_DIR/system_info.txt" 2>&1
echo "" >> "$LOG_DIR/system_info.txt"
echo "Версии зависимостей:" >> "$LOG_DIR/system_info.txt"
pip freeze >> "$LOG_DIR/system_info.txt" 2>&1

echo ""
echo "Диагностика завершена. Все файлы сохранены в каталог: $LOG_DIR"
echo "Для отправки в issue GitHub приложите весь каталог $LOG_DIR"