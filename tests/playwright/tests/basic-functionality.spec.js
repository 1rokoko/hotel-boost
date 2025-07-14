const { test, expect } = require('@playwright/test');

test.describe('Basic Functionality Tests', () => {
  test('should load home page successfully', async ({ page }) => {
    await page.goto('/');
    
    // Check that we get a JSON response
    const content = await page.textContent('body');
    const data = JSON.parse(content);
    
    expect(data).toHaveProperty('message', 'WhatsApp Hotel Bot API');
    expect(data).toHaveProperty('version', '1.0.0');
    expect(data).toHaveProperty('status', 'running');
  });

  test('should load admin dashboard HTML', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Check page title
    await expect(page).toHaveTitle(/WhatsApp Hotel Bot - Admin Dashboard/);
    
    // Check main heading
    await expect(page.locator('h4')).toContainText('Hotel Bot Admin Dashboard');
    
    // Check navigation sidebar
    await expect(page.locator('.sidebar')).toBeVisible();
    
    // Check main content area
    await expect(page.locator('.main-content')).toBeVisible();
    
    // Check that we have navigation items
    await expect(page.locator('.nav-item')).toHaveCount(5);
    
    // Check specific navigation items
    await expect(page.locator('.nav-item').getByText('Dashboard')).toBeVisible();
    await expect(page.locator('.nav-item').getByText('Hotels')).toBeVisible();
    await expect(page.locator('.nav-item').getByText('Messages')).toBeVisible();
    await expect(page.locator('.nav-item').getByText('Analytics')).toBeVisible();
    await expect(page.locator('.nav-item').getByText('Settings')).toBeVisible();
  });

  test('should display system metrics', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Check that metrics are displayed
    await expect(page.getByText('Active Hotels: 5')).toBeVisible();
    await expect(page.getByText('Messages Today: 127')).toBeVisible();
    await expect(page.getByText('Response Rate: 98%')).toBeVisible();
    await expect(page.getByText('Avg Response Time: 2.3s')).toBeVisible();
  });

  test('should display recent activity', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Check recent activity section
    await expect(page.getByText('Recent Activity')).toBeVisible();
    await expect(page.getByText('Hotel "Grand Plaza" connected successfully')).toBeVisible();
    await expect(page.getByText('New message from guest +1234567890')).toBeVisible();
    await expect(page.getByText('AI response generated for Hotel "Ocean View"')).toBeVisible();
  });

  test('should display hotel configuration status', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Check hotel configuration section
    await expect(page.getByText('Hotel Configuration')).toBeVisible();
    await expect(page.getByText('Total Hotels: 5')).toBeVisible();
    await expect(page.getByText('Green API Configured: 5/5')).toBeVisible();
    await expect(page.getByText('DeepSeek AI Configured: 5/5')).toBeVisible();
    await expect(page.getByText('All systems operational')).toBeVisible();
  });

  test('should have responsive design', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Test desktop view
    await page.setViewportSize({ width: 1200, height: 800 });
    await expect(page.locator('.sidebar')).toBeVisible();
    await expect(page.locator('.main-content')).toBeVisible();
    
    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page.locator('.sidebar')).toBeVisible();
    await expect(page.locator('.main-content')).toBeVisible();
  });

  test('should handle navigation hover effects', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Test hover on navigation items
    const navItem = page.locator('.nav-item').first();
    await navItem.hover();
    
    // Check that hover styles are applied (background color change)
    const backgroundColor = await navItem.evaluate(el => 
      window.getComputedStyle(el).backgroundColor
    );
    
    // Should have some background color (not transparent)
    expect(backgroundColor).not.toBe('rgba(0, 0, 0, 0)');
  });

  test('should display cards with proper styling', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Check that cards are visible and styled
    const cards = page.locator('.card');
    await expect(cards).toHaveCount(3);
    
    // Check first card (System Overview)
    const firstCard = cards.first();
    await expect(firstCard).toBeVisible();
    
    // Check that cards have proper styling
    const cardStyle = await firstCard.evaluate(el => ({
      background: window.getComputedStyle(el).backgroundColor,
      padding: window.getComputedStyle(el).padding,
      borderRadius: window.getComputedStyle(el).borderRadius
    }));
    
    expect(cardStyle.background).not.toBe('rgba(0, 0, 0, 0)');
    expect(cardStyle.padding).not.toBe('0px');
    expect(cardStyle.borderRadius).not.toBe('0px');
  });

  test('should display metrics with proper styling', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Check metric elements
    const metrics = page.locator('.metric');
    await expect(metrics).toHaveCount(4);
    
    // Check that metrics have proper styling
    const metricStyle = await metrics.first().evaluate(el => ({
      background: window.getComputedStyle(el).backgroundColor,
      color: window.getComputedStyle(el).color,
      borderRadius: window.getComputedStyle(el).borderRadius
    }));
    
    expect(metricStyle.background).not.toBe('rgba(0, 0, 0, 0)');
    expect(metricStyle.color).not.toBe('rgb(0, 0, 0)');
    expect(metricStyle.borderRadius).not.toBe('0px');
  });

  test('should load quickly', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/api/v1/admin/dashboard');
    const endTime = Date.now();
    
    // Should load within 2 seconds
    expect(endTime - startTime).toBeLessThan(2000);
    
    // Check that content is visible
    await expect(page.locator('h4')).toBeVisible();
  });

  test('should have proper page structure', async ({ page }) => {
    await page.goto('/api/v1/admin/dashboard');
    
    // Check HTML structure
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.locator('meta[charset="UTF-8"]')).toBeAttached();
    await expect(page.locator('meta[name="viewport"]')).toBeAttached();
    
    // Check main container structure
    await expect(page.locator('.container')).toBeVisible();
    await expect(page.locator('.sidebar')).toBeVisible();
    await expect(page.locator('.main-content')).toBeVisible();
  });
});

test.describe('API Integration Tests', () => {
  test('should fetch hotels list successfully', async ({ request }) => {
    const response = await request.get('/api/v1/hotels');
    
    expect(response.status()).toBe(200);
    
    const hotels = await response.json();
    expect(Array.isArray(hotels)).toBeTruthy();
    expect(hotels.length).toBeGreaterThan(0);
    
    // Check hotel structure
    const hotel = hotels[0];
    expect(hotel).toHaveProperty('id');
    expect(hotel).toHaveProperty('name');
    expect(hotel).toHaveProperty('whatsapp_number');
    expect(hotel).toHaveProperty('is_active');
  });

  test('should fetch dashboard data successfully', async ({ request }) => {
    const response = await request.get('/api/v1/admin/dashboard/data');
    
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data).toHaveProperty('status', 'success');
    expect(data).toHaveProperty('data');
    expect(data.data).toHaveProperty('features');
    expect(Array.isArray(data.data.features)).toBeTruthy();
  });

  test('should handle health check', async ({ request }) => {
    const response = await request.get('/health');
    
    expect(response.status()).toBe(200);
    
    const health = await response.json();
    expect(health).toHaveProperty('status', 'healthy');
    expect(health).toHaveProperty('service', 'WhatsApp Hotel Bot');
    expect(health).toHaveProperty('features');
  });

  test('should handle performance status', async ({ request }) => {
    const response = await request.get('/api/v1/performance/status');
    
    expect(response.status()).toBe(200);
    
    const performance = await response.json();
    expect(performance).toHaveProperty('status', 'optimal');
    expect(performance).toHaveProperty('metrics');
    expect(performance).toHaveProperty('services');
  });
});

test.describe('Security Tests', () => {
  test('should include security headers', async ({ request }) => {
    const response = await request.get('/health');
    
    const headers = response.headers();
    expect(headers).toHaveProperty('x-content-type-options', 'nosniff');
    expect(headers).toHaveProperty('x-frame-options', 'DENY');
    expect(headers).toHaveProperty('x-xss-protection', '1; mode=block');
  });

  test('should handle CORS properly', async ({ request }) => {
    const response = await request.get('/health', {
      headers: {
        'Origin': 'http://localhost:3000'
      }
    });
    
    expect(response.status()).toBe(200);
    // CORS headers should be present for allowed origins
  });
});
