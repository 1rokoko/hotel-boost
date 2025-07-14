#!/usr/bin/env python3
"""
Compare Sections - Сравнение Dashboard и DeepSeek Settings
"""

import asyncio
from playwright.async_api import async_playwright

async def compare_sections():
    """Сравнение Dashboard и DeepSeek Settings для поиска различий"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🔍 СРАВНЕНИЕ DASHBOARD И DEEPSEEK SETTINGS")
        print("=" * 60)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Анализируем Dashboard
            print("\n📊 АНАЛИЗ DASHBOARD СЕКЦИИ:")
            dashboard_info = await page.evaluate('''
                () => {
                    const section = document.getElementById('dashboard-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        display: style.display,
                        position: style.position,
                        left: rect.left,
                        top: rect.top,
                        width: rect.width,
                        height: rect.height,
                        marginLeft: style.marginLeft,
                        paddingLeft: style.paddingLeft,
                        transform: style.transform,
                        zIndex: style.zIndex,
                        className: section.className,
                        hasActiveClass: section.classList.contains('active'),
                        parentElement: section.parentElement.className
                    };
                }
            ''')
            
            if dashboard_info:
                print(f"   Display: {dashboard_info['display']}")
                print(f"   Position: {dashboard_info['position']}")
                print(f"   Left: {dashboard_info['left']}px")
                print(f"   Top: {dashboard_info['top']}px")
                print(f"   Margin Left: {dashboard_info['marginLeft']}")
                print(f"   Padding Left: {dashboard_info['paddingLeft']}")
                print(f"   Transform: {dashboard_info['transform']}")
                print(f"   Z-Index: {dashboard_info['zIndex']}")
                print(f"   Class: {dashboard_info['className']}")
                print(f"   Active: {dashboard_info['hasActiveClass']}")
                print(f"   Parent: {dashboard_info['parentElement']}")
            
            # Переходим в DeepSeek Settings
            print("\n🧠 ПЕРЕХОД В DEEPSEEK SETTINGS...")
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(2000)
            
            # Анализируем DeepSeek Settings
            print("\n📊 АНАЛИЗ DEEPSEEK SETTINGS СЕКЦИИ:")
            deepseek_info = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        display: style.display,
                        position: style.position,
                        left: rect.left,
                        top: rect.top,
                        width: rect.width,
                        height: rect.height,
                        marginLeft: style.marginLeft,
                        paddingLeft: style.paddingLeft,
                        transform: style.transform,
                        zIndex: style.zIndex,
                        className: section.className,
                        hasActiveClass: section.classList.contains('active'),
                        parentElement: section.parentElement.className
                    };
                }
            ''')
            
            if deepseek_info:
                print(f"   Display: {deepseek_info['display']}")
                print(f"   Position: {deepseek_info['position']}")
                print(f"   Left: {deepseek_info['left']}px")
                print(f"   Top: {deepseek_info['top']}px")
                print(f"   Margin Left: {deepseek_info['marginLeft']}")
                print(f"   Padding Left: {deepseek_info['paddingLeft']}")
                print(f"   Transform: {deepseek_info['transform']}")
                print(f"   Z-Index: {deepseek_info['zIndex']}")
                print(f"   Class: {deepseek_info['className']}")
                print(f"   Active: {deepseek_info['hasActiveClass']}")
                print(f"   Parent: {deepseek_info['parentElement']}")
            
            # Сравнение
            print("\n🔍 СРАВНЕНИЕ:")
            if dashboard_info and deepseek_info:
                print(f"   Dashboard Left: {dashboard_info['left']}px")
                print(f"   DeepSeek Left: {deepseek_info['left']}px")
                print(f"   Разница: {deepseek_info['left'] - dashboard_info['left']}px")
                
                print(f"\n   Dashboard Position: {dashboard_info['position']}")
                print(f"   DeepSeek Position: {deepseek_info['position']}")
                
                print(f"\n   Dashboard Active: {dashboard_info['hasActiveClass']}")
                print(f"   DeepSeek Active: {deepseek_info['hasActiveClass']}")
                
                # Ключевые различия
                differences = []
                if dashboard_info['left'] != deepseek_info['left']:
                    differences.append(f"Left позиция: {dashboard_info['left']} vs {deepseek_info['left']}")
                if dashboard_info['position'] != deepseek_info['position']:
                    differences.append(f"Position: {dashboard_info['position']} vs {deepseek_info['position']}")
                if dashboard_info['marginLeft'] != deepseek_info['marginLeft']:
                    differences.append(f"Margin Left: {dashboard_info['marginLeft']} vs {deepseek_info['marginLeft']}")
                
                if differences:
                    print(f"\n🚨 КЛЮЧЕВЫЕ РАЗЛИЧИЯ:")
                    for diff in differences:
                        print(f"   - {diff}")
                else:
                    print(f"\n✅ НЕТ КЛЮЧЕВЫХ РАЗЛИЧИЙ В CSS")
            
            # Проверяем CSS правила для обеих секций
            css_analysis = await page.evaluate('''
                () => {
                    const dashboard = document.getElementById('dashboard-section');
                    const deepseek = document.getElementById('deepseek-settings-section');
                    
                    if (!dashboard || !deepseek) return null;
                    
                    // Получаем все CSS правила
                    const dashboardStyles = window.getComputedStyle(dashboard);
                    const deepseekStyles = window.getComputedStyle(deepseek);
                    
                    const importantProps = ['position', 'left', 'top', 'margin', 'marginLeft', 'padding', 'paddingLeft', 'transform', 'display'];
                    
                    const comparison = {};
                    importantProps.forEach(prop => {
                        comparison[prop] = {
                            dashboard: dashboardStyles[prop],
                            deepseek: deepseekStyles[prop],
                            same: dashboardStyles[prop] === deepseekStyles[prop]
                        };
                    });
                    
                    return comparison;
                }
            ''')
            
            if css_analysis:
                print(f"\n📋 ДЕТАЛЬНОЕ СРАВНЕНИЕ CSS:")
                for prop, values in css_analysis.items():
                    status = "✅ ОДИНАКОВО" if values['same'] else "❌ РАЗЛИЧАЕТСЯ"
                    print(f"   {prop}: {status}")
                    if not values['same']:
                        print(f"      Dashboard: {values['dashboard']}")
                        print(f"      DeepSeek: {values['deepseek']}")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(compare_sections())
