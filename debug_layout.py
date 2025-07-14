#!/usr/bin/env python3
"""
Debug Layout - Отладка структуры страницы
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_layout():
    """Отладка структуры страницы для поиска причины белого пространства"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🔍 ОТЛАДКА СТРУКТУРЫ СТРАНИЦЫ")
        print("=" * 50)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Переходим в DeepSeek Settings
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) {
                        link.click();
                    }
                }
            ''')
            
            await page.wait_for_timeout(2000)
            
            # Анализируем все элементы в main-content
            elements_info = await page.evaluate('''
                () => {
                    const mainContent = document.querySelector('.main-content');
                    if (!mainContent) return [];
                    
                    const children = Array.from(mainContent.children);
                    return children.map((child, index) => {
                        const rect = child.getBoundingClientRect();
                        const style = window.getComputedStyle(child);
                        
                        return {
                            index: index,
                            tagName: child.tagName,
                            className: child.className,
                            id: child.id,
                            top: rect.top,
                            left: rect.left,
                            width: rect.width,
                            height: rect.height,
                            display: style.display,
                            position: style.position,
                            marginTop: style.marginTop,
                            paddingTop: style.paddingTop,
                            visible: rect.width > 0 && rect.height > 0
                        };
                    });
                }
            ''')
            
            print(f"\n📋 Элементы в main-content:")
            for elem in elements_info:
                visibility = "ВИДИМ" if elem['visible'] else "СКРЫТ"
                print(f"   {elem['index']}. {elem['tagName']} (#{elem['id']}, .{elem['className']})")
                print(f"      Top: {elem['top']}px, Height: {elem['height']}px, Display: {elem['display']}")
                print(f"      Margin Top: {elem['marginTop']}, Padding Top: {elem['paddingTop']}")
                print(f"      Статус: {visibility}")
                print()
            
            # Проверяем все content-section элементы
            sections_info = await page.evaluate('''
                () => {
                    const sections = document.querySelectorAll('.content-section');
                    return Array.from(sections).map((section, index) => {
                        const rect = section.getBoundingClientRect();
                        const style = window.getComputedStyle(section);
                        
                        return {
                            index: index,
                            id: section.id,
                            top: rect.top,
                            height: rect.height,
                            display: style.display,
                            hasActiveClass: section.classList.contains('active'),
                            visible: rect.width > 0 && rect.height > 0
                        };
                    });
                }
            ''')
            
            print(f"📋 Все content-section элементы:")
            for section in sections_info:
                status = "АКТИВЕН" if section['hasActiveClass'] else "НЕАКТИВЕН"
                visibility = "ВИДИМ" if section['visible'] else "СКРЫТ"
                print(f"   {section['index']}. #{section['id']}")
                print(f"      Top: {section['top']}px, Height: {section['height']}px")
                print(f"      Display: {section['display']}, Статус: {status}, Видимость: {visibility}")
                print()
            
            # Проверяем, есть ли элементы, которые создают пространство перед DeepSeek Settings
            space_analysis = await page.evaluate('''
                () => {
                    const deepseekSection = document.getElementById('deepseek-settings-section');
                    if (!deepseekSection) return null;
                    
                    const mainContent = document.querySelector('.main-content');
                    if (!mainContent) return null;
                    
                    const mainRect = mainContent.getBoundingClientRect();
                    const deepseekRect = deepseekSection.getBoundingClientRect();
                    
                    // Ищем элементы между началом main-content и DeepSeek Settings
                    const allElements = Array.from(mainContent.querySelectorAll('*'));
                    const elementsBefore = allElements.filter(el => {
                        const rect = el.getBoundingClientRect();
                        return rect.top < deepseekRect.top && rect.height > 0;
                    });
                    
                    return {
                        mainContentTop: mainRect.top,
                        deepseekTop: deepseekRect.top,
                        spaceBetween: deepseekRect.top - mainRect.top,
                        elementsBefore: elementsBefore.length,
                        elementsBeforeDetails: elementsBefore.slice(0, 5).map(el => ({
                            tagName: el.tagName,
                            className: el.className,
                            id: el.id,
                            top: el.getBoundingClientRect().top,
                            height: el.getBoundingClientRect().height
                        }))
                    };
                }
            ''')
            
            if space_analysis:
                print(f"🔍 Анализ пространства:")
                print(f"   - Main Content Top: {space_analysis['mainContentTop']}px")
                print(f"   - DeepSeek Section Top: {space_analysis['deepseekTop']}px")
                print(f"   - Пространство между ними: {space_analysis['spaceBetween']}px")
                print(f"   - Элементов перед DeepSeek: {space_analysis['elementsBefore']}")
                
                if space_analysis['elementsBeforeDetails']:
                    print(f"   - Первые 5 элементов перед DeepSeek:")
                    for elem in space_analysis['elementsBeforeDetails']:
                        print(f"     * {elem['tagName']} (#{elem['id']}, .{elem['className']})")
                        print(f"       Top: {elem['top']}px, Height: {elem['height']}px")
            
            # Скриншот для анализа
            await page.screenshot(path="debug_layout.png", full_page=True)
            print(f"\n📸 Скриншот для анализа: debug_layout.png")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_layout())
