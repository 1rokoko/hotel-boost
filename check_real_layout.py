#!/usr/bin/env python3
"""
Real Layout Check - Проверка верстки на реальном сайте
"""

import asyncio
from playwright.async_api import async_playwright
import time

async def check_real_layout():
    """Проверка реальной верстки админ панели"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🔍 ПРОВЕРКА РЕАЛЬНОЙ ВЕРСТКИ АДМИН ПАНЕЛИ")
        print("=" * 60)
        
        try:
            # Переходим на админ панель
            print("📍 Переходим на http://localhost:8000/api/v1/admin/dashboard")
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            
            print("✅ Страница загружена")
            
            # Проверяем, загружается ли CSS файл
            print("\n🎨 Проверка загрузки CSS...")
            
            # Проверяем наличие ссылки на CSS
            css_link = await page.query_selector('link[href*="admin_dashboard.css"]')
            if css_link:
                href = await css_link.get_attribute('href')
                print(f"✅ CSS ссылка найдена: {href}")
            else:
                print("❌ CSS ссылка НЕ найдена!")
            
            # Проверяем, применяются ли стили к sidebar
            print("\n🔧 Проверка стилей sidebar...")
            sidebar = await page.query_selector('.sidebar')
            if sidebar:
                # Получаем вычисленные стили
                styles = await page.evaluate('''
                    () => {
                        const sidebar = document.querySelector('.sidebar');
                        if (!sidebar) return null;
                        
                        const computed = window.getComputedStyle(sidebar);
                        return {
                            position: computed.position,
                            width: computed.width,
                            left: computed.left,
                            background: computed.background,
                            zIndex: computed.zIndex
                        };
                    }
                ''')
                
                print(f"📊 Стили sidebar:")
                print(f"   - Position: {styles['position']}")
                print(f"   - Width: {styles['width']}")
                print(f"   - Left: {styles['left']}")
                print(f"   - Z-Index: {styles['zIndex']}")
                print(f"   - Background: {styles['background'][:50]}...")
                
                # Проверяем правильность позиционирования
                if styles['position'] == 'fixed' and styles['width'] == '250px':
                    print("✅ Sidebar правильно позиционирован!")
                else:
                    print("❌ Sidebar НЕ правильно позиционирован!")
            else:
                print("❌ Sidebar НЕ найден!")
            
            # Проверяем main-content
            print("\n📄 Проверка main-content...")
            main_content = await page.query_selector('.main-content')
            if main_content:
                main_styles = await page.evaluate('''
                    () => {
                        const main = document.querySelector('.main-content');
                        if (!main) return null;
                        
                        const computed = window.getComputedStyle(main);
                        return {
                            marginLeft: computed.marginLeft,
                            width: computed.width,
                            padding: computed.padding
                        };
                    }
                ''')
                
                print(f"📊 Стили main-content:")
                print(f"   - Margin Left: {main_styles['marginLeft']}")
                print(f"   - Width: {main_styles['width']}")
                print(f"   - Padding: {main_styles['padding']}")
                
                if main_styles['marginLeft'] == '250px':
                    print("✅ Main content правильно позиционирован!")
                else:
                    print("❌ Main content НЕ правильно позиционирован!")
            else:
                print("❌ Main content НЕ найден!")
            
            # Проверяем карточки
            print("\n🃏 Проверка стилей карточек...")
            cards = await page.query_selector_all('.card')
            if len(cards) > 0:
                card_styles = await page.evaluate('''
                    () => {
                        const card = document.querySelector('.card');
                        if (!card) return null;
                        
                        const computed = window.getComputedStyle(card);
                        return {
                            borderRadius: computed.borderRadius,
                            boxShadow: computed.boxShadow,
                            border: computed.border
                        };
                    }
                ''')
                
                print(f"📊 Стили карточек:")
                print(f"   - Border Radius: {card_styles['borderRadius']}")
                print(f"   - Border: {card_styles['border']}")
                print(f"   - Box Shadow: {card_styles['boxShadow'][:50]}...")
                
                if card_styles['borderRadius'] == '15px':
                    print("✅ Карточки правильно стилизованы!")
                else:
                    print("❌ Карточки НЕ правильно стилизованы!")
            else:
                print("❌ Карточки НЕ найдены!")
            
            # Делаем скриншот для визуальной проверки
            print("\n📸 Делаем скриншот...")
            await page.screenshot(path="admin_dashboard_layout_check.png", full_page=True)
            print("✅ Скриншот сохранен: admin_dashboard_layout_check.png")
            
            # Проверяем мобильную версию
            print("\n📱 Проверка мобильной версии...")
            await page.set_viewport_size({"width": 600, "height": 800})
            await page.wait_for_timeout(1000)
            
            mobile_toggle = await page.query_selector('.mobile-menu-toggle')
            if mobile_toggle:
                toggle_styles = await page.evaluate('''
                    () => {
                        const toggle = document.querySelector('.mobile-menu-toggle');
                        if (!toggle) return null;
                        
                        const computed = window.getComputedStyle(toggle);
                        return {
                            display: computed.display
                        };
                    }
                ''')
                
                print(f"📱 Mobile toggle display: {toggle_styles['display']}")
                if toggle_styles['display'] == 'block':
                    print("✅ Мобильная кнопка видна!")
                else:
                    print("❌ Мобильная кнопка НЕ видна!")
            else:
                print("❌ Мобильная кнопка НЕ найдена!")
            
            # Скриншот мобильной версии
            await page.screenshot(path="admin_dashboard_mobile_check.png", full_page=True)
            print("✅ Мобильный скриншот сохранен: admin_dashboard_mobile_check.png")
            
            # Проверяем, загружается ли CSS файл напрямую
            print("\n🌐 Проверка прямого доступа к CSS...")
            css_response = await page.goto("http://localhost:8000/static/css/admin_dashboard.css")
            if css_response and css_response.status == 200:
                print("✅ CSS файл доступен напрямую!")
                css_content = await css_response.text()
                print(f"✅ Размер CSS файла: {len(css_content)} символов")
                
                # Проверяем ключевые CSS правила
                key_rules = ["nav.sidebar", "position: fixed", "width: 250px"]
                for rule in key_rules:
                    if rule in css_content:
                        print(f"   ✅ Найдено правило: {rule}")
                    else:
                        print(f"   ❌ НЕ найдено правило: {rule}")
            else:
                print("❌ CSS файл НЕ доступен напрямую!")
            
            print("\n" + "=" * 60)
            print("📋 ИТОГОВАЯ ПРОВЕРКА ВЕРСТКИ")
            print("=" * 60)
            
            print("🎯 ЧТО ПРОВЕРИЛИ:")
            print("   - Загрузка CSS файла")
            print("   - Позиционирование sidebar")
            print("   - Отступы main-content")
            print("   - Стилизация карточек")
            print("   - Мобильная адаптивность")
            print("   - Прямой доступ к CSS")
            
            print("\n📸 СКРИНШОТЫ СОХРАНЕНЫ:")
            print("   - admin_dashboard_layout_check.png (десктоп)")
            print("   - admin_dashboard_mobile_check.png (мобильная)")
            
            print("\n🔍 РЕКОМЕНДАЦИИ:")
            print("   1. Проверьте скриншоты визуально")
            print("   2. Если стили не применяются, проверьте кеш браузера")
            print("   3. Убедитесь, что сервер перезапущен")
            print("   4. Проверьте консоль браузера на ошибки")
            
            # Ждем 5 секунд, чтобы пользователь мог посмотреть
            print("\n⏰ Оставляем браузер открытым на 10 секунд для визуальной проверки...")
            await page.wait_for_timeout(10000)
            
        except Exception as e:
            print(f"❌ Ошибка при проверке: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_real_layout())
