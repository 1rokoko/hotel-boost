const { test, expect } = require('@playwright/test');

test.describe('API Endpoints', () => {
  test.describe('Health Check', () => {
    test('should return healthy status', async ({ request }) => {
      const response = await request.get('/health');
      
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('status');
      expect(data).toHaveProperty('service', 'WhatsApp Hotel Bot');
      expect(data).toHaveProperty('version');
      expect(data).toHaveProperty('environment');
      expect(data).toHaveProperty('features');
    });
  });

  test.describe('Admin Dashboard API', () => {
    test('should return dashboard data', async ({ request }) => {
      const response = await request.get('/api/v1/admin/dashboard/data');
      
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('status', 'success');
      expect(data).toHaveProperty('data');
      expect(data.data).toHaveProperty('message');
      expect(data.data).toHaveProperty('features');
      expect(Array.isArray(data.data.features)).toBeTruthy();
    });

    test('should serve HTML dashboard', async ({ request }) => {
      const response = await request.get('/api/v1/admin/dashboard');
      
      expect(response.status()).toBe(200);
      expect(response.headers()['content-type']).toContain('text/html');
      
      const html = await response.text();
      expect(html).toContain('WhatsApp Hotel Bot - Admin Dashboard');
      expect(html).toContain('Hotel Bot Admin');
    });
  });

  test.describe('Hotels API', () => {
    test('should return hotels list', async ({ request }) => {
      const response = await request.get('/api/v1/hotels');
      
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(Array.isArray(data)).toBeTruthy();
      
      // Should have at least one test hotel
      expect(data.length).toBeGreaterThanOrEqual(1);
      
      if (data.length > 0) {
        const hotel = data[0];
        expect(hotel).toHaveProperty('id');
        expect(hotel).toHaveProperty('name');
        expect(hotel).toHaveProperty('whatsapp_number');
      }
    });

    test('should create new hotel', async ({ request }) => {
      const newHotel = {
        name: 'Test Hotel API',
        whatsapp_number: '+1234567891',
        green_api_instance_id: 'test_instance',
        green_api_token: 'test_token'
      };

      const response = await request.post('/api/v1/hotels', {
        data: newHotel
      });

      expect(response.status()).toBe(201);
      
      const data = await response.json();
      expect(data).toHaveProperty('id');
      expect(data).toHaveProperty('name', newHotel.name);
      expect(data).toHaveProperty('whatsapp_number', newHotel.whatsapp_number);
    });

    test('should get hotel by ID', async ({ request }) => {
      // First get the list to find an existing hotel
      const listResponse = await request.get('/api/v1/hotels');
      const hotels = await listResponse.json();
      
      if (hotels.length > 0) {
        const hotelId = hotels[0].id;
        
        const response = await request.get(`/api/v1/hotels/${hotelId}`);
        expect(response.status()).toBe(200);
        
        const data = await response.json();
        expect(data).toHaveProperty('id', hotelId);
        expect(data).toHaveProperty('name');
        expect(data).toHaveProperty('whatsapp_number');
      }
    });

    test('should handle non-existent hotel', async ({ request }) => {
      const response = await request.get('/api/v1/hotels/non-existent-id');
      expect(response.status()).toBe(404);
    });
  });

  test.describe('Webhooks', () => {
    test('should handle Green API webhook', async ({ request }) => {
      const webhookData = {
        typeWebhook: 'incomingMessageReceived',
        instanceData: {
          idInstance: 'test_instance',
          wid: 'test_wid'
        },
        messageData: {
          idMessage: 'test_message_id',
          timestamp: Date.now(),
          typeMessage: 'textMessage',
          chatId: '1234567890@c.us',
          textMessageData: {
            textMessage: 'Hello, this is a test message'
          }
        }
      };

      const response = await request.post('/api/v1/webhooks/green-api', {
        data: webhookData
      });

      // Should accept webhook (even if processing fails due to missing setup)
      expect([200, 202, 400]).toContain(response.status());
    });

    test('should reject invalid webhook data', async ({ request }) => {
      const invalidData = {
        invalid: 'data'
      };

      const response = await request.post('/api/v1/webhooks/green-api', {
        data: invalidData
      });

      expect([400, 422]).toContain(response.status());
    });
  });

  test.describe('Documentation', () => {
    test('should serve OpenAPI docs', async ({ request }) => {
      const response = await request.get('/docs');
      
      expect(response.status()).toBe(200);
      expect(response.headers()['content-type']).toContain('text/html');
      
      const html = await response.text();
      expect(html).toContain('swagger');
      expect(html).toContain('WhatsApp Hotel Bot');
    });

    test('should serve ReDoc documentation', async ({ request }) => {
      const response = await request.get('/redoc');
      
      expect(response.status()).toBe(200);
      expect(response.headers()['content-type']).toContain('text/html');
      
      const html = await response.text();
      expect(html).toContain('redoc');
      expect(html).toContain('WhatsApp Hotel Bot');
    });

    test('should serve OpenAPI JSON schema', async ({ request }) => {
      const response = await request.get('/openapi.json');
      
      expect(response.status()).toBe(200);
      expect(response.headers()['content-type']).toContain('application/json');
      
      const schema = await response.json();
      expect(schema).toHaveProperty('openapi');
      expect(schema).toHaveProperty('info');
      expect(schema.info).toHaveProperty('title', 'WhatsApp Hotel Bot');
    });
  });

  test.describe('Error Handling', () => {
    test('should handle 404 for non-existent routes', async ({ request }) => {
      const response = await request.get('/api/v1/non-existent-endpoint');
      expect(response.status()).toBe(404);
    });

    test('should handle invalid JSON in POST requests', async ({ request }) => {
      const response = await request.post('/api/v1/hotels', {
        data: 'invalid json string',
        headers: {
          'content-type': 'application/json'
        }
      });
      
      expect([400, 422]).toContain(response.status());
    });

    test('should handle missing required fields', async ({ request }) => {
      const incompleteHotel = {
        name: 'Incomplete Hotel'
        // Missing required whatsapp_number
      };

      const response = await request.post('/api/v1/hotels', {
        data: incompleteHotel
      });

      expect([400, 422]).toContain(response.status());
    });
  });

  test.describe('Security Headers', () => {
    test('should include security headers', async ({ request }) => {
      const response = await request.get('/health');
      
      const headers = response.headers();
      expect(headers).toHaveProperty('x-content-type-options', 'nosniff');
      expect(headers).toHaveProperty('x-frame-options', 'DENY');
      expect(headers).toHaveProperty('x-xss-protection', '1; mode=block');
    });
  });

  test.describe('Performance', () => {
    test('should respond quickly to health checks', async ({ request }) => {
      const startTime = Date.now();
      const response = await request.get('/health');
      const endTime = Date.now();
      
      expect(response.status()).toBe(200);
      expect(endTime - startTime).toBeLessThan(1000); // Should respond within 1 second
    });

    test('should handle concurrent requests', async ({ request }) => {
      const promises = Array.from({ length: 10 }, () => 
        request.get('/health')
      );
      
      const responses = await Promise.all(promises);
      
      responses.forEach(response => {
        expect(response.status()).toBe(200);
      });
    });
  });
});
