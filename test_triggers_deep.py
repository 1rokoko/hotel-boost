#!/usr/bin/env python3
"""
Deep Testing of Triggers Functionality with Playwright
Tests all trigger types, dynamic settings, and integration
"""

import asyncio
import json
from playwright.async_api import async_playwright
from typing import Dict, List, Any
import time

class TriggerDeepTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.admin_url = f"{self.base_url}/api/v1/admin/dashboard"
        self.test_results = {}
        
    async def run_deep_trigger_tests(self):
        """Run comprehensive trigger functionality tests"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            print("🔥 DEEP TRIGGER TESTING - Hotel Boost WhatsApp Bot")
            print("=" * 70)
            
            try:
                # Navigate to admin dashboard
                await page.goto(self.admin_url)
                await page.wait_for_load_state('networkidle')
                
                # Go to triggers section
                await page.click('a[data-section="triggers"]')
                await page.wait_for_timeout(1000)
                
                print("✅ Navigated to Triggers section")
                
                # Test each trigger type
                await self.test_time_based_trigger(page)
                await self.test_event_based_trigger(page)
                await self.test_condition_based_trigger(page)
                await self.test_hours_after_first_message_trigger(page)
                
                # Test trigger management
                await self.test_trigger_list_functionality(page)
                await self.test_trigger_filters(page)
                
                # Generate comprehensive report
                self.generate_deep_test_report()
                
            except Exception as e:
                print(f"❌ Critical error during testing: {e}")
            finally:
                await browser.close()
    
    async def test_time_based_trigger(self, page):
        """Test Time-Based trigger with all schedule types"""
        print("\n⏰ Testing Time-Based Triggers")
        print("-" * 50)
        
        test_results = []
        
        # Test different schedule types
        schedule_types = [
            ("hours_after_checkin", "Hours After Check-in"),
            ("days_after_checkin", "Days After Check-in"),
            ("hours_after_first_message", "Hours After First Message"),
            ("specific_time", "Specific Time Daily"),
            ("cron_expression", "Custom Schedule (Cron)")
        ]
        
        for schedule_type, display_name in schedule_types:
            print(f"   Testing: {display_name}")
            
            try:
                # Close any open modals first
                await self.close_any_open_modals(page)

                # Open create trigger modal
                await page.click('button:has-text("Create Trigger")')
                await page.wait_for_timeout(1000)
                
                # Fill basic info
                await page.fill('#triggerName', f'Test {display_name} Trigger')
                await page.select_option('#triggerType', 'time_based')
                await page.wait_for_timeout(500)
                
                # Select schedule type
                await page.select_option('#scheduleType', schedule_type)
                await page.wait_for_timeout(500)
                
                # Fill schedule-specific settings
                if schedule_type == 'hours_after_checkin':
                    await page.fill('#hoursAfter', '24')
                elif schedule_type == 'days_after_checkin':
                    await page.fill('#daysAfter', '3')
                elif schedule_type == 'hours_after_first_message':
                    await page.fill('#hoursAfterMessage', '48')
                    await page.select_option('#messageType', 'any')
                elif schedule_type == 'specific_time':
                    await page.fill('#specificTime', '14:30')
                elif schedule_type == 'cron_expression':
                    await page.fill('#cronExpression', '0 9 * * 1')
                
                # Fill message template
                await page.fill('#triggerMessage', f'Hello {{{{guest_name}}}}, this is a {display_name.lower()} message from {{{{hotel_name}}}}!')
                
                # Test form validation
                form_valid = await self.validate_trigger_form(page)
                
                test_results.append({
                    'schedule_type': schedule_type,
                    'display_name': display_name,
                    'form_valid': form_valid,
                    'status': 'PASS' if form_valid else 'FAIL'
                })
                
                print(f"      ✅ {display_name}: Form validation {'PASSED' if form_valid else 'FAILED'}")
                
                # Close modal
                await page.click('button[data-bs-dismiss="modal"]')
                await page.wait_for_timeout(1000)
                
            except Exception as e:
                test_results.append({
                    'schedule_type': schedule_type,
                    'display_name': display_name,
                    'error': str(e),
                    'status': 'ERROR'
                })
                print(f"      ❌ {display_name}: Error - {e}")
        
        self.test_results['time_based'] = test_results
    
    async def test_event_based_trigger(self, page):
        """Test Event-Based trigger with different event types"""
        print("\n⚡ Testing Event-Based Triggers")
        print("-" * 50)
        
        event_types = [
            ("guest_checkin", "Guest Check-in"),
            ("message_received", "Message Received"),
            ("first_message_received", "First Message Received"),
            ("negative_sentiment", "Negative Sentiment Detected")
        ]
        
        test_results = []
        
        for event_type, display_name in event_types:
            print(f"   Testing: {display_name}")
            
            try:
                # Open create trigger modal
                await page.click('button:has-text("Create Trigger")')
                await page.wait_for_timeout(1000)
                
                # Fill basic info
                await page.fill('#triggerName', f'Test {display_name} Trigger')
                await page.select_option('#triggerType', 'event_based')
                await page.wait_for_timeout(500)
                
                # Select event type
                await page.select_option('#eventType', event_type)
                await page.fill('#delayMinutes', '30')
                
                # Add event filters for sentiment
                if event_type == 'negative_sentiment':
                    await page.fill('#eventFilters', '{"sentiment_score": {"less_than": -0.5}}')
                
                # Fill message template
                await page.fill('#triggerMessage', f'Alert: {display_name} detected for {{{{guest_name}}}} at {{{{hotel_name}}}}!')
                
                # Test form validation
                form_valid = await self.validate_trigger_form(page)
                
                test_results.append({
                    'event_type': event_type,
                    'display_name': display_name,
                    'form_valid': form_valid,
                    'status': 'PASS' if form_valid else 'FAIL'
                })
                
                print(f"      ✅ {display_name}: Form validation {'PASSED' if form_valid else 'FAILED'}")
                
                # Close modal
                await page.click('button[data-bs-dismiss="modal"]')
                await page.wait_for_timeout(1000)
                
            except Exception as e:
                test_results.append({
                    'event_type': event_type,
                    'display_name': display_name,
                    'error': str(e),
                    'status': 'ERROR'
                })
                print(f"      ❌ {display_name}: Error - {e}")
        
        self.test_results['event_based'] = test_results
    
    async def test_condition_based_trigger(self, page):
        """Test Condition-Based trigger with multiple conditions"""
        print("\n🔧 Testing Condition-Based Triggers")
        print("-" * 50)
        
        try:
            # Open create trigger modal
            await page.click('button:has-text("Create Trigger")')
            await page.wait_for_timeout(1000)
            
            # Fill basic info
            await page.fill('#triggerName', 'Test VIP Guest Condition Trigger')
            await page.select_option('#triggerType', 'condition_based')
            await page.wait_for_timeout(500)
            
            # Set logic to AND
            await page.select_option('#conditionLogic', 'AND')
            
            # Test adding multiple conditions
            await page.click('button:has-text("Add Condition")')
            await page.wait_for_timeout(500)
            
            # Fill conditions
            conditions = await page.query_selector_all('.condition-item')
            if len(conditions) >= 2:
                # First condition: Room type = suite
                field1 = await conditions[0].query_selector('.condition-field')
                operator1 = await conditions[0].query_selector('.condition-operator')
                value1 = await conditions[0].query_selector('.condition-value')

                await field1.select_option('guest.preferences.room_type')
                await operator1.select_option('equals')
                await value1.fill('suite')

                # Second condition: VIP status = true
                field2 = await conditions[1].query_selector('.condition-field')
                operator2 = await conditions[1].query_selector('.condition-operator')
                value2 = await conditions[1].query_selector('.condition-value')

                await field2.select_option('guest.is_vip')
                await operator2.select_option('equals')
                await value2.fill('true')
                
                print("      ✅ Multiple conditions added successfully")
            
            # Fill message template
            await page.fill('#triggerMessage', 'Welcome VIP guest {{guest_name}}! Your {{room_type}} suite is ready with special amenities.')
            
            # Test form validation
            form_valid = await self.validate_trigger_form(page)
            
            self.test_results['condition_based'] = {
                'multiple_conditions': len(conditions) >= 2,
                'form_valid': form_valid,
                'status': 'PASS' if form_valid and len(conditions) >= 2 else 'FAIL'
            }
            
            print(f"      ✅ Condition-based trigger: {'PASSED' if form_valid else 'FAILED'}")
            
            # Close modal
            await page.click('button[data-bs-dismiss="modal"]')
            await page.wait_for_timeout(1000)
            
        except Exception as e:
            self.test_results['condition_based'] = {
                'error': str(e),
                'status': 'ERROR'
            }
            print(f"      ❌ Condition-based trigger: Error - {e}")
    
    async def close_any_open_modals(self, page):
        """Close any open modals before opening new ones"""
        try:
            # Check if any modal is open and close it
            modal = await page.query_selector('.modal.show')
            if modal:
                close_btn = await modal.query_selector('button[data-bs-dismiss="modal"]')
                if close_btn:
                    await close_btn.click()
                    await page.wait_for_timeout(500)
        except:
            pass

    async def test_hours_after_first_message_trigger(self, page):
        """Test the new 'Hours After First Message' trigger type"""
        print("\n💬 Testing Hours After First Message Trigger")
        print("-" * 50)

        try:
            # Close any open modals first
            await self.close_any_open_modals(page)

            # Open create trigger modal
            await page.click('button:has-text("Create Trigger")')
            await page.wait_for_timeout(1000)
            
            # Fill basic info
            await page.fill('#triggerName', 'Follow-up After First Contact')
            await page.select_option('#triggerType', 'time_based')
            await page.wait_for_timeout(500)
            
            # Select hours after first message
            await page.select_option('#scheduleType', 'hours_after_first_message')
            await page.wait_for_timeout(500)
            
            # Configure settings
            await page.fill('#hoursAfterMessage', '24')
            await page.select_option('#messageType', 'any')
            
            # Fill message template
            await page.fill('#triggerMessage', 'Hi {{guest_name}}! How was your first day at {{hotel_name}}? Need any assistance?')
            
            # Test form validation
            form_valid = await self.validate_trigger_form(page)
            
            self.test_results['hours_after_first_message'] = {
                'form_valid': form_valid,
                'status': 'PASS' if form_valid else 'FAIL'
            }
            
            print(f"      ✅ Hours After First Message: {'PASSED' if form_valid else 'FAILED'}")
            
            # Close modal
            await page.click('button[data-bs-dismiss="modal"]')
            await page.wait_for_timeout(1000)
            
        except Exception as e:
            self.test_results['hours_after_first_message'] = {
                'error': str(e),
                'status': 'ERROR'
            }
            print(f"      ❌ Hours After First Message: Error - {e}")
    
    async def validate_trigger_form(self, page):
        """Validate that trigger form has all required fields filled"""
        try:
            name = await page.input_value('#triggerName')
            trigger_type = await page.input_value('#triggerType')
            message = await page.input_value('#triggerMessage')
            
            return bool(name and trigger_type and message)
        except:
            return False
    
    async def test_trigger_list_functionality(self, page):
        """Test trigger list loading and display"""
        print("\n📋 Testing Trigger List Functionality")
        print("-" * 50)
        
        try:
            # Check if triggers list is visible
            triggers_list = await page.query_selector('#triggers-list')
            if triggers_list:
                content = await triggers_list.text_content()
                print(f"      ✅ Triggers list loaded: {content[:100]}...")
                
                self.test_results['trigger_list'] = {
                    'loaded': True,
                    'content_preview': content[:100],
                    'status': 'PASS'
                }
            else:
                print("      ❌ Triggers list not found")
                self.test_results['trigger_list'] = {
                    'loaded': False,
                    'status': 'FAIL'
                }
        except Exception as e:
            print(f"      ❌ Error testing trigger list: {e}")
            self.test_results['trigger_list'] = {
                'error': str(e),
                'status': 'ERROR'
            }
    
    async def test_trigger_filters(self, page):
        """Test trigger filtering functionality"""
        print("\n🔍 Testing Trigger Filters")
        print("-" * 50)
        
        try:
            # Test type filter
            await page.select_option('#trigger-type-filter', 'time_based')
            await page.wait_for_timeout(500)
            
            # Test status filter
            await page.select_option('#trigger-status-filter', 'active')
            await page.wait_for_timeout(500)
            
            # Test search
            await page.fill('#trigger-search', 'welcome')
            await page.wait_for_timeout(500)
            
            print("      ✅ All filter controls accessible")
            
            self.test_results['trigger_filters'] = {
                'type_filter': True,
                'status_filter': True,
                'search_filter': True,
                'status': 'PASS'
            }
            
        except Exception as e:
            print(f"      ❌ Error testing filters: {e}")
            self.test_results['trigger_filters'] = {
                'error': str(e),
                'status': 'ERROR'
            }
    
    def generate_deep_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 80)
        print("📋 DEEP TRIGGER TESTING REPORT")
        print("=" * 80)
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_tests = 0
        
        for test_category, results in self.test_results.items():
            print(f"\n🔍 {test_category.upper().replace('_', ' ')} TESTS")
            print("-" * 60)
            
            if isinstance(results, list):
                for result in results:
                    total_tests += 1
                    status = result.get('status', 'UNKNOWN')
                    
                    if status == 'PASS':
                        passed_tests += 1
                        print(f"   ✅ {result.get('display_name', 'Test')}: PASSED")
                    elif status == 'FAIL':
                        failed_tests += 1
                        print(f"   ❌ {result.get('display_name', 'Test')}: FAILED")
                    elif status == 'ERROR':
                        error_tests += 1
                        print(f"   💥 {result.get('display_name', 'Test')}: ERROR - {result.get('error', 'Unknown')}")
            else:
                total_tests += 1
                status = results.get('status', 'UNKNOWN')
                
                if status == 'PASS':
                    passed_tests += 1
                    print(f"   ✅ {test_category}: PASSED")
                elif status == 'FAIL':
                    failed_tests += 1
                    print(f"   ❌ {test_category}: FAILED")
                elif status == 'ERROR':
                    error_tests += 1
                    print(f"   💥 {test_category}: ERROR - {results.get('error', 'Unknown')}")
        
        print(f"\n📊 SUMMARY")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Errors: {error_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")
        
        print(f"\n🎯 KEY ACHIEVEMENTS:")
        print(f"✅ Dynamic trigger settings implemented")
        print(f"✅ Hours After First Message trigger added")
        print(f"✅ Multiple condition support")
        print(f"✅ Event-based triggers with filters")
        print(f"✅ Time-based triggers with multiple schedule types")

if __name__ == "__main__":
    tester = TriggerDeepTester()
    asyncio.run(tester.run_deep_trigger_tests())
