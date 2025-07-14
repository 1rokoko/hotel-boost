#!/usr/bin/env python3
"""
Navigation Test - Проверка доступности навигации
"""

import asyncio
from playwright.async_api import async_playwright

async def test_navigation():
    """Тест навигации в sidebar"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🧭 ТЕСТ НАВИГАЦИИ SIDEBAR")
        print("=" * 40)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Проверяем все навигационные элементы
            nav_elements = await page.evaluate('''
                () => {
                    const links = document.querySelectorAll('.sidebar .nav-link');
                    const results = [];
                    
                    links.forEach((link, index) => {
                        const rect = link.getBoundingClientRect();
                        const section = link.getAttribute('data-section');
                        const text = link.textContent.trim();
                        
                        results.push({
                            index: index,
                            section: section,
                            text: text,
                            visible: rect.width > 0 && rect.height > 0,
                            inViewport: rect.top >= 0 && rect.bottom <= window.innerHeight,
                            top: rect.top,
                            bottom: rect.bottom,
                            left: rect.left,
                            width: rect.width
                        });
                    });
                    
                    return results;
                }
            ''')
            
            print(f"\n📋 Найдено навигационных элементов: {len(nav_elements)}")
            
            for element in nav_elements:
                status = "✅" if element['visible'] and element['inViewport'] else "❌"
                viewport_status = "в области видимости" if element['inViewport'] else "ВНЕ области видимости"
                print(f"   {status} {element['text']} ({element['section']}) - {viewport_status}")
                if not element['inViewport']:
                    print(f"      Top: {element['top']}, Bottom: {element['bottom']}")
            
            # Пробуем прокрутить sidebar, если нужно
            deepseek_settings_link = None
            for element in nav_elements:
                if element['section'] == 'deepseek-settings':
                    deepseek_settings_link = element
                    break
            
            if deepseek_settings_link and not deepseek_settings_link['inViewport']:
                print(f"\n🔄 DeepSeek Settings вне области видимости, пробуем прокрутить...")
                
                # Прокручиваем sidebar
                await page.evaluate('''
                    () => {
                        const sidebar = document.querySelector('.sidebar');
                        const link = document.querySelector('a[data-section="deepseek-settings"]');
                        if (sidebar && link) {
                            link.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }
                ''')
                
                await page.wait_for_timeout(1000)
                
                # Проверяем снова
                link_visible = await page.evaluate('''
                    () => {
                        const link = document.querySelector('a[data-section="deepseek-settings"]');
                        if (!link) return false;
                        
                        const rect = link.getBoundingClientRect();
                        return rect.top >= 0 && rect.bottom <= window.innerHeight;
                    }
                ''')
                
                print(f"   После прокрутки: {'✅ ВИДИМ' if link_visible else '❌ ВСЕ ЕЩЕ НЕ ВИДИМ'}")
            
            # Пробуем кликнуть на DeepSeek Settings
            print(f"\n🧠 Пробуем перейти в DeepSeek Settings...")
            
            try:
                # Используем JavaScript клик вместо Playwright клика
                await page.evaluate('''
                    () => {
                        const link = document.querySelector('a[data-section="deepseek-settings"]');
                        if (link) {
                            link.click();
                        }
                    }
                ''')
                
                await page.wait_for_timeout(2000)
                
                # Проверяем, что секция открылась
                section_visible = await page.evaluate('''
                    () => {
                        const section = document.getElementById('deepseek-settings-section');
                        return section && window.getComputedStyle(section).display === 'block';
                    }
                ''')
                
                print(f"   DeepSeek Settings секция: {'✅ ОТКРЫТА' if section_visible else '❌ НЕ ОТКРЫТА'}")
                
                if section_visible:
                    # Проверяем позиционирование
                    position_check = await page.evaluate('''
                        () => {
                            const section = document.getElementById('deepseek-settings-section');
                            if (!section) return null;
                            
                            const rect = section.getBoundingClientRect();
                            return {
                                left: rect.left,
                                width: rect.width,
                                properlyPositioned: rect.left >= 250
                            };
                        }
                    ''')
                    
                    if position_check:
                        print(f"   Позиционирование: {'✅ ПРАВИЛЬНОЕ' if position_check['properlyPositioned'] else '❌ НЕПРАВИЛЬНОЕ'}")
                        print(f"   Left: {position_check['left']}px, Width: {position_check['width']}px")
                
            except Exception as e:
                print(f"   ❌ Ошибка при клике: {e}")
            
            # Скриншот
            await page.screenshot(path="navigation_test.png", full_page=True)
            print(f"\n📸 Скриншот: navigation_test.png")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_navigation())
