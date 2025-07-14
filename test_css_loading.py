#!/usr/bin/env python3
"""
Test CSS loading and styling issues
"""

import asyncio
from playwright.async_api import async_playwright

async def test_css_loading():
    """Test CSS loading and identify styling issues"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print('🔍 TESTING CSS LOADING AND STYLING')
            print('=' * 50)
            
            # Navigate to dashboard
            await page.goto('http://localhost:8000/api/v1/admin/dashboard')
            await page.wait_for_load_state('networkidle')
            
            # Test 1: Check if CSS file loads
            css_response = await page.evaluate('''async () => {
                try {
                    const response = await fetch('/static/css/admin_dashboard.css');
                    return {
                        status: response.status,
                        loaded: response.ok,
                        size: response.ok ? (await response.text()).length : 0
                    };
                } catch (e) {
                    return { status: 0, loaded: false, error: e.message };
                }
            }''')
            
            print(f'✅ CSS File Loading:')
            print(f'   - Status: {css_response.get("status", "Unknown")}')
            print(f'   - Loaded: {css_response.get("loaded", False)}')
            print(f'   - Size: {css_response.get("size", 0)} characters')
            
            # Test 2: Check if styles are applied
            sidebar_styles = await page.evaluate('''() => {
                const sidebar = document.querySelector('.sidebar');
                if (!sidebar) return null;
                
                const styles = window.getComputedStyle(sidebar);
                return {
                    position: styles.position,
                    width: styles.width,
                    background: styles.background,
                    zIndex: styles.zIndex
                };
            }''')
            
            print(f'\\n✅ Sidebar Styling:')
            if sidebar_styles:
                print(f'   - Position: {sidebar_styles.get("position", "not set")}')
                print(f'   - Width: {sidebar_styles.get("width", "not set")}')
                print(f'   - Background: {sidebar_styles.get("background", "not set")[:50]}...')
                print(f'   - Z-Index: {sidebar_styles.get("zIndex", "not set")}')
            else:
                print('   - ❌ Sidebar element not found')
            
            # Test 3: Check main content positioning
            main_content_styles = await page.evaluate('''() => {
                const main = document.querySelector('.main-content');
                if (!main) return null;
                
                const styles = window.getComputedStyle(main);
                return {
                    marginLeft: styles.marginLeft,
                    padding: styles.padding,
                    width: styles.width
                };
            }''')
            
            print(f'\\n✅ Main Content Styling:')
            if main_content_styles:
                print(f'   - Margin Left: {main_content_styles.get("marginLeft", "not set")}')
                print(f'   - Padding: {main_content_styles.get("padding", "not set")}')
                print(f'   - Width: {main_content_styles.get("width", "not set")}')
            else:
                print('   - ❌ Main content element not found')
            
            # Test 4: Check for layout issues
            layout_issues = await page.evaluate('''() => {
                const issues = [];
                
                // Check if sidebar overlaps content
                const sidebar = document.querySelector('.sidebar');
                const mainContent = document.querySelector('.main-content');
                
                if (sidebar && mainContent) {
                    const sidebarRect = sidebar.getBoundingClientRect();
                    const mainRect = mainContent.getBoundingClientRect();
                    
                    if (sidebarRect.right > mainRect.left) {
                        issues.push('Sidebar overlaps main content');
                    }
                }
                
                // Check for hidden form fields
                const hiddenFields = Array.from(document.querySelectorAll('input, select, textarea'))
                    .filter(field => {
                        const rect = field.getBoundingClientRect();
                        return rect.width === 0 || rect.height === 0 || 
                               window.getComputedStyle(field).display === 'none';
                    }).length;
                
                if (hiddenFields > 0) {
                    issues.push(`${hiddenFields} form fields are hidden`);
                }
                
                return issues;
            }''')
            
            print(f'\\n🔍 Layout Issues:')
            if layout_issues:
                for issue in layout_issues:
                    print(f'   - ❌ {issue}')
            else:
                print('   - ✅ No layout issues detected')
            
            # Test 5: Check specific problematic sections
            print(f'\\n🔍 Checking Problematic Sections:')
            
            sections = ['deepseek-settings', 'triggers', 'templates', 'conversations']
            for section in sections:
                await page.click(f'a[data-section="{section}"]')
                await page.wait_for_timeout(500)
                
                visible_fields = await page.evaluate(f'''() => {{
                    const section = document.querySelector('[data-section="{section}"]');
                    if (!section) return 0;
                    
                    const fields = section.querySelectorAll('input, select, textarea');
                    let visible = 0;
                    
                    fields.forEach(field => {{
                        const rect = field.getBoundingClientRect();
                        const styles = window.getComputedStyle(field);
                        if (rect.width > 0 && rect.height > 0 && styles.display !== 'none') {{
                            visible++;
                        }}
                    }});
                    
                    return visible;
                }}''')
                
                print(f'   - {section}: {visible_fields} visible fields')
            
            print(f'\\n📊 SUMMARY:')
            css_working = css_response.get('loaded', False)
            styles_applied = sidebar_styles is not None
            no_layout_issues = len(layout_issues) == 0
            
            print(f'   - CSS File Loading: {"✅" if css_working else "❌"}')
            print(f'   - Styles Applied: {"✅" if styles_applied else "❌"}')
            print(f'   - Layout Issues: {"✅" if no_layout_issues else "❌"}')
            
            if css_working and styles_applied and no_layout_issues:
                print('\\n🎉 CSS is working correctly!')
            else:
                print('\\n⚠️ CSS issues detected - need investigation')
            
        except Exception as e:
            print(f'❌ Error during CSS testing: {e}')
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_css_loading())
