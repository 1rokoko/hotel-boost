#!/usr/bin/env python3
"""
Тест исправления AI Configuration верстки
"""

import asyncio
from playwright.async_api import async_playwright

async def test_ai_configuration():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("🧪 ТЕСТ ИСПРАВЛЕНИЯ AI CONFIGURATION")
            print("=" * 50)
            
            # Открываем админ панель
            await page.goto("http://localhost:8000/admin")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
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
                            
                            # Тестируем функционал
                            print("\n🧪 Тест функционала:")
                            
                            # Заполняем форму
                            await page.fill('#ai-api-key', 'test-api-key')
                            await page.select_option('#ai-model', 'deepseek-chat')
                            await page.fill('#ai-max-tokens', '1500')
                            await page.fill('#ai-system-prompt', 'Test system prompt')
                            
                            # Кликаем Save
                            await page.click('button[onclick="saveAIConfig()"]')
                            await page.wait_for_timeout(1000)
                            
                            # Проверяем, что появилось сообщение об успехе
                            success_alert = page.locator('.alert-success')
                            if await success_alert.count() > 0:
                                print("✅ Сохранение работает - показано сообщение об успехе")
                            else:
                                print("⚠️ Сообщение об успехе не найдено")
                            
                            print("🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
                            
                        else:
                            print("❌ Не все элементы формы найдены")
                    else:
                        print("❌ AI Configuration имеет проблемы с позиционированием")
                        print(f"   Видимость: {'✅' if is_visible else '❌'}")
                        print(f"   Позиционирование: {'✅' if is_positioned_correctly else '❌'}")
                else:
                    print("❌ AI Configuration секция не найдена")
            else:
                print("❌ Пункт меню 'AI Configuration' не найден")
                
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_ai_configuration())
