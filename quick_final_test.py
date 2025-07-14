#!/usr/bin/env python3
"""
Quick Final Test - Быстрая финальная проверка
"""

import asyncio
from playwright.async_api import async_playwright

async def quick_final_test():
    """Быстрая финальная проверка"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("⚡ БЫСТРАЯ ФИНАЛЬНАЯ ПРОВЕРКА")
        print("=" * 40)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # Переходим в DeepSeek Settings
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(2000)
            
            # Проверяем результат
            result = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        left: rect.left,
                        top: rect.top,
                        position: style.position,
                        success: rect.left >= 250 && rect.top < 200
                    };
                }
            ''')
            
            if result:
                print(f"🧠 DeepSeek Settings:")
                print(f"   Left: {result['left']}px")
                print(f"   Top: {result['top']}px")
                print(f"   Position: {result['position']}")
                print(f"   РЕЗУЛЬТАТ: {'🎉 УСПЕХ!' if result['success'] else '❌ ПРОВАЛ'}")
            
            await page.screenshot(path="quick_final_result.png", full_page=True)
            print(f"📸 Скриншот: quick_final_result.png")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(quick_final_test())
