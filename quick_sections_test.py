#!/usr/bin/env python3
"""
Quick Sections Test - Быстрая проверка секций
"""

import asyncio
from playwright.async_api import async_playwright

async def quick_test():
    """Быстрая проверка секций"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("⚡ БЫСТРАЯ ПРОВЕРКА СЕКЦИЙ")
        print("=" * 40)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Проверяем Dashboard
            dashboard_ok = await page.evaluate('''
                () => {
                    const section = document.getElementById('dashboard-section');
                    if (!section) return false;
                    const rect = section.getBoundingClientRect();
                    return rect.left >= 250;
                }
            ''')
            print(f"🏠 Dashboard: {'✅ ОК' if dashboard_ok else '❌ ПРОБЛЕМА'}")
            
            # Переходим в DeepSeek Settings
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(1000)
            
            # Проверяем DeepSeek Settings
            deepseek_info = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    return {
                        left: rect.left,
                        top: rect.top,
                        width: rect.width,
                        height: rect.height,
                        display: window.getComputedStyle(section).display
                    };
                }
            ''')
            
            if deepseek_info:
                print(f"🧠 DeepSeek Settings:")
                print(f"   Left: {deepseek_info['left']}px")
                print(f"   Top: {deepseek_info['top']}px")
                print(f"   Display: {deepseek_info['display']}")
                
                if deepseek_info['left'] >= 250:
                    print(f"   ✅ Правильно позиционирован")
                else:
                    print(f"   ❌ Перекрывается с sidebar")
                    
                if deepseek_info['top'] < 200:
                    print(f"   ✅ Нет белого пространства")
                else:
                    print(f"   ❌ Есть белое пространство")
            
            # Скриншот
            await page.screenshot(path="quick_test.png", full_page=True)
            print(f"📸 Скриншот: quick_test.png")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(quick_test())
