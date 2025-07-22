#!/usr/bin/env python3
"""
Test New Sections - Проверка новой AI Configuration и восстановленных триггеров
"""

import asyncio
from playwright.async_api import async_playwright

async def test_new_sections():
    """Тест новой AI Configuration секции и функционала триггеров"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🧪 ТЕСТ НОВЫХ СЕКЦИЙ И ФУНКЦИОНАЛА")
        print("=" * 60)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # ЗАДАЧА 1: Тест новой AI Configuration секции
            print("\n🧠 ЗАДАЧА 1: ТЕСТ AI CONFIGURATION")
            print("-" * 40)
            
            # Проверяем, что новый пункт меню есть
            ai_config_link = await page.query_selector('a[data-section="deepseek-config"]')
            if ai_config_link:
                print("✅ Новый пункт меню 'AI Configuration' найден")
                
                # Кликаем на новый пункт меню
                await ai_config_link.click()
                await page.wait_for_timeout(1000)
                
                # Проверяем позиционирование новой секции
                ai_config_info = await page.evaluate('''
                    () => {
                        const section = document.getElementById('deepseek-config-section');
                        if (!section) return null;
                        
                        const rect = section.getBoundingClientRect();
                        const style = window.getComputedStyle(section);
                        
                        return {
                            display: style.display,
                            left: rect.left,
                            top: rect.top,
                            width: rect.width,
                            height: rect.height,
                            properlyPositioned: rect.left >= 250,
                            noWhiteSpace: rect.top < 200
                        };
                    }
                ''')
                
                if ai_config_info:
                    print(f"📊 AI Configuration секция:")
                    print(f"   Display: {ai_config_info['display']}")
                    print(f"   Left: {ai_config_info['left']}px")
                    print(f"   Top: {ai_config_info['top']}px")
                    print(f"   Правильно позиционирована: {'✅' if ai_config_info['properlyPositioned'] else '❌'}")
                    print(f"   Нет белого пространства: {'✅' if ai_config_info['noWhiteSpace'] else '❌'}")
                    
                    if ai_config_info['properlyPositioned'] and ai_config_info['noWhiteSpace']:
                        print("🎉 AI Configuration работает ИДЕАЛЬНО!")
                    else:
                        print("❌ AI Configuration имеет проблемы с позиционированием")
                
                # Проверяем элементы формы
                form_elements = await page.evaluate('''
                    () => {
                        const elements = {
                            apiKey: document.getElementById('ai-api-key'),
                            model: document.getElementById('ai-model'),
                            maxTokens: document.getElementById('ai-max-tokens'),
                            temperature: document.getElementById('ai-temperature'),
                            systemPrompt: document.getElementById('ai-system-prompt'),
                            saveButton: document.querySelector('button[onclick="saveAIConfig()"]'),
                            testButton: document.querySelector('button[onclick="testAIConnection()"]')
                        };
                        
                        const results = {};
                        for (const [key, element] of Object.entries(elements)) {
                            results[key] = {
                                found: !!element,
                                visible: element ? element.offsetWidth > 0 && element.offsetHeight > 0 : false
                            };
                        }
                        
                        return results;
                    }
                ''')
                
                print(f"\n📋 Элементы формы AI Configuration:")
                all_elements_ok = True
                for element_name, info in form_elements.items():
                    status = "✅ ОК" if info['found'] and info['visible'] else "❌ ПРОБЛЕМА"
                    print(f"   {element_name}: {status}")
                    if not (info['found'] and info['visible']):
                        all_elements_ok = False
                
                if all_elements_ok:
                    print("🎉 Все элементы формы работают правильно!")
                
                # Тест функционала
                print(f"\n🧪 Тест функционала AI Configuration:")
                
                # Заполняем форму
                await page.fill('#ai-api-key', 'test-api-key-12345')
                await page.select_option('#ai-model', 'deepseek-chat')
                await page.fill('#ai-max-tokens', '1500')
                await page.fill('#test-message', 'Hello, I need help with my booking')
                
                # Тестируем AI Response
                await page.click('button[onclick="testAIResponse()"]')
                await page.wait_for_timeout(2000)
                
                ai_response = await page.text_content('#ai-response-output')
                if 'AI Assistant:' in ai_response:
                    print("✅ AI Response тест работает")
                else:
                    print("❌ AI Response тест не работает")
                
            else:
                print("❌ Новый пункт меню 'AI Configuration' НЕ найден")
            
            # ЗАДАЧА 2: Тест функционала триггеров
            print("\n⚡ ЗАДАЧА 2: ТЕСТ ФУНКЦИОНАЛА ТРИГГЕРОВ")
            print("-" * 40)
            
            # Переходим в секцию триггеров
            triggers_link = await page.query_selector('a[data-section="triggers"]')
            if triggers_link:
                print("✅ Пункт меню 'Triggers' найден")
                
                await triggers_link.click()
                await page.wait_for_timeout(2000)
                
                # Проверяем позиционирование секции триггеров
                triggers_info = await page.evaluate('''
                    () => {
                        const section = document.getElementById('triggers-section');
                        if (!section) return null;
                        
                        const rect = section.getBoundingClientRect();
                        const style = window.getComputedStyle(section);
                        
                        return {
                            display: style.display,
                            left: rect.left,
                            properlyPositioned: rect.left >= 250
                        };
                    }
                ''')
                
                if triggers_info:
                    print(f"📊 Triggers секция:")
                    print(f"   Display: {triggers_info['display']}")
                    print(f"   Left: {triggers_info['left']}px")
                    print(f"   Правильно позиционирована: {'✅' if triggers_info['properlyPositioned'] else '❌'}")
                
                # Проверяем элементы управления триггерами
                trigger_elements = await page.evaluate('''
                    () => {
                        const elements = {
                            createButton: document.querySelector('button[onclick="showCreateTriggerModal()"]'),
                            triggersList: document.getElementById('triggers-list'),
                            typeFilter: document.getElementById('trigger-type-filter')
                        };
                        
                        const results = {};
                        for (const [key, element] of Object.entries(elements)) {
                            results[key] = {
                                found: !!element,
                                visible: element ? element.offsetWidth > 0 && element.offsetHeight > 0 : false
                            };
                        }
                        
                        return results;
                    }
                ''')
                
                print(f"\n📋 Элементы управления триггерами:")
                triggers_elements_ok = True
                for element_name, info in trigger_elements.items():
                    status = "✅ ОК" if info['found'] and info['visible'] else "❌ ПРОБЛЕМА"
                    print(f"   {element_name}: {status}")
                    if not (info['found'] and info['visible']):
                        triggers_elements_ok = False
                
                # Тест создания триггера
                create_button = await page.query_selector('button[onclick="showCreateTriggerModal()"]')
                if create_button:
                    print(f"\n🧪 Тест создания триггера:")
                    await create_button.click()
                    await page.wait_for_timeout(1000)
                    
                    # Проверяем, что модальное окно открылось
                    modal = await page.query_selector('#createTriggerModal')
                    if modal:
                        print("✅ Модальное окно создания триггера открылось")
                        
                        # Закрываем модальное окно
                        close_button = await page.query_selector('#createTriggerModal .btn-close')
                        if close_button:
                            await close_button.click()
                            await page.wait_for_timeout(500)
                    else:
                        print("❌ Модальное окно создания триггера НЕ открылось")
                
                if triggers_elements_ok:
                    print("🎉 Функционал триггеров восстановлен и работает!")
                else:
                    print("⚠️ Функционал триггеров требует доработки")
                    
            else:
                print("❌ Пункт меню 'Triggers' НЕ найден")
            
            # ИТОГОВАЯ ОЦЕНКА
            print(f"\n" + "=" * 60)
            print("🏆 ИТОГОВАЯ ОЦЕНКА")
            print("=" * 60)
            
            # Проверяем обе задачи
            task1_success = ai_config_info and ai_config_info['properlyPositioned'] and ai_config_info['noWhiteSpace']
            task2_success = triggers_info and triggers_info['properlyPositioned'] and triggers_elements_ok
            
            print(f"📋 Задача 1 (AI Configuration): {'🎉 ВЫПОЛНЕНА' if task1_success else '❌ ТРЕБУЕТ ДОРАБОТКИ'}")
            print(f"📋 Задача 2 (Функционал триггеров): {'🎉 ВЫПОЛНЕНА' if task2_success else '❌ ТРЕБУЕТ ДОРАБОТКИ'}")
            
            if task1_success and task2_success:
                print(f"\n🎉🎉🎉 ОБЕ ЗАДАЧИ ВЫПОЛНЕНЫ УСПЕШНО! 🎉🎉🎉")
                print("✅ AI Configuration работает с правильной версткой")
                print("✅ Функционал триггеров восстановлен и работает")
            else:
                print(f"\n⚠️ НЕКОТОРЫЕ ЗАДАЧИ ТРЕБУЮТ ДОРАБОТКИ")
            
            # Скриншот для документации
            await page.screenshot(path="new_sections_test.png", full_page=True)
            print(f"\n📸 Скриншот результата: new_sections_test.png")
            
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_new_sections())
