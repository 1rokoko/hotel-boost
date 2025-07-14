#!/usr/bin/env python3
"""
Test All Sections - Проверка всех секций админ панели
"""

import asyncio
from playwright.async_api import async_playwright

async def test_all_sections():
    """Тест всех секций админ панели"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🔄 ТЕСТ ВСЕХ СЕКЦИЙ АДМИН ПАНЕЛИ")
        print("=" * 60)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Список секций для тестирования
            sections_to_test = [
                'dashboard',
                'hotels', 
                'conversations',
                'triggers',
                'templates',
                'deepseek-settings'
            ]
            
            results = {}
            
            for section in sections_to_test:
                print(f"\n🔍 Тестируем секцию: {section}")
                
                # Кликаем на секцию
                try:
                    await page.evaluate(f'''
                        () => {{
                            const link = document.querySelector('a[data-section="{section}"]');
                            if (link) {{
                                link.click();
                            }}
                        }}
                    ''')
                    
                    await page.wait_for_timeout(1000)
                    
                    # Проверяем позиционирование секции
                    section_info = await page.evaluate(f'''
                        () => {{
                            const section = document.getElementById('{section}-section');
                            if (!section) return null;
                            
                            const rect = section.getBoundingClientRect();
                            const style = window.getComputedStyle(section);
                            
                            return {{
                                visible: style.display === 'block',
                                hasActiveClass: section.classList.contains('active'),
                                top: rect.top,
                                left: rect.left,
                                width: rect.width,
                                height: rect.height,
                                properlyPositioned: rect.left >= 250
                            }};
                        }}
                    ''')
                    
                    if section_info:
                        status = "✅ ХОРОШО" if (section_info['visible'] and 
                                                section_info['properlyPositioned'] and 
                                                section_info['height'] > 0) else "❌ ПРОБЛЕМЫ"
                        
                        print(f"   Статус: {status}")
                        print(f"   - Видимость: {'✅' if section_info['visible'] else '❌'}")
                        print(f"   - Active класс: {'✅' if section_info['hasActiveClass'] else '❌'}")
                        print(f"   - Позиция: left={section_info['left']}px, top={section_info['top']}px")
                        print(f"   - Размер: {section_info['width']}px x {section_info['height']}px")
                        print(f"   - Правильное позиционирование: {'✅' if section_info['properlyPositioned'] else '❌'}")
                        
                        results[section] = {
                            'status': 'good' if section_info['visible'] and section_info['properlyPositioned'] and section_info['height'] > 0 else 'bad',
                            'details': section_info
                        }
                    else:
                        print(f"   ❌ Секция не найдена!")
                        results[section] = {'status': 'not_found', 'details': None}
                        
                except Exception as e:
                    print(f"   ❌ Ошибка при тестировании: {e}")
                    results[section] = {'status': 'error', 'details': str(e)}
            
            # Специальная проверка DeepSeek Settings
            print(f"\n🧠 СПЕЦИАЛЬНАЯ ПРОВЕРКА DEEPSEEK SETTINGS:")
            
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) {
                        link.click();
                    }
                }
            ''')
            
            await page.wait_for_timeout(2000)
            
            # Проверяем элементы формы
            form_check = await page.evaluate('''
                () => {
                    const elements = {
                        section: document.getElementById('deepseek-settings-section'),
                        header: document.querySelector('#deepseek-settings-section .card-header h5'),
                        apiKey: document.getElementById('deepseek-api-key'),
                        model: document.getElementById('deepseek-model'),
                        saveButton: document.querySelector('#deepseek-settings-section button')
                    };
                    
                    const results = {};
                    for (const [key, element] of Object.entries(elements)) {
                        if (element) {
                            const rect = element.getBoundingClientRect();
                            results[key] = {
                                found: true,
                                visible: rect.width > 0 && rect.height > 0,
                                left: rect.left,
                                top: rect.top,
                                properlyPositioned: rect.left >= 250,
                                text: element.textContent ? element.textContent.trim().substring(0, 30) : ''
                            };
                        } else {
                            results[key] = { found: false };
                        }
                    }
                    
                    return results;
                }
            ''')
            
            print(f"📋 Элементы DeepSeek Settings:")
            for element_name, info in form_check.items():
                if info['found']:
                    status = "✅" if info['visible'] and info['properlyPositioned'] else "❌"
                    print(f"   {status} {element_name}: left={info['left']}px, top={info['top']}px")
                    if info['text']:
                        print(f"      Текст: '{info['text']}'")
                else:
                    print(f"   ❌ {element_name}: НЕ НАЙДЕН")
            
            # Скриншот для визуальной проверки
            await page.screenshot(path="all_sections_test.png", full_page=True)
            print(f"\n📸 Скриншот: all_sections_test.png")
            
            # Итоговый отчет
            print(f"\n" + "=" * 60)
            print("📊 ИТОГОВЫЙ ОТЧЕТ ПО ВСЕМ СЕКЦИЯМ")
            print("=" * 60)
            
            good_sections = [s for s, r in results.items() if r['status'] == 'good']
            bad_sections = [s for s, r in results.items() if r['status'] != 'good']
            
            print(f"✅ Работают правильно ({len(good_sections)}): {', '.join(good_sections)}")
            if bad_sections:
                print(f"❌ Есть проблемы ({len(bad_sections)}): {', '.join(bad_sections)}")
            
            if len(good_sections) == len(sections_to_test):
                print(f"\n🎉 ВСЕ СЕКЦИИ РАБОТАЮТ ПРАВИЛЬНО!")
            else:
                print(f"\n⚠️ НЕКОТОРЫЕ СЕКЦИИ ТРЕБУЮТ ДОРАБОТКИ")
            
            # Проверяем мобильную версию
            print(f"\n📱 Проверка мобильной версии...")
            await page.set_viewport_size({"width": 600, "height": 800})
            await page.wait_for_timeout(1000)
            
            mobile_check = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    return {
                        left: rect.left,
                        width: rect.width,
                        mobileOk: rect.left >= 0 && rect.width > 500
                    };
                }
            ''')
            
            if mobile_check:
                print(f"   Мобильная версия: {'✅ ХОРОШО' if mobile_check['mobileOk'] else '❌ ПРОБЛЕМЫ'}")
                print(f"   Left: {mobile_check['left']}px, Width: {mobile_check['width']}px")
            
            await page.screenshot(path="all_sections_mobile.png", full_page=True)
            print(f"📸 Мобильный скриншот: all_sections_mobile.png")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Общая ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_all_sections())
