#!/usr/bin/env python3
"""
Find Space Culprit - Поиск элемента, создающего белое пространство
"""

import asyncio
from playwright.async_api import async_playwright

async def find_space_culprit():
    """Поиск элемента, который создает белое пространство"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🕵️ ПОИСК ВИНОВНИКА БЕЛОГО ПРОСТРАНСТВА")
        print("=" * 60)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            
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
            
            # Анализируем каждый элемент в main-content и его высоту
            detailed_analysis = await page.evaluate('''
                () => {
                    const mainContent = document.querySelector('.main-content');
                    if (!mainContent) return null;
                    
                    const deepseekSection = document.getElementById('deepseek-settings-section');
                    if (!deepseekSection) return null;
                    
                    const deepseekRect = deepseekSection.getBoundingClientRect();
                    
                    // Получаем все элементы в main-content
                    const allChildren = Array.from(mainContent.children);
                    
                    let cumulativeHeight = 0;
                    const analysis = allChildren.map((child, index) => {
                        const rect = child.getBoundingClientRect();
                        const style = window.getComputedStyle(child);
                        
                        const elementHeight = rect.height;
                        const marginTop = parseFloat(style.marginTop) || 0;
                        const marginBottom = parseFloat(style.marginBottom) || 0;
                        const paddingTop = parseFloat(style.paddingTop) || 0;
                        const paddingBottom = parseFloat(style.paddingBottom) || 0;
                        
                        const totalSpace = elementHeight + marginTop + marginBottom + paddingTop + paddingBottom;
                        
                        const result = {
                            index: index,
                            tagName: child.tagName,
                            id: child.id,
                            className: child.className,
                            top: rect.top,
                            height: rect.height,
                            marginTop: marginTop,
                            marginBottom: marginBottom,
                            paddingTop: paddingTop,
                            paddingBottom: paddingBottom,
                            totalSpace: totalSpace,
                            display: style.display,
                            position: style.position,
                            cumulativeHeight: cumulativeHeight,
                            isDeepSeek: child.id === 'deepseek-settings-section'
                        };
                        
                        if (style.display !== 'none') {
                            cumulativeHeight += totalSpace;
                        }
                        
                        return result;
                    });
                    
                    return {
                        deepseekTop: deepseekRect.top,
                        elements: analysis,
                        totalHeightBeforeDeepSeek: cumulativeHeight
                    };
                }
            ''')
            
            if detailed_analysis:
                print(f"📊 DeepSeek Section Top: {detailed_analysis['deepseekTop']}px")
                print(f"📊 Общая высота до DeepSeek: {detailed_analysis['totalHeightBeforeDeepSeek']}px")
                print()
                
                print("📋 ДЕТАЛЬНЫЙ АНАЛИЗ ЭЛЕМЕНТОВ:")
                print("-" * 80)
                
                for elem in detailed_analysis['elements']:
                    if elem['isDeepSeek']:
                        print(f">>> DEEPSEEK SECTION <<<")
                    
                    print(f"{elem['index']}. {elem['tagName']} (#{elem['id']})")
                    print(f"   Class: {elem['className'][:50]}...")
                    print(f"   Display: {elem['display']}")
                    print(f"   Position: {elem['position']}")
                    print(f"   Top: {elem['top']}px")
                    print(f"   Height: {elem['height']}px")
                    print(f"   Margins: {elem['marginTop']}px / {elem['marginBottom']}px")
                    print(f"   Padding: {elem['paddingTop']}px / {elem['paddingBottom']}px")
                    print(f"   Total Space: {elem['totalSpace']}px")
                    print(f"   Cumulative: {elem['cumulativeHeight']}px")
                    
                    if elem['totalSpace'] > 100:
                        print(f"   ⚠️ БОЛЬШОЙ ЭЛЕМЕНТ!")
                    
                    if elem['display'] == 'none' and elem['height'] > 0:
                        print(f"   ⚠️ СКРЫТЫЙ, НО ЗАНИМАЕТ МЕСТО!")
                    
                    print()
                
                # Ищем элементы, которые могут создавать пространство
                problematic_elements = [
                    elem for elem in detailed_analysis['elements'] 
                    if (elem['display'] == 'none' and elem['height'] > 0) or 
                       (elem['totalSpace'] > 100 and not elem['isDeepSeek'])
                ]
                
                if problematic_elements:
                    print("🚨 ПРОБЛЕМНЫЕ ЭЛЕМЕНТЫ:")
                    for elem in problematic_elements:
                        print(f"   - {elem['tagName']} #{elem['id']}: {elem['totalSpace']}px")
                        print(f"     Display: {elem['display']}, Height: {elem['height']}px")
                
                # Проверяем CSS правила для скрытых элементов
                hidden_sections_info = await page.evaluate('''
                    () => {
                        const sections = document.querySelectorAll('.content-section');
                        return Array.from(sections).map(section => {
                            const rect = section.getBoundingClientRect();
                            const style = window.getComputedStyle(section);
                            
                            return {
                                id: section.id,
                                display: style.display,
                                height: rect.height,
                                top: rect.top,
                                position: style.position,
                                hasActiveClass: section.classList.contains('active')
                            };
                        });
                    }
                ''')
                
                print("\n📋 АНАЛИЗ ВСЕХ CONTENT-SECTION:")
                for section in hidden_sections_info:
                    status = "АКТИВЕН" if section['hasActiveClass'] else "СКРЫТ"
                    problem = "⚠️ ПРОБЛЕМА" if section['display'] == 'none' and section['height'] > 0 else "✅ ОК"
                    
                    print(f"   {section['id']}: {status}, Display: {section['display']}")
                    print(f"      Height: {section['height']}px, Top: {section['top']}px, {problem}")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(find_space_culprit())
