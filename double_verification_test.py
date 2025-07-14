#!/usr/bin/env python3
"""
Double Verification Test - Двойная проверка исправления
"""

import asyncio
from playwright.async_api import async_playwright

async def double_verification():
    """Двойная проверка исправления позиционирования"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🔥 ДВОЙНАЯ ПРОВЕРКА ИСПРАВЛЕНИЯ")
        print("=" * 60)
        
        try:
            await page.goto("http://localhost:8000/api/v1/admin/dashboard")
            await page.wait_for_load_state('networkidle')
            print("✅ Страница загружена")
            
            # ПЕРВАЯ ПРОВЕРКА
            print("\n🔍 ПЕРВАЯ ПРОВЕРКА:")
            print("-" * 30)
            
            # Проверяем DeepSeek Settings
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(2000)
            
            first_check = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        left: rect.left,
                        top: rect.top,
                        position: style.position,
                        display: style.display,
                        properlyPositioned: rect.left >= 250,
                        noWhiteSpace: rect.top < 200
                    };
                }
            ''')
            
            if first_check:
                print(f"📊 DeepSeek Settings (1-я проверка):")
                print(f"   Left: {first_check['left']}px")
                print(f"   Top: {first_check['top']}px")
                print(f"   Position: {first_check['position']}")
                print(f"   Правильно позиционирован: {'✅' if first_check['properlyPositioned'] else '❌'}")
                print(f"   Нет белого пространства: {'✅' if first_check['noWhiteSpace'] else '❌'}")
                
                first_success = first_check['properlyPositioned'] and first_check['noWhiteSpace']
                print(f"   РЕЗУЛЬТАТ 1-й проверки: {'🎉 УСПЕХ' if first_success else '❌ ПРОВАЛ'}")
            
            # Проверяем другие секции
            sections_to_test = ['conversations', 'triggers', 'templates']
            first_other_results = {}
            
            for section_name in sections_to_test:
                await page.evaluate(f'''
                    () => {{
                        const link = document.querySelector('a[data-section="{section_name}"]');
                        if (link) link.click();
                    }}
                ''')
                await page.wait_for_timeout(1000)
                
                section_check = await page.evaluate(f'''
                    () => {{
                        const section = document.getElementById('{section_name}-section');
                        if (!section) return null;
                        
                        const rect = section.getBoundingClientRect();
                        const style = window.getComputedStyle(section);
                        
                        return {{
                            left: rect.left,
                            position: style.position,
                            display: style.display,
                            properlyPositioned: rect.left >= 250
                        }};
                    }}
                ''')
                
                if section_check:
                    result = "✅ ОК" if section_check['properlyPositioned'] else "❌ ПРОБЛЕМА"
                    print(f"   {section_name}: {result} (left: {section_check['left']}px)")
                    first_other_results[section_name] = section_check['properlyPositioned']
            
            # ВТОРАЯ ПРОВЕРКА (через 3 секунды)
            print(f"\n⏰ Ожидание 3 секунды перед второй проверкой...")
            await page.wait_for_timeout(3000)
            
            print("\n🔍 ВТОРАЯ ПРОВЕРКА:")
            print("-" * 30)
            
            # Снова проверяем DeepSeek Settings
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(2000)
            
            second_check = await page.evaluate('''
                () => {
                    const section = document.getElementById('deepseek-settings-section');
                    if (!section) return null;
                    
                    const rect = section.getBoundingClientRect();
                    const style = window.getComputedStyle(section);
                    
                    return {
                        left: rect.left,
                        top: rect.top,
                        position: style.position,
                        display: style.display,
                        properlyPositioned: rect.left >= 250,
                        noWhiteSpace: rect.top < 200
                    };
                }
            ''')
            
            if second_check:
                print(f"📊 DeepSeek Settings (2-я проверка):")
                print(f"   Left: {second_check['left']}px")
                print(f"   Top: {second_check['top']}px")
                print(f"   Position: {second_check['position']}")
                print(f"   Правильно позиционирован: {'✅' if second_check['properlyPositioned'] else '❌'}")
                print(f"   Нет белого пространства: {'✅' if second_check['noWhiteSpace'] else '❌'}")
                
                second_success = second_check['properlyPositioned'] and second_check['noWhiteSpace']
                print(f"   РЕЗУЛЬТАТ 2-й проверки: {'🎉 УСПЕХ' if second_success else '❌ ПРОВАЛ'}")
            
            # Снова проверяем другие секции
            second_other_results = {}
            
            for section_name in sections_to_test:
                await page.evaluate(f'''
                    () => {{
                        const link = document.querySelector('a[data-section="{section_name}"]');
                        if (link) link.click();
                    }}
                ''')
                await page.wait_for_timeout(1000)
                
                section_check = await page.evaluate(f'''
                    () => {{
                        const section = document.getElementById('{section_name}-section');
                        if (!section) return null;
                        
                        const rect = section.getBoundingClientRect();
                        return {{
                            left: rect.left,
                            properlyPositioned: rect.left >= 250
                        }};
                    }}
                ''')
                
                if section_check:
                    result = "✅ ОК" if section_check['properlyPositioned'] else "❌ ПРОБЛЕМА"
                    print(f"   {section_name}: {result} (left: {section_check['left']}px)")
                    second_other_results[section_name] = section_check['properlyPositioned']
            
            # ИТОГОВАЯ ОЦЕНКА
            print(f"\n" + "=" * 60)
            print("🎯 ИТОГОВАЯ ОЦЕНКА ДВОЙНОЙ ПРОВЕРКИ")
            print("=" * 60)
            
            # Проверяем консистентность результатов
            deepseek_consistent = (first_check and second_check and 
                                 first_check['left'] == second_check['left'] and
                                 first_success == second_success)
            
            others_consistent = all(
                first_other_results.get(section) == second_other_results.get(section)
                for section in sections_to_test
            )
            
            print(f"📊 DeepSeek Settings:")
            if first_check and second_check:
                if first_success and second_success:
                    print(f"   🎉 ПОЛНОСТЬЮ ИСПРАВЛЕНО!")
                    print(f"   ✅ Обе проверки успешны")
                    print(f"   ✅ Позиционирование: {second_check['left']}px (правильно)")
                    print(f"   ✅ Белое пространство устранено")
                elif deepseek_consistent:
                    print(f"   ❌ ПРОБЛЕМА ОСТАЕТСЯ")
                    print(f"   ❌ Обе проверки показывают одинаковую проблему")
                else:
                    print(f"   ⚠️ НЕСТАБИЛЬНОЕ ПОВЕДЕНИЕ")
                    print(f"   ⚠️ Результаты проверок различаются")
            
            print(f"\n📊 Другие секции:")
            all_others_ok = all(second_other_results.values())
            if all_others_ok:
                print(f"   🎉 ВСЕ СЕКЦИИ РАБОТАЮТ ПРАВИЛЬНО!")
                for section in sections_to_test:
                    print(f"   ✅ {section}")
            else:
                print(f"   ⚠️ НЕКОТОРЫЕ СЕКЦИИ ИМЕЮТ ПРОБЛЕМЫ:")
                for section, ok in second_other_results.items():
                    status = "✅" if ok else "❌"
                    print(f"   {status} {section}")
            
            # Финальный вердикт
            all_perfect = (first_success and second_success and 
                          deepseek_consistent and all_others_ok)
            
            print(f"\n🏆 ФИНАЛЬНЫЙ ВЕРДИКТ:")
            if all_perfect:
                print(f"   🎉🎉🎉 ВСЕ ИСПРАВЛЕНО НА 100%! 🎉🎉🎉")
                print(f"   ✅ DeepSeek Settings работает идеально")
                print(f"   ✅ Все остальные секции работают правильно")
                print(f"   ✅ Результаты стабильны и консистентны")
            else:
                print(f"   ⚠️ ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ РАБОТА")
                if not (first_success and second_success):
                    print(f"   ❌ DeepSeek Settings все еще имеет проблемы")
                if not all_others_ok:
                    print(f"   ❌ Некоторые другие секции имеют проблемы")
                if not deepseek_consistent:
                    print(f"   ❌ Нестабильное поведение")
            
            # Скриншот для документации
            await page.evaluate('''
                () => {
                    const link = document.querySelector('a[data-section="deepseek-settings"]');
                    if (link) link.click();
                }
            ''')
            await page.wait_for_timeout(1000)
            await page.screenshot(path="double_verification_result.png", full_page=True)
            print(f"\n📸 Скриншот результата: double_verification_result.png")
            
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"❌ Ошибка при двойной проверке: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(double_verification())
