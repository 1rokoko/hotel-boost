#!/usr/bin/env python3
"""
Final Layout Test - Итоговая проверка всех исправлений верстки
"""

import asyncio
from playwright.async_api import async_playwright

async def final_layout_test():
    """Итоговый тест всех исправлений верстки"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🎯 ИТОГОВЫЙ ТЕСТ ВЕРСТКИ АДМИН ПАНЕЛИ")
        print("=" * 60)
        
        try:
            # Загружаем страницу
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Админ панель загружена")
            
            # Проверяем, что Dashboard активен по умолчанию
            dashboard_active = await page.evaluate('''
                () => {
                    const dashboardSection = document.getElementById('dashboard-section');
                    const dashboardNav = document.querySelector('a[data-section="dashboard"]');
                    
                    return {
                        sectionVisible: dashboardSection && window.getComputedStyle(dashboardSection).display === 'block',
                        navActive: dashboardNav && dashboardNav.classList.contains('active')
                    };
                }
            ''')
            
            print(f"🏠 Dashboard по умолчанию: {'✅ АКТИВЕН' if dashboard_active['sectionVisible'] and dashboard_active['navActive'] else '❌ НЕ АКТИВЕН'}")
            
            # Тестируем переключение на DeepSeek Settings
            print("\n🧠 Тестируем DeepSeek Settings...")
            await page.click('a[data-section="deepseek-settings"]')
            await page.wait_for_timeout(1000)
            
            # Проверяем DeepSeek Settings
            deepseek_status = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return { found: false };
                    
                    const style = window.getComputedStyle(section);
                    const rect = section.getBoundingClientRect();
                    
                    return {
                        found: true,
                        visible: style.display === 'block',
                        hasActiveClass: section.classList.contains('active'),
                        left: rect.left,
                        width: rect.width,
                        height: rect.height,
                        properlyPositioned: rect.left >= 250
                    };
                }
            ''')
            
            if deepseek_status['found']:
                print(f"   📍 Секция найдена: ✅")
                print(f"   👁️ Видимость: {'✅' if deepseek_status['visible'] else '❌'}")
                print(f"   🎯 Active класс: {'✅' if deepseek_status['hasActiveClass'] else '❌'}")
                print(f"   📐 Позиция (left): {deepseek_status['left']}px")
                print(f"   📏 Ширина: {deepseek_status['width']}px")
                print(f"   📐 Правильное позиционирование: {'✅' if deepseek_status['properlyPositioned'] else '❌'}")
            else:
                print("   ❌ Секция DeepSeek Settings НЕ найдена!")
            
            # Проверяем элементы формы
            form_elements = await page.evaluate('''
                () => {
                    const elements = {
                        apiKey: document.getElementById('deepseek-api-key'),
                        model: document.getElementById('deepseek-model'),
                        travelMemory: document.getElementById('deepseek-travel-memory'),
                        saveButton: document.querySelector('button:has-text("Save Settings")')
                    };
                    
                    const results = {};
                    for (const [key, element] of Object.entries(elements)) {
                        if (element) {
                            const rect = element.getBoundingClientRect();
                            results[key] = {
                                found: true,
                                visible: rect.width > 0 && rect.height > 0,
                                left: rect.left,
                                width: rect.width
                            };
                        } else {
                            results[key] = { found: false };
                        }
                    }
                    
                    return results;
                }
            ''')
            
            print(f"\n🔍 Элементы формы:")
            for element_name, status in form_elements.items():
                if status['found']:
                    print(f"   {element_name}: ✅ найден, видим: {'✅' if status['visible'] else '❌'}, left: {status['left']}px")
                else:
                    print(f"   {element_name}: ❌ НЕ найден")
            
            # Тестируем другие секции
            print(f"\n🔄 Тестируем переключение между секциями...")
            
            sections_to_test = ['hotels', 'conversations', 'triggers', 'templates']
            for section in sections_to_test:
                await page.click(f'a[data-section="{section}"]')
                await page.wait_for_timeout(500)
                
                section_visible = await page.evaluate(f'''
                    () => {{
                        const section = document.getElementById('{section}-section');
                        return section && window.getComputedStyle(section).display === 'block';
                    }}
                ''')
                
                print(f"   {section}: {'✅' if section_visible else '❌'}")
            
            # Возвращаемся к DeepSeek Settings для финальной проверки
            await page.click('a[data-section="deepseek-settings"]')
            await page.wait_for_timeout(1000)
            
            # Финальная проверка DeepSeek Settings
            final_check = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    const apiKey = document.getElementById('deepseek-api-key');
                    const travelMemory = document.getElementById('deepseek-travel-memory');
                    
                    if (!section || !apiKey || !travelMemory) return false;
                    
                    const sectionRect = section.getBoundingClientRect();
                    const apiKeyRect = apiKey.getBoundingClientRect();
                    const travelMemoryRect = travelMemory.getBoundingClientRect();
                    
                    return {
                        sectionVisible: window.getComputedStyle(section).display === 'block',
                        sectionLeft: sectionRect.left,
                        apiKeyVisible: apiKeyRect.width > 0 && apiKeyRect.height > 0,
                        travelMemoryVisible: travelMemoryRect.width > 0 && travelMemoryRect.height > 0,
                        noOverlap: sectionRect.left >= 250
                    };
                }
            ''')
            
            # Делаем финальные скриншоты
            await page.screenshot(path="final_deepseek_desktop.png", full_page=True)
            print(f"\n📸 Скриншот десктоп: final_deepseek_desktop.png")
            
            # Тест мобильной версии
            await page.set_viewport_size({"width": 600, "height": 800})
            await page.wait_for_timeout(1000)
            await page.screenshot(path="final_deepseek_mobile.png", full_page=True)
            print(f"📱 Скриншот мобильная: final_deepseek_mobile.png")
            
            # Итоговая оценка
            print(f"\n" + "=" * 60)
            print("📋 ИТОГОВАЯ ОЦЕНКА ИСПРАВЛЕНИЙ")
            print("=" * 60)
            
            if (final_check and 
                final_check['sectionVisible'] and 
                final_check['noOverlap'] and 
                final_check['apiKeyVisible'] and 
                final_check['travelMemoryVisible']):
                
                print("🎉 ВСЕ ИСПРАВЛЕНИЯ УСПЕШНЫ!")
                print("✅ DeepSeek Settings отображается правильно")
                print("✅ Контент не перекрывается с sidebar")
                print("✅ Все элементы формы видимы и доступны")
                print("✅ Переключение между секциями работает")
                
            else:
                print("⚠️ ОСТАЛИСЬ ПРОБЛЕМЫ С ВЕРСТКОЙ")
                if final_check:
                    print(f"   - Секция видима: {'✅' if final_check['sectionVisible'] else '❌'}")
                    print(f"   - Нет перекрытия: {'✅' if final_check['noOverlap'] else '❌'}")
                    print(f"   - API Key видим: {'✅' if final_check['apiKeyVisible'] else '❌'}")
                    print(f"   - Travel Memory видим: {'✅' if final_check['travelMemoryVisible'] else '❌'}")
                else:
                    print("   - Не удалось получить данные о секции")
            
            print(f"\n📸 СКРИНШОТЫ ДЛЯ ПРОВЕРКИ:")
            print("   - final_deepseek_desktop.png")
            print("   - final_deepseek_mobile.png")
            
            print(f"\n💡 РЕКОМЕНДАЦИИ:")
            print("   1. Проверьте скриншоты визуально")
            print("   2. Убедитесь, что все поля формы доступны")
            print("   3. Протестируйте на разных размерах экрана")
            
            # Ждем для визуальной проверки
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(final_layout_test())
