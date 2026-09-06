# Googletrans: дефолтный провайдер → DeepL

## Проблема

`googletrans` — неофициальная обёртка над веб-версией Google Translate. Регулярно ломается при изменениях на стороне Google, балансирует на грани ToS. В `machine_translation.py` провайдеры абстрагированы, но дефолтом сейчас является googletrans.

## Предлагаемое решение

1. **DeepL как дефолт** — если `DEEPL_API_KEY` настроен, использовать DeepL
2. **Googletrans как фоллбэк** — автоматическое переключение при ошибке DeepL
3. **Обработка ошибок** — при падении googletrans показывать вменяемую ошибку, а не краш
4. **Rate limiting** — добавить retry с exponential backoff для обоих провайдеров

## Реализация в `machine_translation.py`

```python
# Приоритет: DeepL (official API) > googletrans (web scraping)
PROVIDERS = {
    "deepl": {"priority": 1, "requires_key": True},
    "googletrans": {"priority": 2, "requires_key": False},
}
```

- При выборе провайдера: сначала проверять наличие API ключа для Deepl
- При ошибке: автоматический fallback на следующий доступный провайдер
- В GUI: показывать текущий провайдер иallowing ручной выбор

## Приоритет
Высокий — googletrans может отвалиться в любой момент, а DeepL уже подключён.

## Контекст
Замечение от архитектурного обзора Claude: "googletrans может отвалиться без предупреждения, делайте deepl дефолтным/фолбэком, а не наоборот."
