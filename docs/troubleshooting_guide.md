# WhatsApp Hotel Bot - Troubleshooting Guide

## 🔧 Common Issues and Solutions

This guide helps you solve the most common problems you might encounter with your WhatsApp Hotel Bot system.

## 🚨 Quick Fixes (Try These First)

### Problem: Can't Access Dashboard
**Symptoms**: Browser shows "This site can't be reached" or similar error

**Solutions**:
1. **Check if server is running**
   ```bash
   # Look for this in your command prompt:
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

2. **Restart the server**
   ```bash
   # Press Ctrl+C to stop, then restart:
   python -m uvicorn app_full:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Try different URL formats**
   - `http://localhost:8000/api/v1/admin/dashboard`
   - `http://127.0.0.1:8000/api/v1/admin/dashboard`

### Problem: Dashboard Shows Only "-" in Stats
**Symptoms**: Stats cards show dashes instead of numbers

**Solutions**:
1. **Wait 3-5 seconds** for data to load
2. **Click the Refresh button** in the top-right
3. **Check browser console** (F12 → Console tab) for errors
4. **Verify API endpoints** are working:
   - Go to: `http://localhost:8000/health`
   - Should show system status

### Problem: "alembic command not found"
**Symptoms**: Error when running `alembic upgrade head`

**Solution**:
```bash
# Use this instead:
python -m alembic upgrade head

# Or for multiple heads:
python -m alembic upgrade heads
```

## 🗄️ Database Issues

### Problem: Database Connection Errors
**Symptoms**: "Database connection failed" or similar errors

**Solutions**:
1. **Initialize the database**
   ```bash
   python scripts/init_sqlite_db.py
   ```

2. **Check database file exists**
   - Look for `test.db` in your project folder
   - File should be several KB in size

3. **Reset database if corrupted**
   ```bash
   # Delete the old database
   del test.db
   # Recreate it
   python scripts/init_sqlite_db.py
   ```

### Problem: Migration Errors
**Symptoms**: Alembic migration failures

**Solutions**:
1. **Use SQLite-compatible approach**
   ```bash
   # Skip migrations and use our init script:
   python scripts/init_sqlite_db.py
   ```

2. **Check migration status**
   ```bash
   python -m alembic current
   python -m alembic history
   ```

3. **Force migration to specific version**
   ```bash
   python -m alembic upgrade 010_create_user_auth_tables
   ```

## 🌐 Server and Network Issues

### Problem: Port Already in Use
**Symptoms**: "Address already in use" error

**Solutions**:
1. **Use different port**
   ```bash
   python -m uvicorn app_full:app --reload --host 0.0.0.0 --port 8001
   # Then access: http://localhost:8001/api/v1/admin/dashboard
   ```

2. **Kill existing process**
   ```bash
   # Windows:
   netstat -ano | findstr :8000
   taskkill /PID [PID_NUMBER] /F
   
   # Then restart normally
   ```

### Problem: Slow Loading or Timeouts
**Symptoms**: Dashboard takes forever to load

**Solutions**:
1. **Check system resources**
   - Close unnecessary programs
   - Ensure sufficient RAM available

2. **Restart with minimal logging**
   ```bash
   python -m uvicorn app_full:app --host 0.0.0.0 --port 8000 --log-level warning
   ```

3. **Clear browser cache**
   - Press Ctrl+Shift+Delete
   - Clear cached images and files

## 🎨 Dashboard and UI Issues

### Problem: Dashboard Looks Broken
**Symptoms**: Missing styles, broken layout

**Solutions**:
1. **Check internet connection**
   - Dashboard uses CDN resources (Bootstrap, Chart.js)
   - Ensure internet access for external resources

2. **Hard refresh the page**
   - Press Ctrl+Shift+R (Windows)
   - Or Cmd+Shift+R (Mac)

3. **Try different browser**
   - Chrome, Firefox, Edge all supported
   - Disable browser extensions if issues persist

### Problem: Navigation Not Working
**Symptoms**: Clicking sidebar items doesn't switch sections

**Solutions**:
1. **Check JavaScript errors**
   - Press F12 → Console tab
   - Look for red error messages

2. **Refresh the page**
   - Press F5 or Ctrl+R

3. **Clear browser data**
   - Settings → Privacy → Clear browsing data

## 📱 Mobile Access Issues

### Problem: Can't Access from Phone/Tablet
**Symptoms**: Mobile browser can't reach dashboard

**Solutions**:
1. **Find your computer's IP address**
   ```bash
   # Windows:
   ipconfig
   # Look for IPv4 Address (e.g., 192.168.1.100)
   ```

2. **Use IP address in mobile browser**
   ```
   http://192.168.1.100:8000/api/v1/admin/dashboard
   ```

3. **Check firewall settings**
   - Windows Firewall might block connections
   - Temporarily disable to test

## 🔐 Security and Authentication Issues

### Problem: Security Headers Errors
**Symptoms**: Browser security warnings

**Solutions**:
1. **Use HTTP (not HTTPS) for local development**
   - `http://localhost:8000` ✅
   - `https://localhost:8000` ❌

2. **Check CORS settings**
   - System configured for localhost access
   - External access may need configuration

## 🐍 Python Environment Issues

### Problem: "Module not found" Errors
**Symptoms**: ImportError or ModuleNotFoundError

**Solutions**:
1. **Verify Python version**
   ```bash
   python --version
   # Should be 3.11+ (currently 3.13.4)
   ```

2. **Check installed packages**
   ```bash
   pip list | findstr fastapi
   pip list | findstr uvicorn
   ```

3. **Reinstall dependencies if needed**
   ```bash
   pip install -r requirements.txt
   ```

### Problem: Virtual Environment Issues
**Symptoms**: Packages not found despite installation

**Solutions**:
1. **Check if in virtual environment**
   ```bash
   # Should show virtual env name in prompt
   # If not, activate it:
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Mac/Linux
   ```

## 🔍 Diagnostic Commands

### System Health Check
```bash
# Run comprehensive health check:
python scripts/health_check_comprehensive.py
```

### Quick Status Check
```bash
# Check if server responds:
python -c "import requests; print('Status:', requests.get('http://localhost:8000/health').status_code)"
```

### Database Status
```bash
# Check database:
python -c "import sqlite3; print('DB exists:', os.path.exists('test.db'))"
```

## 📞 Getting Help

### Step 1: Gather Information
Before seeking help, collect:
1. **Error messages** (copy exact text)
2. **Browser console logs** (F12 → Console)
3. **Server logs** (from command prompt)
4. **System info** (Windows version, Python version)

### Step 2: Try Safe Mode
```bash
# Start with minimal configuration:
python -m uvicorn app_full:app --host 127.0.0.1 --port 8000
```

### Step 3: Reset to Known Good State
```bash
# Complete reset:
1. Stop server (Ctrl+C)
2. Delete test.db
3. Run: python scripts/init_sqlite_db.py
4. Restart server
5. Test dashboard
```

## ✅ Prevention Tips

### Daily Maintenance
1. **Regular restarts** - Restart server daily
2. **Monitor logs** - Check for warnings
3. **Update browser** - Keep browser current
4. **Backup database** - Copy test.db regularly

### Best Practices
1. **Use consistent URLs** - Always use same format
2. **Close cleanly** - Use Ctrl+C to stop server
3. **Monitor resources** - Watch CPU/memory usage
4. **Keep notes** - Document any custom changes

## 🎯 Success Indicators

Your system is working correctly when:
- ✅ Dashboard loads in under 3 seconds
- ✅ All stats show numbers (not "-")
- ✅ Navigation switches sections smoothly
- ✅ System status shows all "Active"
- ✅ Refresh button updates data
- ✅ No errors in browser console
- ✅ Health endpoint returns 200 status

Remember: Most issues are solved by restarting the server and refreshing the browser!
