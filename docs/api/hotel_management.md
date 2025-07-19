# Hotel Management API Documentation

This document provides comprehensive documentation for the Hotel Management API endpoints in the WhatsApp Hotel Bot application.

## Overview

The Hotel Management API provides endpoints for managing hotels, their configurations, and related operations. All endpoints support multi-tenancy and include comprehensive validation and error handling.

## Base URL

```
/api/v1/hotels
```

## Authentication

All endpoints require proper authentication. Include the hotel context in requests using the `X-Hotel-ID` header when applicable.

```http
X-Hotel-ID: 123e4567-e89b-12d3-a456-426614174000
```

## Endpoints

### 1. Create Hotel

Create a new hotel with configuration.

**Endpoint:** `POST /api/v1/hotels/`

**Request Body:**
```json
{
  "name": "Grand Hotel Example",
  "whatsapp_number": "+1234567890",
  "green_api_instance_id": "instance123",
  "green_api_token": "token123",
  "green_api_webhook_token": "webhook123",
  "settings": {
    "notifications": {
      "email_enabled": true,
      "sms_enabled": false,
      "webhook_enabled": true
    },
    "auto_responses": {
      "enabled": true,
      "greeting_message": "Welcome to Grand Hotel! How can we assist you today?",
      "business_hours": {
        "enabled": true,
        "start": "08:00",
        "end": "22:00",
        "timezone": "UTC"
      }
    },
    "sentiment_analysis": {
      "enabled": true,
      "threshold": 0.3,
      "alert_negative": true
    },
    "language": {
      "primary": "en",
      "supported": ["en", "es", "fr"]
    }
  },
  "is_active": true
}
```

**Response (201 Created):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Grand Hotel Example",
  "whatsapp_number": "+1234567890",
  "has_green_api_credentials": true,
  "is_active": true,
  "is_operational": true,
  "settings": {
    "notifications": {
      "email_enabled": true,
      "sms_enabled": false,
      "webhook_enabled": true
    },
    "auto_responses": {
      "enabled": true,
      "greeting_message": "Welcome to Grand Hotel! How can we assist you today?",
      "business_hours": {
        "enabled": true,
        "start": "08:00",
        "end": "22:00",
        "timezone": "UTC"
      }
    },
    "sentiment_analysis": {
      "enabled": true,
      "threshold": 0.3,
      "alert_negative": true
    },
    "language": {
      "primary": "en",
      "supported": ["en", "es", "fr"]
    }
  },
  "created_at": "2023-07-11T10:00:00Z",
  "updated_at": "2023-07-11T10:00:00Z"
}
```

### 2. Get Hotel

Retrieve a specific hotel by ID.

**Endpoint:** `GET /api/v1/hotels/{hotel_id}`

**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Grand Hotel Example",
  "whatsapp_number": "+1234567890",
  "has_green_api_credentials": true,
  "is_active": true,
  "is_operational": true,
  "settings": {
    "notifications": {
      "email_enabled": true,
      "sms_enabled": false,
      "webhook_enabled": true
    }
  },
  "created_at": "2023-07-11T10:00:00Z",
  "updated_at": "2023-07-11T10:00:00Z"
}
```

### 3. Update Hotel

Update hotel information.

**Endpoint:** `PUT /api/v1/hotels/{hotel_id}`

**Request Body:**
```json
{
  "name": "Updated Grand Hotel",
  "is_active": false
}
```

**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Updated Grand Hotel",
  "whatsapp_number": "+1234567890",
  "has_green_api_credentials": true,
  "is_active": false,
  "is_operational": false,
  "settings": {
    "notifications": {
      "email_enabled": true,
      "sms_enabled": false,
      "webhook_enabled": true
    }
  },
  "created_at": "2023-07-11T10:00:00Z",
  "updated_at": "2023-07-11T10:30:00Z"
}
```

### 4. Delete Hotel

Delete a hotel.

**Endpoint:** `DELETE /api/v1/hotels/{hotel_id}`

**Response (204 No Content)**

### 5. Search Hotels

Search and filter hotels with pagination.

**Endpoint:** `GET /api/v1/hotels/`

**Query Parameters:**
- `name` (optional): Filter by hotel name
- `whatsapp_number` (optional): Filter by WhatsApp number
- `is_active` (optional): Filter by active status
- `has_green_api_credentials` (optional): Filter by Green API credentials
- `page` (optional, default: 1): Page number
- `size` (optional, default: 10): Page size
- `sort_by` (optional, default: "name"): Sort field
- `sort_order` (optional, default: "asc"): Sort order

**Example Request:**
```http
GET /api/v1/hotels/?name=Grand&is_active=true&page=1&size=10&sort_by=name&sort_order=asc
```

**Response (200 OK):**
```json
{
  "hotels": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Grand Hotel Example",
      "whatsapp_number": "+1234567890",
      "has_green_api_credentials": true,
      "is_active": true,
      "is_operational": true,
      "created_at": "2023-07-11T10:00:00Z",
      "updated_at": "2023-07-11T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 10,
  "pages": 1
}
```

### 6. Get Active Hotels

Get all active hotels.

**Endpoint:** `GET /api/v1/hotels/active`

**Response (200 OK):**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Grand Hotel Example",
    "whatsapp_number": "+1234567890",
    "has_green_api_credentials": true,
    "is_active": true,
    "is_operational": true,
    "created_at": "2023-07-11T10:00:00Z",
    "updated_at": "2023-07-11T10:00:00Z"
  }
]
```

### 7. Get Operational Hotels

Get all operational hotels (active with Green API credentials).

**Endpoint:** `GET /api/v1/hotels/operational`

**Response (200 OK):**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Grand Hotel Example",
    "whatsapp_number": "+1234567890",
    "has_green_api_credentials": true,
    "is_active": true,
    "is_operational": true,
    "created_at": "2023-07-11T10:00:00Z",
    "updated_at": "2023-07-11T10:00:00Z"
  }
]
```

### 8. Get Hotel by WhatsApp Number

Retrieve hotel by WhatsApp number.

**Endpoint:** `GET /api/v1/hotels/whatsapp/{whatsapp_number}`

**Example:** `GET /api/v1/hotels/whatsapp/%2B1234567890`

**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Grand Hotel Example",
  "whatsapp_number": "+1234567890",
  "has_green_api_credentials": true,
  "is_active": true,
  "is_operational": true,
  "created_at": "2023-07-11T10:00:00Z",
  "updated_at": "2023-07-11T10:00:00Z"
}
```

### 9. Update Hotel Configuration

Update hotel configuration settings.

**Endpoint:** `PATCH /api/v1/hotels/{hotel_id}/config`

**Request Body:**
```json
{
  "settings": {
    "notifications": {
      "email_enabled": false,
      "sms_enabled": true
    },
    "sentiment_analysis": {
      "threshold": 0.5
    }
  },
  "merge": true
}
```

**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Grand Hotel Example",
  "settings": {
    "notifications": {
      "email_enabled": false,
      "sms_enabled": true,
      "webhook_enabled": true
    },
    "sentiment_analysis": {
      "enabled": true,
      "threshold": 0.5,
      "alert_negative": true
    }
  },
  "updated_at": "2023-07-11T11:00:00Z"
}
```

### 10. Update Hotel Status

Update hotel active status.

**Endpoint:** `PATCH /api/v1/hotels/{hotel_id}/status`

**Request Body:**
```json
{
  "is_active": false,
  "reason": "Maintenance scheduled"
}
```

**Response (200 OK):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Grand Hotel Example",
  "is_active": false,
  "is_operational": false,
  "updated_at": "2023-07-11T11:30:00Z"
}
```

## Error Responses

### Validation Error (422)
```json
{
  "detail": [
    {
      "loc": ["body", "whatsapp_number"],
      "msg": "WhatsApp number must be a valid international phone number",
      "type": "value_error"
    }
  ]
}
```

### Not Found (404)
```json
{
  "detail": "Hotel not found"
}
```

### Conflict (409)
```json
{
  "detail": "Hotel with WhatsApp number +1234567890 already exists"
}
```

### Internal Server Error (500)
```json
{
  "detail": "Failed to create hotel"
}
```

## Configuration Schema

### Notification Settings
```json
{
  "notifications": {
    "email_enabled": true,
    "sms_enabled": false,
    "webhook_enabled": true
  }
}
```

### Auto Response Settings
```json
{
  "auto_responses": {
    "enabled": true,
    "greeting_message": "Welcome message",
    "business_hours": {
      "enabled": true,
      "start": "09:00",
      "end": "18:00",
      "timezone": "UTC"
    }
  }
}
```

### Sentiment Analysis Settings
```json
{
  "sentiment_analysis": {
    "enabled": true,
    "threshold": 0.3,
    "alert_negative": true
  }
}
```

### Language Settings
```json
{
  "language": {
    "primary": "en",
    "supported": ["en", "es", "fr"]
  }
}
```

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- 100 requests per minute per IP address
- 1000 requests per hour per authenticated user

## Best Practices

1. **Always validate data** before sending requests
2. **Use appropriate HTTP methods** (GET for retrieval, POST for creation, etc.)
3. **Handle errors gracefully** and provide meaningful error messages
4. **Implement retry logic** for transient failures
5. **Use pagination** for large result sets
6. **Cache responses** when appropriate to reduce API calls
7. **Monitor rate limits** to avoid being throttled

## SDK Examples

### Python
```python
import requests

# Create hotel
hotel_data = {
    "name": "My Hotel",
    "whatsapp_number": "+1234567890",
    "is_active": True
}

response = requests.post(
    "https://api.example.com/api/v1/hotels/",
    json=hotel_data,
    headers={"Authorization": "Bearer your-token"}
)

if response.status_code == 201:
    hotel = response.json()
    print(f"Created hotel: {hotel['id']}")
```

### JavaScript
```javascript
// Create hotel
const hotelData = {
  name: "My Hotel",
  whatsapp_number: "+1234567890",
  is_active: true
};

const response = await fetch('/api/v1/hotels/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your-token'
  },
  body: JSON.stringify(hotelData)
});

if (response.ok) {
  const hotel = await response.json();
  console.log(`Created hotel: ${hotel.id}`);
}
```

## Admin Interface Routes

### DeepSeek AI Management

**Standalone DeepSeek Testing Interface**
- **Route:** `GET /api/v1/admin/deepseek-testing`
- **Description:** Standalone page for testing DeepSeek AI functionality
- **Features:**
  - Sentiment analysis testing
  - AI response generation
  - Live chat demo
  - Trigger system testing
- **Template:** `app/templates/deepseek_testing.html`
- **Access:** Direct URL, no menu navigation required

**Standalone AI Configuration Interface**
- **Route:** `GET /api/v1/admin/ai-configuration`
- **Description:** Standalone page for configuring DeepSeek AI settings
- **Features:**
  - API key management
  - Model selection and parameters
  - System prompt configuration
  - Response testing
  - Usage statistics
- **Template:** `app/templates/ai_configuration.html`
- **Access:** Direct URL, no menu navigation required

**Main Admin Dashboard**
- **Route:** `GET /api/v1/admin/dashboard`
- **Description:** Main admin interface with navigation menu
- **Features:**
  - Hotels management (restored functionality)
  - Triggers management (restored functionality)
  - Templates, Analytics, Monitoring
  - Links to standalone DeepSeek pages
- **Template:** `app/templates/admin_dashboard.html`

## Support

For additional support or questions about the Hotel Management API, please refer to the main documentation or contact the development team.
