#!/usr/bin/env python3
"""
Final Fix Test - Финальная проверка исправлений
"""

import asyncio
from playwright.async_api import async_playwright

async def final_test():
    """Финальная проверка всех исправлений"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🎯 ФИНАЛЬНАЯ ПРОВЕРКА ИСПРАВЛЕНИЙ")
        print("=" * 50)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Проверяем Dashboard по умолчанию
            dashboard_check = await page.evaluate('''
                () => {
                    const section = document.getElementById('dashboard-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        display: style.display,
                        left: rect.left,
                        width: rect.width,
                        properlyPositioned: rect.left >= 250 || style.display === 'none'
                    };
                }
            ''')
            
            if dashboard_check:
                print(f"🏠 Dashboard: {'✅ ОК' if dashboard_check['properlyPositioned'] else '❌ ПРОБЛЕМА'}")
                print(f"   Display: {dashboard_check['display']}, Left: {dashboard_check['left']}px")
            
            # Переходим в DeepSeek Settings
            print(f"\n🧠 Переходим в DeepSeek Settings...")
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(2000)
            
            # Детальная проверка DeepSeek Settings
            deepseek_analysis = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    // Проверяем ключевые элементы
                    const header = document.querySelector('#deepseek-settings-section .card-header h5');
                    const apiKey = document.getElementById('deepseek-api-key');
                    
                    const headerRect = header ? header.getBoundingClientRect() : null;
                    const apiKeyRect = apiKey ? apiKey.getBoundingClientRect() : null;
                    
                    return {
                        section: {
                            display: style.display,
                            left: rect.left,
                            top: rect.top,
                            width: rect.width,
                            height: rect.height,
                            properlyPositioned: rect.left >= 250
                        },
                        header: headerRect ? {
                            text: header.textContent.trim(),
                            left: headerRect.left,
                            top: headerRect.top,
                            properlyPositioned: headerRect.left >= 250
                        } : null,
                        apiKey: apiKeyRect ? {
                            left: apiKeyRect.left,
                            top: apiKeyRect.top,
                            properlyPositioned: apiKeyRect.left >= 250
                        } : null
                    };
                }
            ''')
            
            if deepseek_analysis:
                section = deepseek_analysis['section']
                print(f"📊 DeepSeek Settings секция:")
                print(f"   Display: {section['display']}")
                print(f"   Позиция: left={section['left']}px, top={section['top']}px")
                print(f"   Размер: {section['width']}px x {section['height']}px")
                print(f"   Правильное позиционирование: {'✅' if section['properlyPositioned'] else '❌'}")
                
                if deepseek_analysis['header']:
                    header = deepseek_analysis['header']
                    print(f"\n📋 Заголовок '{header['text']}':")
                    print(f"   Позиция: left={header['left']}px, top={header['top']}px")
                    print(f"   Правильное позиционирование: {'✅' if header['properlyPositioned'] else '❌'}")
                
                if deepseek_analysis['apiKey']:
                    apiKey = deepseek_analysis['apiKey']
                    print(f"\n🔑 API Key поле:")
                    print(f"   Позиция: left={apiKey['left']}px, top={apiKey['top']}px")
                    print(f"   Правильное позиционирование: {'✅' if apiKey['properlyPositioned'] else '❌'}")
                
                # Проверяем основные проблемы
                no_white_space = section['top'] < 200
                no_sidebar_overlap = section['properlyPositioned']
                header_visible = deepseek_analysis['header'] and deepseek_analysis['header']['properlyPositioned']
                
                print(f"\n🔍 Анализ проблем:")
                print(f"   - Белое пространство устранено: {'✅' if no_white_space else '❌'}")
                print(f"   - Нет перекрытия с sidebar: {'✅' if no_sidebar_overlap else '❌'}")
                print(f"   - Заголовок видим полностью: {'✅' if header_visible else '❌'}")
                
                # Итоговая оценка
                all_good = no_white_space and no_sidebar_overlap and header_visible
                print(f"\n🎯 ИТОГОВАЯ ОЦЕНКА: {'🎉 ВСЕ ИСПРАВЛЕНО!' if all_good else '⚠️ ОСТАЛИСЬ ПРОБЛЕМЫ'}")
            
            # Проверяем другие секции
            print(f"\n🔄 Быстрая проверка других секций...")
            other_sections = ['hotels', 'conversations', 'triggers']
            
            for section_name in other_sections:
                await page.evaluate(f'''
                    () => {{
                        const link = document.querySelector('a[data-section="{section_name}"]');
                        if (link) link.click();
                    }}
                ''')
                await page.wait_for_timeout(500)
                
                section_ok = await page.evaluate(f'''
                    () => {{
                        const section = document.getElementById('{section_name}-section');
                        if (!section) return false;
                        
                        const rect = section.getBoundingClientRect();
                        const style = window.getComputedStyle(section);
                        
                        return style.display === 'block' && rect.left >= 250;
                    }}
                ''')
                
                print(f"   {section_name}: {'✅ ОК' if section_ok else '❌ ПРОБЛЕМА'}")
            
            # Скриншоты
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(1000)
            
            await page.screenshot(path="final_fix_desktop.png", full_page=True)
            print(f"\n📸 Скриншот десктоп: final_fix_desktop.png")
            
            # Мобильная версия
            await page.set_viewport_size({"width": 600, "height": 800})
            await page.wait_for_timeout(1000)
            await page.screenshot(path="final_fix_mobile.png", full_page=True)
            print(f"📱 Скриншот мобильная: final_fix_mobile.png")
            
            print(f"\n📸 СКРИНШОТЫ ДЛЯ ПРОВЕРКИ:")
            print("   - final_fix_desktop.png")
            print("   - final_fix_mobile.png")
            
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(final_test())
