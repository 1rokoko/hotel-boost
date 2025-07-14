#!/usr/bin/env python3
"""
Simple DeepSeek Settings Test
"""

import asyncio
from playwright.async_api import async_playwright

async def simple_test():
    """Простой тест DeepSeek Settings"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🧠 ПРОСТОЙ ТЕСТ DEEPSEEK SETTINGS")
        print("=" * 40)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Кликаем на DeepSeek Settings
            await page.click('a[data-section="deepseek-settings"]')
            await page.wait_for_timeout(2000)
            print("✅ Кликнули на DeepSeek Settings")
            
            # Проверяем видимость секции
            section_visible = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return false;
                    
                    const style = window.getComputedStyle(section);
                    const rect = section.getBoundingClientRect();
                    
                    return {
                        display: style.display,
                        visibility: style.visibility,
                        width: rect.width,
                        height: rect.height,
                        left: rect.left
                    };
                }
            ''')
            
            print(f"📊 Статус секции:")
            print(f"   - Display: {section_visible['display']}")
            print(f"   - Visibility: {section_visible['visibility']}")
            print(f"   - Width: {section_visible['width']}px")
            print(f"   - Height: {section_visible['height']}px")
            print(f"   - Left: {section_visible['left']}px")
            
            # Проверяем поля формы
            fields_found = await page.evaluate('''
                () => {
                    return {
                        apiKey: !!document.getElementById('deepseek-api-key'),
                        model: !!document.getElementById('deepseek-model'),
                        travelMemory: !!document.getElementById('deepseek-travel-memory'),
                        saveButton: !!document.querySelector('button:has-text("Save Settings")')
                    };
                }
            ''')
            
            print(f"🔍 Поля формы:")
            print(f"   - API Key: {'✅' if fields_found['apiKey'] else '❌'}")
            print(f"   - Model: {'✅' if fields_found['model'] else '❌'}")
            print(f"   - Travel Memory: {'✅' if fields_found['travelMemory'] else '❌'}")
            print(f"   - Save Button: {'✅' if fields_found['saveButton'] else '❌'}")
            
            # Скриншот
            await page.screenshot(path="simple_deepseek_test.png", full_page=True)
            print("📸 Скриншот: simple_deepseek_test.png")
            
            # Итог
            if (section_visible['display'] == 'block' and 
                section_visible['left'] >= 250 and 
                fields_found['apiKey'] and 
                fields_found['travelMemory']):
                print("\n🎉 ТЕСТ ПРОЙДЕН! DeepSeek Settings работает правильно!")
            else:
                print("\n⚠️ ТЕСТ НЕ ПРОЙДЕН. Есть проблемы с отображением.")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(simple_test())
