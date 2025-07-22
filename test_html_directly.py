#!/usr/bin/env python3
"""
Тест HTML файла напрямую
"""

import asyncio
import os
from playwright.async_api import async_playwright

async def test_html_directly():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("🧪 ТЕСТ HTML ФАЙЛА НАПРЯМУЮ")
            print("=" * 50)
            
            # Получаем путь к HTML файлу
            html_path = os.path.abspath("app/templates/admin_dashboard.html")
            file_url = f"file://{html_path}"
            
            print(f"📂 Открываем файл: {file_url}")
            
            # Открываем HTML файл напрямую
            await page.goto(file_url)
            await page.wait_for_load_state('networkidle')
            print("✅ HTML файл загружен")
            
            # Ищем пункт меню AI Configuration
            ai_config_link = page.locator('a[data-section="deepseek-config"]')
            if await ai_config_link.count() > 0:
                print("✅ Пункт меню 'AI Configuration' найден")
                
                # Кликаем на AI Configuration
                await ai_config_link.click()
                await page.wait_for_timeout(1000)
                
                # Проверяем, что секция показана
                ai_section = page.locator('#deepseek-config-section')
                if await ai_section.count() > 0:
                    # Получаем стили секции
                    display = await ai_section.evaluate('el => getComputedStyle(el).display')
                    position = await ai_section.evaluate('el => getComputedStyle(el).position')
                    left = await ai_section.evaluate('el => getComputedStyle(el).left')
                    top = await ai_section.evaluate('el => getComputedStyle(el).top')
                    
                    print(f"📊 AI Configuration секция:")
                    print(f"   Display: {display}")
                    print(f"   Position: {position}")
                    print(f"   Left: {left}")
                    print(f"   Top: {top}")
                    
                    # Проверяем правильность позиционирования
                    is_visible = display == 'block'
                    is_positioned_correctly = position == 'relative' and left == '0px' and top == '0px'
                    
                    if is_visible and is_positioned_correctly:
                        print("🎉 AI Configuration работает правильно!")
                        
                        # Проверяем элементы формы
                        form_elements = {
                            'apiKey': '#ai-api-key',
                            'model': '#ai-model',
                            'maxTokens': '#ai-max-tokens',
                            'temperature': '#ai-temperature',
                            'systemPrompt': '#ai-system-prompt',
                            'saveButton': 'button[onclick="saveAIConfig()"]',
                            'testButton': 'button[onclick="testAIConnection()"]'
                        }
                        
                        print("\n📋 Проверка элементов формы:")
                        all_elements_ok = True
                        for name, selector in form_elements.items():
                            element = page.locator(selector)
                            if await element.count() > 0:
                                print(f"   {name}: ✅ ОК")
                            else:
                                print(f"   {name}: ❌ НЕ НАЙДЕН")
                                all_elements_ok = False
                        
                        if all_elements_ok:
                            print("🎉 Все элементы формы найдены!")
                            print("🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
                        else:
                            print("❌ Не все элементы формы найдены")
                    else:
                        print("❌ AI Configuration имеет проблемы с позиционированием")
                        print(f"   Видимость: {'✅' if is_visible else '❌'}")
                        print(f"   Позиционирование: {'✅' if is_positioned_correctly else '❌'}")
                        
                        # Попробуем исправить позиционирование через JavaScript
                        print("\n🔧 Попытка исправления через JavaScript...")
                        await page.evaluate("""
                            const section = document.getElementById('deepseek-config-section');
                            if (section) {
                                section.style.setProperty('position', 'relative', 'important');
                                section.style.setProperty('left', '0', 'important');
                                section.style.setProperty('top', '0', 'important');
                                section.style.setProperty('margin', '0', 'important');
                                section.style.setProperty('padding', '20px', 'important');
                                section.style.setProperty('width', '100%', 'important');
                                section.style.setProperty('box-sizing', 'border-box', 'important');
                            }
                        """)
                        
                        await page.wait_for_timeout(500)
                        
                        # Проверяем снова
                        display = await ai_section.evaluate('el => getComputedStyle(el).display')
                        position = await ai_section.evaluate('el => getComputedStyle(el).position')
                        left = await ai_section.evaluate('el => getComputedStyle(el).left')
                        top = await ai_section.evaluate('el => getComputedStyle(el).top')
                        
                        print(f"📊 После исправления:")
                        print(f"   Display: {display}")
                        print(f"   Position: {position}")
                        print(f"   Left: {left}")
                        print(f"   Top: {top}")
                        
                        is_fixed = position == 'relative' and left == '0px' and top == '0px'
                        if is_fixed:
                            print("🎉 Исправление сработало!")
                        else:
                            print("❌ Исправление не помогло")
                else:
                    print("❌ AI Configuration секция не найдена")
            else:
                print("❌ Пункт меню 'AI Configuration' не найден")
                
            # Ждем немного, чтобы можно было посмотреть результат
            print("\n⏳ Ожидание 10 секунд для просмотра...")
            await page.wait_for_timeout(10000)
                
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_html_directly())
