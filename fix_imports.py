#!/usr/bin/env python3
"""
Скрипт для исправления неправильных импортов после замены JSONB
"""

import os
import re

def fix_imports_in_file(file_path):
    """Исправляет неправильные импорты в файле"""
    print(f"Проверяем файл: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Исправляем пустые импорты postgresql
    content = re.sub(
        r'from sqlalchemy\.dialects\.postgresql import\s*\n',
        'from sqlalchemy.dialects.postgresql import UUID\n',
        content
    )
    
    # Исправляем импорты, где остались только запятые
    content = re.sub(
        r'from sqlalchemy\.dialects\.postgresql import\s*,\s*([A-Z_]+)',
        r'from sqlalchemy.dialects.postgresql import \1',
        content
    )
    
    # Исправляем импорты, где UUID в конце с запятой
    content = re.sub(
        r'from sqlalchemy\.dialects\.postgresql import\s*([A-Z_]+),\s*\n',
        r'from sqlalchemy.dialects.postgresql import \1\n',
        content
    )
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ Файл исправлен")
        return True
    else:
        print(f"  ⏭️ Изменений не требуется")
        return False

def main():
    """Основная функция"""
    print("🔧 ИСПРАВЛЕНИЕ ИМПОРТОВ")
    print("=" * 30)
    
    models_dir = "app/models"
    files_updated = 0
    
    for filename in os.listdir(models_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            file_path = os.path.join(models_dir, filename)
            if fix_imports_in_file(file_path):
                files_updated += 1
    
    print(f"\n🎉 Обработка завершена!")
    print(f"📊 Исправлено файлов: {files_updated}")

if __name__ == "__main__":
    main()
