#!/usr/bin/env python3
"""
Quick Layout Check - Быстрая проверка верстки
"""

import asyncio
from playwright.async_api import async_playwright

async def quick_check():
    """Быстрая проверка верстки"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("⚡ БЫСТРАЯ ПРОВЕРКА ВЕРСТКИ")
        print("=" * 40)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            
            print("✅ Страница загружена")
            
            # Проверяем sidebar
            sidebar_fixed = await page.evaluate('''
                () => {
                    const sidebar = document.querySelector('.sidebar');
                    if (!sidebar) return false;
                    const style = window.getComputedStyle(sidebar);
                    return style.position === 'fixed' && style.width === '250px';
                }
            ''')
            
            print(f"🔧 Sidebar fixed: {'✅ ДА' if sidebar_fixed else '❌ НЕТ'}")
            
            # Проверяем main-content
            main_margin = await page.evaluate('''
                () => {
                    const main = document.querySelector('.main-content');
                    if (!main) return false;
                    const style = window.getComputedStyle(main);
                    return style.marginLeft === '250px';
                }
            ''')
            
            print(f"📄 Main margin: {'✅ ДА' if main_margin else '❌ НЕТ'}")
            
            # Проверяем карточки
            cards_styled = await page.evaluate('''
                () => {
                    const card = document.querySelector('.card');
                    if (!card) return false;
                    const style = window.getComputedStyle(card);
                    return style.borderRadius === '15px';
                }
            ''')
            
            print(f"🃏 Cards styled: {'✅ ДА' if cards_styled else '❌ НЕТ'}")
            
            # Делаем скриншот
            await page.screenshot(path="quick_check.png", full_page=True)
            print("📸 Скриншот: quick_check.png")
            
            if sidebar_fixed and main_margin and cards_styled:
                print("\n🎉 ВСЕ СТИЛИ ПРИМЕНИЛИСЬ ПРАВИЛЬНО!")
            else:
                print("\n⚠️ НЕКОТОРЫЕ СТИЛИ НЕ ПРИМЕНИЛИСЬ")
                print("💡 Проверьте скриншот для визуальной оценки")
            
            await page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(quick_check())
