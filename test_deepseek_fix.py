#!/usr/bin/env python3
"""
DeepSeek Settings Fix Test - Проверка исправлений белого пространства и перекрытия
"""

import asyncio
from playwright.async_api import async_playwright

async def test_deepseek_fix():
    """Тест исправлений DeepSeek Settings"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🔧 ТЕСТ ИСПРАВЛЕНИЙ DEEPSEEK SETTINGS")
        print("=" * 50)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Переходим в DeepSeek Settings через JavaScript
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) {
                        link.click();
                    }
                }
            ''')
            
            await page.wait_for_timeout(2000)
            print("✅ Перешли в DeepSeek Settings")
            
            # Проверяем позиционирование секции
            section_info = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        display: style.display,
                        top: rect.top,
                        left: rect.left,
                        width: rect.width,
                        height: rect.height,
                        paddingTop: style.paddingTop,
                        marginTop: style.marginTop
                    };
                }
            ''')
            
            if section_info:
                print(f"\n📐 Позиционирование секции:")
                print(f"   - Display: {section_info['display']}")
                print(f"   - Top: {section_info['top']}px")
                print(f"   - Left: {section_info['left']}px")
                print(f"   - Width: {section_info['width']}px")
                print(f"   - Height: {section_info['height']}px")
                print(f"   - Padding Top: {section_info['paddingTop']}")
                print(f"   - Margin Top: {section_info['marginTop']}")
                
                # Проверяем проблемы
                has_white_space = section_info['top'] > 100
                overlaps_sidebar = section_info['left'] < 250
                
                print(f"\n🔍 Анализ проблем:")
                print(f"   - Большое белое пространство: {'❌ ДА' if has_white_space else '✅ НЕТ'}")
                print(f"   - Перекрытие с sidebar: {'❌ ДА' if overlaps_sidebar else '✅ НЕТ'}")
            
            # Проверяем заголовок карточки
            card_header_info = await page.evaluate('''
                () => {
                    const header = document.querySelector('#deepseek-settings-section .card-header h5');
                    if (!header) return null;
                    
                    const rect = header.getBoundingClientRect();
                    return {
                        text: header.textContent.trim(),
                        top: rect.top,
                        left: rect.left,
                        width: rect.width,
                        visible: rect.width > 0 && rect.height > 0
                    };
                }
            ''')
            
            if card_header_info:
                print(f"\n📋 Заголовок карточки:")
                print(f"   - Текст: '{card_header_info['text']}'")
                print(f"   - Top: {card_header_info['top']}px")
                print(f"   - Left: {card_header_info['left']}px")
                print(f"   - Видимость: {'✅ ВИДИМ' if card_header_info['visible'] else '❌ НЕ ВИДИМ'}")
                
                header_overlaps = card_header_info['left'] < 250
                print(f"   - Перекрытие с sidebar: {'❌ ДА' if header_overlaps else '✅ НЕТ'}")
            
            # Проверяем поля формы
            form_fields = await page.evaluate('''
                () => {
                    const fields = [
                        { id: 'deepseek-api-key', name: 'API Key' },
                        { id: 'deepseek-model', name: 'Model' },
                        { id: 'deepseek-max-tokens', name: 'Max Tokens' },
                        { id: 'deepseek-temperature', name: 'Temperature' }
                    ];
                    
                    return fields.map(field => {
                        const element = document.getElementById(field.id);
                        if (!element) return { ...field, found: false };
                        
                        const rect = element.getBoundingClientRect();
                        return {
                            ...field,
                            found: true,
                            top: rect.top,
                            left: rect.left,
                            visible: rect.width > 0 && rect.height > 0,
                            accessible: rect.left >= 250
                        };
                    });
                }
            ''')
            
            print(f"\n🔍 Поля формы:")
            for field in form_fields:
                if field['found']:
                    status = "✅" if field['visible'] and field['accessible'] else "❌"
                    print(f"   {status} {field['name']}: top={field['top']}px, left={field['left']}px")
                else:
                    print(f"   ❌ {field['name']}: НЕ НАЙДЕНО")
            
            # Проверяем прокрутку страницы
            scroll_info = await page.evaluate('''
                () => {
                    return {
                        scrollTop: window.pageYOffset || document.documentElement.scrollTop,
                        scrollHeight: document.documentElement.scrollHeight,
                        clientHeight: document.documentElement.clientHeight
                    };
                }
            ''')
            
            print(f"\n📜 Прокрутка страницы:")
            print(f"   - Scroll Top: {scroll_info['scrollTop']}px")
            print(f"   - Scroll Height: {scroll_info['scrollHeight']}px")
            print(f"   - Client Height: {scroll_info['clientHeight']}px")
            
            # Скриншот для визуальной проверки
            await page.screenshot(path="deepseek_fix_test.png", full_page=True)
            print(f"\n📸 Скриншот: deepseek_fix_test.png")
            
            # Прокручиваем вверх, чтобы убедиться, что контент начинается сверху
            await page.evaluate('window.scrollTo(0, 0)')
            await page.wait_for_timeout(1000)
            
            # Проверяем позицию после прокрутки вверх
            top_position = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    return rect.top;
                }
            ''')
            
            print(f"\n⬆️ После прокрутки вверх:")
            print(f"   - Top позиция секции: {top_position}px")
            
            # Скриншот после прокрутки
            await page.screenshot(path="deepseek_fix_scrolled.png", full_page=True)
            print(f"📸 Скриншот после прокрутки: deepseek_fix_scrolled.png")
            
            # Итоговая оценка
            print(f"\n" + "=" * 50)
            print("📋 ИТОГОВАЯ ОЦЕНКА ИСПРАВЛЕНИЙ")
            print("=" * 50)
            
            if (section_info and 
                not (section_info['top'] > 100) and 
                section_info['left'] >= 250 and 
                card_header_info and 
                card_header_info['left'] >= 250):
                
                print("🎉 ИСПРАВЛЕНИЯ УСПЕШНЫ!")
                print("✅ Белое пространство устранено")
                print("✅ Перекрытие с sidebar исправлено")
                print("✅ Контент правильно позиционирован")
            else:
                print("⚠️ ОСТАЛИСЬ ПРОБЛЕМЫ:")
                if section_info and section_info['top'] > 100:
                    print("   ❌ Все еще есть большое белое пространство")
                if section_info and section_info['left'] < 250:
                    print("   ❌ Секция все еще перекрывается с sidebar")
                if card_header_info and card_header_info['left'] < 250:
                    print("   ❌ Заголовок все еще перекрывается с sidebar")
            
            print(f"\n📸 СКРИНШОТЫ ДЛЯ АНАЛИЗА:")
            print("   - deepseek_fix_test.png (общий вид)")
            print("   - deepseek_fix_scrolled.png (после прокрутки вверх)")
            
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_deepseek_fix())
