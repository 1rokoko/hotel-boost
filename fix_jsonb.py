#!/usr/bin/env python3
"""
Скрипт для замены JSONB на JSON во всех файлах моделей
"""

import os
import re

def fix_jsonb_in_file(file_path):
    """Исправляет JSONB на JSON в файле"""
    print(f"Обрабатываем файл: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Заменяем импорт JSONB на JSON
    content = re.sub(
        r'from sqlalchemy\.dialects\.postgresql import (.*)JSONB(.*)',
        lambda m: f'from sqlalchemy.dialects.postgresql import {m.group(1).replace("JSONB, ", "").replace(", JSONB", "")}{m.group(2)}\nfrom sqlalchemy import JSON',
        content
    )
    
    # Заменяем использование JSONB на JSON
    content = re.sub(r'\bJSONB\b', 'JSON', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ Файл обновлен")
        return True
    else:
        print(f"  ⏭️ Изменений не требуется")
        return False

def main():
    """Основная функция"""
    print("🔧 ИСПРАВЛЕНИЕ JSONB -> JSON")
    print("=" * 40)
    
    models_dir = "app/models"
    files_updated = 0
    
    for filename in os.listdir(models_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            file_path = os.path.join(models_dir, filename)
            if fix_jsonb_in_file(file_path):
                files_updated += 1
    
    print(f"\n🎉 Обработка завершена!")
    print(f"📊 Обновлено файлов: {files_updated}")

if __name__ == "__main__":
    main()
