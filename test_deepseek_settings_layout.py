#!/usr/bin/env python3
"""
DeepSeek Settings Layout Test - Проверка верстки секции DeepSeek Settings
"""

import asyncio
from playwright.async_api import async_playwright

async def test_deepseek_settings_layout():
    """Тест верстки секции DeepSeek Settings"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🧠 ТЕСТ ВЕРСТКИ DEEPSEEK SETTINGS")
        print("=" * 50)
        
        try:
            # Переходим на админ панель
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            
            print("✅ Админ панель загружена")
            
            # Кликаем на DeepSeek Settings
            print("\n🔧 Переходим в DeepSeek Settings...")
            await page.click('a[data-section="deepseek-settings"]')
            await page.wait_for_timeout(2000)
            
            # Проверяем, что секция отображается
            settings_section = await page.query_selector('#deepseek-settings-section')
            if settings_section:
                # Проверяем видимость секции
                is_visible = await page.evaluate('''
                    () => {
                        const section = document.getElementById('deepseek-settings-section');
                        if (!section) return false;
                        
                        const style = window.getComputedStyle(section);
                        return style.display !== 'none' && style.visibility !== 'hidden';
                    }
                ''')
                
                print(f"👁️ Секция видима: {'✅ ДА' if is_visible else '❌ НЕТ'}")
                
                # Проверяем позиционирование контента
                content_position = await page.evaluate('''
                    () => {
                        const section = document.getElementById('deepseek-settings-section');
                        if (!section) return null;
                        
                        const rect = section.getBoundingClientRect();
                        const style = window.getComputedStyle(section);
                        
                        return {
                            left: rect.left,
                            top: rect.top,
                            width: rect.width,
                            height: rect.height,
                            padding: style.padding,
                            margin: style.margin
                        };
                    }
                ''')
                
                print(f"📐 Позиция контента:")
                print(f"   - Left: {content_position['left']}px")
                print(f"   - Top: {content_position['top']}px") 
                print(f"   - Width: {content_position['width']}px")
                print(f"   - Padding: {content_position['padding']}")
                
                # Проверяем, не перекрывается ли контент с sidebar
                content_overlaps = content_position['left'] < 250
                print(f"🚫 Перекрытие с sidebar: {'❌ ДА' if content_overlaps else '✅ НЕТ'}")
                
                # Проверяем наличие ключевых элементов
                print(f"\n🔍 Проверка элементов формы...")
                
                api_key_field = await page.query_selector('#deepseek-api-key')
                model_field = await page.query_selector('#deepseek-model')
                travel_memory_field = await page.query_selector('#deepseek-travel-memory')
                save_button = await page.query_selector('button:has-text("Save Settings")')
                
                print(f"🔑 API Key поле: {'✅ НАЙДЕНО' if api_key_field else '❌ НЕ НАЙДЕНО'}")
                print(f"🤖 Model поле: {'✅ НАЙДЕНО' if model_field else '❌ НЕ НАЙДЕНО'}")
                print(f"🗺️ Travel Memory поле: {'✅ НАЙДЕНО' if travel_memory_field else '❌ НЕ НАЙДЕНО'}")
                print(f"💾 Save кнопка: {'✅ НАЙДЕНА' if save_button else '❌ НЕ НАЙДЕНА'}")
                
                # Проверяем видимость полей формы
                if travel_memory_field:
                    field_visible = await page.evaluate('''
                        (element) => {
                            const rect = element.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0 && rect.top >= 0;
                        }
                    ''', travel_memory_field)
                    
                    print(f"👁️ Travel Memory видимо: {'✅ ДА' if field_visible else '❌ НЕТ'}")
                
                # Проверяем правую колонку со статусом
                status_column = await page.query_selector('#deepseek-settings-section .col-md-4')
                if status_column:
                    status_visible = await page.evaluate('''
                        (element) => {
                            const rect = element.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        }
                    ''', status_column)
                    
                    print(f"📊 Колонка статуса: {'✅ ВИДИМА' if status_visible else '❌ НЕ ВИДИМА'}")
                
            else:
                print("❌ Секция DeepSeek Settings НЕ найдена!")
            
            # Делаем скриншот для визуальной проверки
            print(f"\n📸 Создаем скриншот...")
            await page.screenshot(path="deepseek_settings_layout.png", full_page=True)
            print("✅ Скриншот сохранен: deepseek_settings_layout.png")
            
            # Проверяем мобильную версию
            print(f"\n📱 Проверка мобильной версии...")
            await page.set_viewport_size({"width": 600, "height": 800})
            await page.wait_for_timeout(1000)
            
            mobile_content_position = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    return {
                        left: rect.left,
                        width: rect.width
                    };
                }
            ''')
            
            if mobile_content_position:
                mobile_ok = mobile_content_position['left'] >= 0 and mobile_content_position['width'] > 500
                print(f"📱 Мобильная верстка: {'✅ ХОРОШО' if mobile_ok else '❌ ПРОБЛЕМЫ'}")
                print(f"   - Left: {mobile_content_position['left']}px")
                print(f"   - Width: {mobile_content_position['width']}px")
            
            await page.screenshot(path="deepseek_settings_mobile.png", full_page=True)
            print("✅ Мобильный скриншот: deepseek_settings_mobile.png")
            
            # Итоговая оценка
            print(f"\n" + "=" * 50)
            print("📋 ИТОГОВАЯ ОЦЕНКА ВЕРСТКИ")
            print("=" * 50)
            
            if is_visible and not content_overlaps and api_key_field and travel_memory_field:
                print("🎉 ВЕРСТКА DEEPSEEK SETTINGS: ОТЛИЧНО!")
                print("✅ Все элементы на месте и правильно позиционированы")
            else:
                print("⚠️ ВЕРСТКА DEEPSEEK SETTINGS: ТРЕБУЕТ ДОРАБОТКИ")
                print("💡 Проверьте скриншоты для детального анализа")
            
            print(f"\n📸 СКРИНШОТЫ ДЛЯ ПРОВЕРКИ:")
            print("   - deepseek_settings_layout.png (десктоп)")
            print("   - deepseek_settings_mobile.png (мобильная)")
            
            # Ждем для визуальной проверки
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_deepseek_settings_layout())
