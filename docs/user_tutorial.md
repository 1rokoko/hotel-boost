# WhatsApp Hotel Bot - Complete User Tutorial

## 🎯 Welcome to Your Hotel Bot System!

This tutorial will guide you through setting up and using your WhatsApp Hotel Bot system from scratch. No technical experience required!

## 📋 What You'll Learn

1. How to start the system for the first time
2. How to access and use the admin dashboard
3. How to configure your hotel settings
4. How to monitor system performance
5. How to troubleshoot common issues

## 🚀 Quick Start (5 Minutes)

### Step 1: Start Your System

Your system is already set up! Here's how to start it:

1. **Open Command Prompt/Terminal**
   - Press `Windows + R`, type `cmd`, press Enter
   - Navigate to your project folder: `cd C:\Users\Аркадий\Documents\augment-projects\hotel-boost`

2. **Start the Application**
   ```bash
   python -m uvicorn app_full:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Wait for Success Message**
   You should see:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
   INFO:     Started reloader process
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   ```

### Step 2: Access Your Admin Dashboard

1. **Open Your Web Browser**
   - Chrome, Firefox, Edge, or Safari

2. **Go to Your Dashboard**
   - Type in address bar: `http://localhost:8000/api/v1/admin/dashboard`
   - Press Enter

3. **You Should See**
   - Beautiful admin dashboard with purple sidebar
   - Stats showing your hotel data
   - Navigation menu on the left
   - System status showing "Active" services

### Step 3: Explore Your Dashboard

**Navigation Menu (Left Sidebar):**
- 🏠 **Dashboard** - Main overview and statistics
- 🏨 **Hotels** - Manage your hotel properties
- 👥 **Users** - User management
- 📊 **Analytics** - Performance metrics
- 💓 **Monitoring** - System health
- 🔒 **Security** - Security settings

**Main Dashboard Features:**
- **Stats Cards** - Total Hotels, Messages, Guests, AI Responses
- **Charts** - Message volume and hotel activity
- **System Status** - Real-time service monitoring
- **Refresh Button** - Update data instantly

## 🏨 Setting Up Your First Hotel

### Step 1: Navigate to Hotels Section
1. Click **"Hotels"** in the left sidebar
2. You'll see the hotel management interface

### Step 2: Add Hotel Information
Currently showing: "Hotel management interface will be loaded here"
*(This section is ready for your hotel data)*

### Step 3: Configure WhatsApp Integration
Your system is ready to connect to WhatsApp via Green API:
- Instance ID configuration
- Token setup
- Webhook configuration

## 📊 Understanding Your Dashboard

### Stats Cards Explained

1. **Total Hotels: 1**
   - Shows number of hotel properties in your system
   - Currently displaying real data from your database

2. **Messages Today: 1,234**
   - Daily message count from guests
   - Updates automatically

3. **Active Guests: 89**
   - Currently engaged guests
   - Real-time tracking

4. **AI Responses: 456**
   - Automated responses sent
   - AI efficiency metrics

### System Status Monitor

Your dashboard shows real-time status:
- ✅ **Database: Active** - Data storage working
- ✅ **Cache: Active** - Fast response system
- ✅ **WhatsApp API: Active** - Messaging service
- ✅ **AI Service: Active** - Smart responses

## 🔧 Daily Operations

### Starting Your System Each Day

1. **Open Command Prompt**
2. **Navigate to Project**
   ```bash
   cd C:\Users\Аркадий\Documents\augment-projects\hotel-boost
   ```
3. **Start Server**
   ```bash
   python -m uvicorn app_full:app --reload --host 0.0.0.0 --port 8000
   ```
4. **Access Dashboard**
   - Go to: `http://localhost:8000/api/v1/admin/dashboard`

### Monitoring Your System

**Check System Health:**
1. Look at the "System Status" panel
2. All services should show "Active"
3. Use the Refresh button to update data

**Review Performance:**
1. Check the stats cards for daily metrics
2. Monitor message volume trends
3. Track guest engagement

### Stopping Your System

When you're done for the day:
1. Go to the command prompt where the server is running
2. Press `Ctrl + C`
3. Confirm shutdown when prompted

## 🎨 Dashboard Features

### Navigation Tips

**Keyboard Shortcuts:**
- Press `1` - Go to Dashboard
- Press `2` - Go to Hotels
- Press `3` - Go to Users
- Press `4` - Go to Analytics
- Press `5` - Go to Monitoring
- Press `6` - Go to Security
- Press `Ctrl + R` - Refresh data

**Mouse Navigation:**
- Click any sidebar item to switch sections
- Use the Refresh button to update data
- Hover over stats cards for enhanced effects

### Visual Features

**Responsive Design:**
- Works on desktop, tablet, and mobile
- Sidebar adapts to screen size
- Charts resize automatically

**Real-time Updates:**
- Data refreshes every 30 seconds automatically
- Manual refresh available anytime
- Loading indicators show progress

## 📱 Mobile Access

Your dashboard works perfectly on mobile devices:

1. **On Your Phone/Tablet**
   - Open web browser
   - Go to: `http://[YOUR-COMPUTER-IP]:8000/api/v1/admin/dashboard`
   - Replace `[YOUR-COMPUTER-IP]` with your computer's IP address

2. **Find Your Computer's IP**
   - Windows: Open Command Prompt, type `ipconfig`
   - Look for "IPv4 Address"

## 🔍 Exploring Advanced Features

### API Documentation

Your system includes comprehensive API documentation:

1. **Swagger UI**: `http://localhost:8000/docs`
   - Interactive API testing
   - Complete endpoint documentation
   - Try API calls directly

2. **ReDoc**: `http://localhost:8000/redoc`
   - Beautiful API documentation
   - Detailed schemas and examples

### Health Monitoring

Check system health anytime:
- **Health Endpoint**: `http://localhost:8000/health`
- Returns detailed system status
- Useful for monitoring tools

## 🎉 Congratulations!

You now know how to:
- ✅ Start and stop your hotel bot system
- ✅ Access and navigate the admin dashboard
- ✅ Monitor system performance
- ✅ Use keyboard shortcuts for efficiency
- ✅ Access the system from mobile devices
- ✅ Find API documentation

## 🆘 Need Help?

If you encounter any issues:

1. **Check the troubleshooting guide**: `docs/troubleshooting_guide.md`
2. **Review system logs** in the command prompt
3. **Verify all services are "Active"** in the dashboard
4. **Try refreshing** the dashboard
5. **Restart the system** if needed

## 🚀 Next Steps

Now that you're comfortable with the basics:
1. Explore the Hotels section for property management
2. Check out Analytics for performance insights
3. Review Security settings for your setup
4. Configure WhatsApp integration for live messaging

Your WhatsApp Hotel Bot is ready to revolutionize your guest communication!
