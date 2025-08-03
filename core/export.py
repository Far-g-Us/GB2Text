class Exporter:
    """Экспорт текста в различные форматы"""

    @staticmethod
    def to_po(results: dict, output_path: str):
        """Экспорт в PO-файл (стандарт локализации)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('# GB Text Extractor PO File\n')
            f.write('msgid ""\n')
            f.write('msgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n')

            for seg_name, messages in results.items():
                f.write(f'# {seg_name}\n')
                for msg in messages:
                    f.write(f'msgid "0x{msg["offset"]:04X}: {msg["text"]}"\n')
                    f.write('msgstr ""\n\n')

    @staticmethod
    def to_csv(results: dict, output_path: str):
        """Экспорт в CSV для удобного редактирования"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('segment,offset,original,translation\n')
            for seg_name, messages in results.items():
                for msg in messages:
                    original = msg['text'].replace('"', '""')
                    f.write(f'"{seg_name}",0x{msg["offset"]:04X},"{original}",\n')