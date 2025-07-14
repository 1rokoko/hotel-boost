const { test, expect } = require('@playwright/test');

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to admin dashboard
    await page.goto('/api/v1/admin/dashboard');
  });

  test('should load admin dashboard successfully', async ({ page }) => {
    // Check page title
    await expect(page).toHaveTitle(/WhatsApp Hotel Bot - Admin Dashboard/);
    
    // Check main heading
    await expect(page.locator('h4')).toContainText('Hotel Bot Admin');
    
    // Check navigation sidebar
    await expect(page.locator('.sidebar')).toBeVisible();
    
    // Check main content area
    await expect(page.locator('.main-content')).toBeVisible();
  });

  test('should display navigation menu correctly', async ({ page }) => {
    // Check all navigation items are present
    const navItems = [
      'Dashboard',
      'Hotels', 
      'Users',
      'Analytics',
      'Monitoring',
      'Security'
    ];

    for (const item of navItems) {
      await expect(page.locator('.sidebar').getByText(item)).toBeVisible();
    }
  });

  test('should display stats cards with data', async ({ page }) => {
    // Wait for data to load
    await page.waitForTimeout(2000);
    
    // Check stats cards are visible
    await expect(page.locator('.stat-card').first()).toBeVisible();
    
    // Check that stats show actual numbers (not "-")
    const totalHotels = page.locator('#total-hotels');
    await expect(totalHotels).not.toHaveText('-');
    
    // Should show at least 1 hotel from our test data
    await expect(totalHotels).toHaveText('1');
  });

  test('should navigate between sections', async ({ page }) => {
    // Test navigation to Hotels section
    await page.click('[data-section="hotels"]');
    await expect(page.locator('#hotels-section')).toBeVisible();
    await expect(page.locator('#dashboard-section')).toBeHidden();
    
    // Test navigation to Analytics section
    await page.click('[data-section="analytics"]');
    await expect(page.locator('#analytics-section')).toBeVisible();
    await expect(page.locator('#hotels-section')).toBeHidden();
    
    // Test navigation back to Dashboard
    await page.click('[data-section="dashboard"]');
    await expect(page.locator('#dashboard-section')).toBeVisible();
    await expect(page.locator('#analytics-section')).toBeHidden();
  });

  test('should display system status', async ({ page }) => {
    // Check system status section
    await expect(page.locator('#system-status')).toBeVisible();
    
    // Check that status badges are present
    const statusBadges = page.locator('.status-badge');
    await expect(statusBadges.first()).toBeVisible();
    
    // Check for "Active" status
    await expect(page.locator('.status-active')).toHaveCount.greaterThan(0);
  });

  test('should have working refresh functionality', async ({ page }) => {
    // Click refresh button
    const refreshBtn = page.locator('button:has-text("Refresh")');
    await expect(refreshBtn).toBeVisible();
    
    await refreshBtn.click();
    
    // Check that button shows loading state briefly
    await expect(refreshBtn).toContainText('Refreshing');
    
    // Wait for refresh to complete
    await page.waitForTimeout(1000);
    
    // Button should return to normal state
    await expect(refreshBtn).toContainText('Refresh');
  });

  test('should display charts', async ({ page }) => {
    // Check that chart containers are present
    await expect(page.locator('#messageChart')).toBeVisible();
    await expect(page.locator('#hotelChart')).toBeVisible();
    
    // Check chart titles
    await expect(page.getByText('Message Volume (Last 7 Days)')).toBeVisible();
    await expect(page.getByText('Hotel Activity')).toBeVisible();
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Check that sidebar is still accessible
    await expect(page.locator('.sidebar')).toBeVisible();
    
    // Check that main content adapts
    await expect(page.locator('.main-content')).toBeVisible();
    
    // Check that stats cards stack properly
    const statsCards = page.locator('.stat-card');
    await expect(statsCards.first()).toBeVisible();
  });

  test('should handle keyboard navigation', async ({ page }) => {
    // Test keyboard shortcut for refresh (Ctrl+R)
    await page.keyboard.press('Control+r');
    
    // Should trigger refresh functionality
    await page.waitForTimeout(500);
    
    // Test number key navigation (1 for dashboard)
    await page.keyboard.press('1');
    await expect(page.locator('#dashboard-section')).toBeVisible();
    
    // Test number key navigation (2 for hotels)
    await page.keyboard.press('2');
    await expect(page.locator('#hotels-section')).toBeVisible();
  });

  test('should load data from API endpoints', async ({ page }) => {
    // Intercept API calls
    await page.route('/api/v1/admin/dashboard/data', async route => {
      const response = await route.fetch();
      const json = await response.json();
      
      // Verify API response structure
      expect(json).toHaveProperty('status', 'success');
      expect(json).toHaveProperty('data');
      expect(json.data).toHaveProperty('features');
      
      await route.fulfill({ response });
    });
    
    await page.route('/api/v1/hotels', async route => {
      const response = await route.fetch();
      const json = await response.json();
      
      // Should return array of hotels
      expect(Array.isArray(json)).toBeTruthy();
      
      await route.fulfill({ response });
    });
    
    await page.route('/health', async route => {
      const response = await route.fetch();
      const json = await response.json();
      
      // Verify health check response
      expect(json).toHaveProperty('status');
      expect(json).toHaveProperty('service');
      
      await route.fulfill({ response });
    });
    
    // Reload page to trigger API calls
    await page.reload();
    
    // Wait for data to load
    await page.waitForTimeout(2000);
  });
});
