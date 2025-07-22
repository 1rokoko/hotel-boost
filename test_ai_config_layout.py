#!/usr/bin/env python3
"""
Тест верстки AI Configuration без сервера
"""

import asyncio
import os
from playwright.async_api import async_playwright

async def test_ai_config_layout():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("🎨 ТЕСТ ВЕРСТКИ AI CONFIGURATION")
            print("=" * 40)
            
            # Получаем абсолютный путь к HTML файлу
            current_dir = os.getcwd()
            html_path = os.path.join(current_dir, "app", "templates", "admin_dashboard.html")
            file_url = f"file:///{html_path.replace(os.sep, '/')}"
            
            print(f"📂 Открываем файл: {file_url}")
            
            # Открываем HTML файл напрямую
            await page.goto(file_url)
            await page.wait_for_load_state('networkidle')
            print("✅ HTML файл загружен")
            
            # Проверяем, что CSS загрузился
            css_loaded = await page.evaluate("""
                () => {
                    const links = document.querySelectorAll('link[rel="stylesheet"]');
                    return links.length > 0;
                }
            """)
            
            if css_loaded:
                print("✅ CSS файлы найдены в HTML")
            else:
                print("⚠️ CSS файлы не найдены")
            
            # Ищем пункт меню AI Configuration
            ai_config_link = page.locator('a[data-section="deepseek-config"]')
            if await ai_config_link.count() > 0:
                print("✅ Пункт меню 'AI Configuration' найден")
                
                # Кликаем на AI Configuration
                await ai_config_link.click()
                await page.wait_for_timeout(1000)
                
                # Проверяем секцию AI Configuration
                ai_section = page.locator('#deepseek-config-section')
                if await ai_section.count() > 0:
                    print("✅ AI Configuration секция найдена")
                    
                    # Получаем стили секции
                    styles = await ai_section.evaluate("""
                        el => {
                            const computed = getComputedStyle(el);
                            return {
                                display: computed.display,
                                position: computed.position,
                                left: computed.left,
                                top: computed.top,
                                transform: computed.transform
                            };
                        }
                    """)
                    
                    print(f"📊 Стили AI Configuration секции:")
                    print(f"   Display: {styles['display']}")
                    print(f"   Position: {styles['position']}")
                    print(f"   Left: {styles['left']}")
                    print(f"   Top: {styles['top']}")
                    print(f"   Transform: {styles['transform']}")
                    
                    # Проверяем правильность позиционирования
                    is_visible = styles['display'] == 'block'
                    is_positioned_correctly = (
                        styles['position'] == 'relative' and 
                        styles['left'] == '0px' and 
                        styles['top'] == '0px'
                    )
                    
                    print(f"\n🔍 Анализ позиционирования:")
                    print(f"   Видимость: {'✅ ОК' if is_visible else '❌ НЕ ОК'}")
                    print(f"   Позиционирование: {'✅ ОК' if is_positioned_correctly else '❌ НЕ ОК'}")
                    
                    if is_visible and is_positioned_correctly:
                        print("\n🎉 ВЕРСТКА ИСПРАВЛЕНА УСПЕШНО!")
                        print("✅ AI Configuration отображается правильно")
                        print("✅ Нет смещения влево")
                    else:
                        print("\n❌ ВЕРСТКА ТРЕБУЕТ ДОПОЛНИТЕЛЬНЫХ ИСПРАВЛЕНИЙ")
                        
                        if not is_visible:
                            print("   - Секция не видна")
                        if not is_positioned_correctly:
                            print("   - Неправильное позиционирование")
                else:
                    print("❌ AI Configuration секция не найдена")
            else:
                print("❌ Пункт меню 'AI Configuration' не найден")
                
            # Ждем для просмотра результата
            print("\n⏳ Ожидание 10 секунд для просмотра...")
            await page.wait_for_timeout(10000)
                
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_ai_config_layout())
