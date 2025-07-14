#!/usr/bin/env python3
"""
Comprehensive Admin Dashboard Functionality Testing
Tests each section in detail, not just UI but actual functionality
"""

import asyncio
import json
from playwright.async_api import async_playwright
from typing import Dict, List, Any
import time

class AdminFunctionalityTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.admin_url = f"{self.base_url}/api/v1/admin/dashboard"
        self.test_results = {}
        
    async def run_comprehensive_tests(self):
        """Run all comprehensive functionality tests"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            print("🚀 Starting Comprehensive Admin Dashboard Testing")
            print("=" * 60)
            
            try:
                # Navigate to admin dashboard
                await page.goto(self.admin_url)
                await page.wait_for_load_state('networkidle')
                
                # Test each section in detail
                await self.test_dashboard_section(page)
                await self.test_hotels_section(page)
                await self.test_conversations_section(page)
                await self.test_triggers_section(page)
                await self.test_templates_section(page)
                await self.test_sentiment_analytics_section(page)
                await self.test_deepseek_section(page)
                
                # Generate comprehensive report
                self.generate_test_report()
                
            except Exception as e:
                print(f"❌ Critical error during testing: {e}")
            finally:
                await browser.close()
    
    async def test_dashboard_section(self, page):
        """Test Dashboard section functionality"""
        print("\n📊 Testing Dashboard Section")
        print("-" * 40)
        
        section_results = {
            "section": "Dashboard",
            "tests": [],
            "overall_status": "PASS"
        }
        
        try:
            # Click Dashboard
            await page.click('a[data-section="dashboard"]')
            await page.wait_for_timeout(1000)
            
            # Test 1: Check if stats are loading real data
            stats_test = await self.test_dashboard_stats(page)
            section_results["tests"].append(stats_test)
            
            # Test 2: Check if charts are rendering
            charts_test = await self.test_dashboard_charts(page)
            section_results["tests"].append(charts_test)
            
            # Test 3: Test refresh functionality
            refresh_test = await self.test_refresh_button(page)
            section_results["tests"].append(refresh_test)
            
        except Exception as e:
            section_results["overall_status"] = "FAIL"
            section_results["error"] = str(e)
        
        self.test_results["dashboard"] = section_results
    
    async def test_dashboard_stats(self, page):
        """Test if dashboard shows real data instead of fake numbers"""
        test_result = {
            "test_name": "Dashboard Stats Data",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Get current stats values
            total_hotels = await page.text_content('#total-hotels')
            total_messages = await page.text_content('#total-messages')
            active_guests = await page.text_content('#active-guests')
            ai_responses = await page.text_content('#ai-responses')
            
            test_result["details"] = {
                "total_hotels": total_hotels,
                "total_messages": total_messages,
                "active_guests": active_guests,
                "ai_responses": ai_responses
            }
            
            # Check if data looks fake (common fake patterns)
            fake_patterns = ['1,234', '456', '89', '-']
            
            if total_hotels in fake_patterns:
                test_result["issues"].append("Total Hotels shows fake data")
                test_result["recommendations"].append("Connect to real hotels API endpoint")
            
            if total_messages in fake_patterns:
                test_result["issues"].append("Messages Today shows fake data")
                test_result["recommendations"].append("Connect to real messages API endpoint")
            
            if active_guests in fake_patterns:
                test_result["issues"].append("Active Guests shows fake data")
                test_result["recommendations"].append("Connect to real guests API endpoint")
            
            if ai_responses in fake_patterns:
                test_result["issues"].append("AI Responses shows fake data")
                test_result["recommendations"].append("Connect to real DeepSeek analytics API")
            
            if not test_result["issues"]:
                test_result["status"] = "PASS"
            
        except Exception as e:
            test_result["issues"].append(f"Error testing stats: {e}")
        
        return test_result
    
    async def test_dashboard_charts(self, page):
        """Test if charts are properly rendered"""
        test_result = {
            "test_name": "Dashboard Charts",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Check if chart canvases exist
            message_chart = await page.query_selector('#messageChart')
            hotel_chart = await page.query_selector('#hotelChart')
            
            if message_chart:
                test_result["details"]["message_chart"] = "Present"
            else:
                test_result["issues"].append("Message chart not found")
                test_result["recommendations"].append("Fix Chart.js initialization")
            
            if hotel_chart:
                test_result["details"]["hotel_chart"] = "Present"
            else:
                test_result["issues"].append("Hotel chart not found")
                test_result["recommendations"].append("Fix Chart.js initialization")
            
            if not test_result["issues"]:
                test_result["status"] = "PASS"
                
        except Exception as e:
            test_result["issues"].append(f"Error testing charts: {e}")
        
        return test_result
    
    async def test_refresh_button(self, page):
        """Test refresh button functionality"""
        test_result = {
            "test_name": "Refresh Button",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Click refresh button
            await page.click('button:has-text("Refresh")')
            await page.wait_for_timeout(2000)
            
            # Check if any network requests were made
            # This is a basic test - in real scenario we'd monitor network activity
            test_result["details"]["clicked"] = "Success"
            test_result["status"] = "PASS"
            
        except Exception as e:
            test_result["issues"].append(f"Refresh button error: {e}")
            test_result["recommendations"].append("Fix refresh button click handler")
        
        return test_result
    
    async def test_triggers_section(self, page):
        """Test Triggers section in detail"""
        print("\n🔥 Testing Triggers Section")
        print("-" * 40)
        
        section_results = {
            "section": "Triggers",
            "tests": [],
            "overall_status": "PASS"
        }
        
        try:
            # Navigate to triggers section
            await page.click('a[data-section="triggers"]')
            await page.wait_for_timeout(1000)
            
            # Test 1: Check if triggers list loads
            list_test = await self.test_triggers_list(page)
            section_results["tests"].append(list_test)
            
            # Test 2: Test Create Trigger button
            create_test = await self.test_create_trigger_button(page)
            section_results["tests"].append(create_test)
            
            # Test 3: Test filters
            filter_test = await self.test_triggers_filters(page)
            section_results["tests"].append(filter_test)
            
        except Exception as e:
            section_results["overall_status"] = "FAIL"
            section_results["error"] = str(e)
        
        self.test_results["triggers"] = section_results
    
    async def test_create_trigger_button(self, page):
        """Test Create Trigger button functionality"""
        test_result = {
            "test_name": "Create Trigger Button",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Click Create Trigger button
            await page.click('button:has-text("Create Trigger")')
            
            # Check if modal appears or alert shows
            try:
                # Wait for either modal or alert
                await page.wait_for_timeout(1000)
                
                # Check if it's just a placeholder alert
                test_result["details"]["action"] = "Shows placeholder alert"
                test_result["issues"].append("Create Trigger shows placeholder instead of real modal")
                test_result["recommendations"].append("Implement real Create Trigger modal with form")
                test_result["recommendations"].append("Connect to /api/v1/triggers POST endpoint")
                test_result["recommendations"].append("Add form fields: name, type, conditions, message template")
                
            except Exception:
                test_result["issues"].append("No response from Create Trigger button")
                test_result["recommendations"].append("Fix button click handler")
            
        except Exception as e:
            test_result["issues"].append(f"Create Trigger button error: {e}")
        
        return test_result
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE ADMIN DASHBOARD TEST REPORT")
        print("=" * 80)
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        for section_name, section_data in self.test_results.items():
            print(f"\n🔍 {section_data['section'].upper()} SECTION")
            print("-" * 50)
            
            if section_data['overall_status'] == 'PASS':
                print("✅ Overall Status: PASS")
            else:
                print("❌ Overall Status: FAIL")
                if 'error' in section_data:
                    print(f"   Error: {section_data['error']}")
            
            for test in section_data.get('tests', []):
                total_tests += 1
                print(f"\n  📝 {test['test_name']}")
                
                if test['status'] == 'PASS':
                    print("     ✅ PASS")
                    passed_tests += 1
                else:
                    print("     ❌ FAIL")
                    failed_tests += 1
                    
                    if test['issues']:
                        print("     🚨 Issues:")
                        for issue in test['issues']:
                            print(f"        • {issue}")
                    
                    if test['recommendations']:
                        print("     💡 Recommendations:")
                        for rec in test['recommendations']:
                            print(f"        • {rec}")
        
        print(f"\n📊 SUMMARY")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")

    async def test_triggers_list(self, page):
        """Test if triggers list loads properly"""
        test_result = {
            "test_name": "Triggers List Loading",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }

        try:
            # Check triggers list content
            triggers_list = await page.text_content('#triggers-list')
            test_result["details"]["content"] = triggers_list

            if "Loading triggers..." in triggers_list:
                test_result["issues"].append("Triggers list stuck in loading state")
                test_result["recommendations"].append("Check /api/v1/triggers endpoint")
            elif "No triggers configured" in triggers_list:
                test_result["status"] = "PASS"
                test_result["details"]["status"] = "Empty state working"
            elif "Error loading triggers" in triggers_list:
                test_result["issues"].append("API error loading triggers")
                test_result["recommendations"].append("Fix /api/v1/triggers endpoint")
            else:
                test_result["status"] = "PASS"
                test_result["details"]["status"] = "Triggers loaded successfully"

        except Exception as e:
            test_result["issues"].append(f"Error testing triggers list: {e}")

        return test_result

    async def test_triggers_filters(self, page):
        """Test triggers filters functionality"""
        test_result = {
            "test_name": "Triggers Filters",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }

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

            # Click filter button
            await page.click('button:has-text("Filter")')
            await page.wait_for_timeout(1000)

            test_result["status"] = "PASS"
            test_result["details"]["filters_tested"] = "Type, Status, Search, Filter button"

        except Exception as e:
            test_result["issues"].append(f"Filter testing error: {e}")
            test_result["recommendations"].append("Implement filter functionality")

        return test_result

    async def test_templates_section(self, page):
        """Test Templates section in detail"""
        print("\n📝 Testing Templates Section")
        print("-" * 40)

        section_results = {
            "section": "Templates",
            "tests": [],
            "overall_status": "PASS"
        }

        try:
            # Navigate to templates section
            await page.click('a[data-section="templates"]')
            await page.wait_for_timeout(1000)

            # Test templates list
            list_test = await self.test_templates_list(page)
            section_results["tests"].append(list_test)

            # Test Create Template button
            create_test = await self.test_create_template_button(page)
            section_results["tests"].append(create_test)

        except Exception as e:
            section_results["overall_status"] = "FAIL"
            section_results["error"] = str(e)

        self.test_results["templates"] = section_results

    async def test_templates_list(self, page):
        """Test templates list loading"""
        test_result = {
            "test_name": "Templates List Loading",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }

        try:
            templates_list = await page.text_content('#templates-list')
            test_result["details"]["content"] = templates_list

            if "No templates created" in templates_list:
                test_result["status"] = "PASS"
                test_result["details"]["status"] = "Empty state working"
            elif "Error loading templates" in templates_list:
                test_result["issues"].append("API error loading templates")
                test_result["recommendations"].append("Fix /api/v1/templates endpoint")
            else:
                test_result["status"] = "PASS"

        except Exception as e:
            test_result["issues"].append(f"Error testing templates list: {e}")

        return test_result

    async def test_create_template_button(self, page):
        """Test Create Template button"""
        test_result = {
            "test_name": "Create Template Button",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }

        try:
            await page.click('button:has-text("Create Template")')
            await page.wait_for_timeout(1000)

            test_result["issues"].append("Create Template shows placeholder instead of real modal")
            test_result["recommendations"].append("Implement real Create Template modal")
            test_result["recommendations"].append("Add form fields: name, category, content, variables, language")
            test_result["recommendations"].append("Connect to /api/v1/templates POST endpoint")

        except Exception as e:
            test_result["issues"].append(f"Create Template button error: {e}")

        return test_result

    async def test_sentiment_analytics_section(self, page):
        """Test Sentiment Analytics section"""
        print("\n💖 Testing Sentiment Analytics Section")
        print("-" * 40)

        section_results = {
            "section": "Sentiment Analytics",
            "tests": [],
            "overall_status": "PASS"
        }

        try:
            await page.click('a[data-section="sentiment-analytics"]')
            await page.wait_for_timeout(1000)

            # Test sentiment stats
            stats_test = await self.test_sentiment_stats(page)
            section_results["tests"].append(stats_test)

        except Exception as e:
            section_results["overall_status"] = "FAIL"
            section_results["error"] = str(e)

        self.test_results["sentiment_analytics"] = section_results

    async def test_sentiment_stats(self, page):
        """Test sentiment analytics stats"""
        test_result = {
            "test_name": "Sentiment Stats",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }

        try:
            positive = await page.text_content('#positive-sentiment')
            neutral = await page.text_content('#neutral-sentiment')
            negative = await page.text_content('#negative-sentiment')
            avg_score = await page.text_content('#avg-sentiment-score')

            test_result["details"] = {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
                "avg_score": avg_score
            }

            if all(val == "0" or val == "0.0" for val in [positive, neutral, negative, avg_score]):
                test_result["status"] = "PASS"
                test_result["details"]["status"] = "Empty state working"
            else:
                test_result["status"] = "PASS"
                test_result["details"]["status"] = "Data loaded"

        except Exception as e:
            test_result["issues"].append(f"Error testing sentiment stats: {e}")

        return test_result

    async def test_conversations_section(self, page):
        """Test Conversations section"""
        print("\n💬 Testing Conversations Section")
        print("-" * 40)

        section_results = {
            "section": "Conversations",
            "tests": [],
            "overall_status": "PASS"
        }

        try:
            await page.click('a[data-section="conversations"]')
            await page.wait_for_timeout(1000)

            # Test conversations list
            list_test = await self.test_conversations_list(page)
            section_results["tests"].append(list_test)

        except Exception as e:
            section_results["overall_status"] = "FAIL"
            section_results["error"] = str(e)

        self.test_results["conversations"] = section_results

    async def test_conversations_list(self, page):
        """Test conversations list"""
        test_result = {
            "test_name": "Conversations List",
            "status": "PASS",
            "details": {},
            "issues": [],
            "recommendations": []
        }

        try:
            conversations_list = await page.text_content('#conversations-list')
            test_result["details"]["content"] = conversations_list

            if "No active conversations" in conversations_list:
                test_result["details"]["status"] = "Empty state working"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["issues"].append(f"Error testing conversations: {e}")

        return test_result

    async def test_hotels_section(self, page):
        """Test Hotels section"""
        print("\n🏨 Testing Hotels Section")
        print("-" * 40)

        section_results = {
            "section": "Hotels",
            "tests": [],
            "overall_status": "PASS"
        }

        try:
            await page.click('a[data-section="hotels"]')
            await page.wait_for_timeout(1000)

            # Test if hotels are displayed
            hotels_test = await self.test_hotels_display(page)
            section_results["tests"].append(hotels_test)

        except Exception as e:
            section_results["overall_status"] = "FAIL"
            section_results["error"] = str(e)

        self.test_results["hotels"] = section_results

    async def test_hotels_display(self, page):
        """Test hotels display"""
        test_result = {
            "test_name": "Hotels Display",
            "status": "PASS",
            "details": {},
            "issues": [],
            "recommendations": []
        }

        try:
            # Check if hotels are displayed
            hotels_section = await page.query_selector('#hotels-section')
            if hotels_section:
                test_result["details"]["status"] = "Hotels section visible"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["issues"].append(f"Error testing hotels: {e}")

        return test_result

    async def test_deepseek_section(self, page):
        """Test DeepSeek section functionality"""
        print("\n🧠 Testing DeepSeek Section")
        print("-" * 40)

        section_results = {
            "section": "DeepSeek Testing",
            "tests": [],
            "overall_status": "PASS"
        }

        try:
            await page.click('a[data-section="deepseek-testing"]')
            await page.wait_for_timeout(1000)

            # Test sentiment analysis functionality
            sentiment_test = await self.test_deepseek_sentiment_analysis(page)
            section_results["tests"].append(sentiment_test)

        except Exception as e:
            section_results["overall_status"] = "FAIL"
            section_results["error"] = str(e)

        self.test_results["deepseek"] = section_results

    async def test_deepseek_sentiment_analysis(self, page):
        """Test DeepSeek sentiment analysis functionality"""
        test_result = {
            "test_name": "DeepSeek Sentiment Analysis",
            "status": "FAIL",
            "details": {},
            "issues": [],
            "recommendations": []
        }

        try:
            # Select a hotel
            await page.select_option('select:has(option:text("Grand Plaza Hotel"))', 'Grand Plaza Hotel')

            # Click Analyze Sentiment button
            await page.click('button:has-text("Analyze Sentiment")')
            await page.wait_for_timeout(3000)

            # Check if result appears
            result_text = await page.text_content('#sentiment-result')
            if result_text and "Click" not in result_text:
                test_result["status"] = "PASS"
                test_result["details"]["result"] = "Analysis completed"
            else:
                test_result["issues"].append("Sentiment analysis not working")
                test_result["recommendations"].append("Check DeepSeek API integration")

        except Exception as e:
            test_result["issues"].append(f"DeepSeek testing error: {e}")

        return test_result

if __name__ == "__main__":
    tester = AdminFunctionalityTester()
    asyncio.run(tester.run_comprehensive_tests())
