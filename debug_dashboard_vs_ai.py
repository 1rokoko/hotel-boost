#!/usr/bin/env python3
"""
Debug Dashboard vs AI - Сравнение работающего Dashboard с проблемной AI Configuration
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_comparison():
    """Детальное сравнение Dashboard и AI Configuration"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🔍 ДЕТАЛЬНОЕ СРАВНЕНИЕ DASHBOARD И AI CONFIGURATION")
        print("=" * 70)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Анализируем Dashboard (работающий)
            print("\n📊 АНАЛИЗ DASHBOARD (РАБОТАЮЩИЙ):")
            dashboard_analysis = await page.evaluate('''
                () => {
                    const section = document.getElementById('dashboard-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        id: section.id,
                        className: section.className,
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
                        parentClassName: section.parentElement.className,
                        hasActiveClass: section.classList.contains('active'),
                        innerHTML: section.innerHTML.substring(0, 200) + '...'
                    };
                }
            ''')
            
            if dashboard_analysis:
                print(f"   ID: {dashboard_analysis['id']}")
                print(f"   Class: {dashboard_analysis['className']}")
                print(f"   Display: {dashboard_analysis['display']}")
                print(f"   Position: {dashboard_analysis['position']}")
                print(f"   Left: {dashboard_analysis['left']}px")
                print(f"   Top: {dashboard_analysis['top']}px")
                print(f"   Margin Left: {dashboard_analysis['marginLeft']}")
                print(f"   Padding Left: {dashboard_analysis['paddingLeft']}")
                print(f"   Transform: {dashboard_analysis['transform']}")
                print(f"   Z-Index: {dashboard_analysis['zIndex']}")
                print(f"   Parent Class: {dashboard_analysis['parentClassName']}")
                print(f"   Active: {dashboard_analysis['hasActiveClass']}")
            
            # Переходим в AI Configuration
            print("\n🧠 ПЕРЕХОД В AI CONFIGURATION...")
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-config"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(2000)
            
            # Анализируем AI Configuration (проблемный)
            print("\n📊 АНАЛИЗ AI CONFIGURATION (ПРОБЛЕМНЫЙ):")
            ai_analysis = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-config-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        id: section.id,
                        className: section.className,
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
                        parentClassName: section.parentElement.className,
                        hasActiveClass: section.classList.contains('active'),
                        innerHTML: section.innerHTML.substring(0, 200) + '...'
                    };
                }
            ''')
            
            if ai_analysis:
                print(f"   ID: {ai_analysis['id']}")
                print(f"   Class: {ai_analysis['className']}")
                print(f"   Display: {ai_analysis['display']}")
                print(f"   Position: {ai_analysis['position']}")
                print(f"   Left: {ai_analysis['left']}px")
                print(f"   Top: {ai_analysis['top']}px")
                print(f"   Margin Left: {ai_analysis['marginLeft']}")
                print(f"   Padding Left: {ai_analysis['paddingLeft']}")
                print(f"   Transform: {ai_analysis['transform']}")
                print(f"   Z-Index: {ai_analysis['zIndex']}")
                print(f"   Parent Class: {ai_analysis['parentClassName']}")
                print(f"   Active: {ai_analysis['hasActiveClass']}")
            
            # Сравнение
            print(f"\n🔍 ДЕТАЛЬНОЕ СРАВНЕНИЕ:")
            if dashboard_analysis and ai_analysis:
                differences = []
                
                if dashboard_analysis['left'] != ai_analysis['left']:
                    differences.append(f"Left: {dashboard_analysis['left']} vs {ai_analysis['left']}")
                if dashboard_analysis['position'] != ai_analysis['position']:
                    differences.append(f"Position: {dashboard_analysis['position']} vs {ai_analysis['position']}")
                if dashboard_analysis['className'] != ai_analysis['className']:
                    differences.append(f"Class: '{dashboard_analysis['className']}' vs '{ai_analysis['className']}'")
                if dashboard_analysis['hasActiveClass'] != ai_analysis['hasActiveClass']:
                    differences.append(f"Active: {dashboard_analysis['hasActiveClass']} vs {ai_analysis['hasActiveClass']}")
                
                if differences:
                    print(f"🚨 КЛЮЧЕВЫЕ РАЗЛИЧИЯ:")
                    for diff in differences:
                        print(f"   - {diff}")
                else:
                    print(f"✅ НЕТ КЛЮЧЕВЫХ РАЗЛИЧИЙ")
            
            # Проверяем CSS правила
            css_rules = await page.evaluate('''
                () => {
                    const dashboard = document.getElementById('dashboard-section');
                    const aiConfig = document.getElementById('deepseek-config-section');
                    
                    if (!dashboard || !aiConfig) return null;
                    
                    const dashboardStyles = window.getComputedStyle(dashboard);
                    const aiConfigStyles = window.getComputedStyle(aiConfig);
                    
                    const props = ['position', 'left', 'top', 'margin', 'padding', 'display', 'transform'];
                    
                    const comparison = {};
                    props.forEach(prop => {
                        comparison[prop] = {
                            dashboard: dashboardStyles[prop],
                            aiConfig: aiConfigStyles[prop],
                            same: dashboardStyles[prop] === aiConfigStyles[prop]
                        };
                    });
                    
                    return comparison;
                }
            ''')
            
            if css_rules:
                print(f"\n📋 СРАВНЕНИЕ CSS ПРАВИЛ:")
                for prop, values in css_rules.items():
                    status = "✅ ОДИНАКОВО" if values['same'] else "❌ РАЗЛИЧАЕТСЯ"
                    print(f"   {prop}: {status}")
                    if not values['same']:
                        print(f"      Dashboard: '{values['dashboard']}'")
                        print(f"      AI Config: '{values['aiConfig']}'")
            
            # Попытка принудительного исправления через JavaScript
            print(f"\n🔧 ПОПЫТКА ПРИНУДИТЕЛЬНОГО ИСПРАВЛЕНИЯ:")
            
            fix_result = await page.evaluate('''
                () => {
                    const aiSection = document.getElementById('deepseek-config-section');
                    if (!aiSection) return 'Section not found';
                    
                    // Копируем стили с Dashboard
                    const dashboard = document.getElementById('dashboard-section');
                    if (!dashboard) return 'Dashboard not found';
                    
                    const dashboardStyles = window.getComputedStyle(dashboard);
                    
                    // Применяем те же стили
                    aiSection.style.setProperty('position', dashboardStyles.position, 'important');
                    aiSection.style.setProperty('left', dashboardStyles.left, 'important');
                    aiSection.style.setProperty('top', dashboardStyles.top, 'important');
                    aiSection.style.setProperty('margin', dashboardStyles.margin, 'important');
                    aiSection.style.setProperty('padding', dashboardStyles.padding, 'important');
                    aiSection.style.setProperty('transform', dashboardStyles.transform, 'important');
                    
                    // Проверяем результат
                    const newRect = aiSection.getBoundingClientRect();
                    
                    return {
                        success: newRect.left >= 250,
                        newLeft: newRect.left,
                        newTop: newRect.top
                    };
                }
            ''')
            
            if fix_result:
                if isinstance(fix_result, dict):
                    print(f"   Результат исправления: {'✅ УСПЕХ' if fix_result['success'] else '❌ ПРОВАЛ'}")
                    print(f"   Новый Left: {fix_result['newLeft']}px")
                    print(f"   Новый Top: {fix_result['newTop']}px")
                else:
                    print(f"   Ошибка: {fix_result}")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_comparison())
