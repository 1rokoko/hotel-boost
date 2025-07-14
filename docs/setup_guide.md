# WhatsApp Hotel Bot - Complete Setup Guide

## Quick Start for First-Time Users

### Prerequisites
- Python 3.11+ (currently using Python 3.13.4 ✅)
- Git (for cloning the repository)
- Basic command line knowledge

### Step 1: Environment Verification

The system is already set up in your current directory. Let's verify everything is working:

```bash
# Check Python version (should be 3.11+)
python --version

# Check if dependencies are installed
pip list | findstr fastapi
pip list | findstr alembic
```

### Step 2: Database Setup

**Important**: The alembic command needs to be run with Python module syntax:

```bash
# ❌ This will NOT work:
alembic upgrade head

# ✅ This WILL work:
python -m alembic upgrade head
```

**Current Database Configuration:**
- Using SQLite for development (configured in .env)
- Database file: `test.db`
- No complex setup required for testing

### Step 3: Start the Application

The application can be started in two ways:

**Option 1: Full Application (with some compatibility issues)**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Option 2: Simplified Application (recommended for testing)**
```bash
python -m uvicorn app_full:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Verify Application is Running

Once started, you can access:
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Admin Dashboard**: http://localhost:8000/api/v1/admin/dashboard

### Common Issues and Solutions

#### Issue 1: "alembic command not found"
**Solution**: Use `python -m alembic` instead of just `alembic`

#### Issue 2: Database migration errors
**Solution**: The current setup uses SQLite which has some compatibility issues with PostgreSQL migrations. For testing, you can skip migrations and use the simplified app.

#### Issue 3: Pydantic compatibility warnings
**Solution**: These are warnings and don't prevent the application from running. The simplified app_full.py avoids these issues.

### Next Steps

1. **Test the API**: Visit http://localhost:8000/docs to explore the API
2. **Check Admin Dashboard**: Visit http://localhost:8000/api/v1/admin/dashboard
3. **Review Configuration**: Check the .env file for current settings

### Environment Status ✅

- ✅ Python 3.13.4 installed
- ✅ All required packages installed (FastAPI, Alembic, etc.)
- ✅ Application starts successfully
- ✅ Database configured (SQLite for development)
- ✅ Basic endpoints responding

The system is ready for use and testing!

## 📚 Additional Documentation

- **User Tutorial**: `docs/user_tutorial.md` - Complete beginner's guide
- **Troubleshooting**: `docs/troubleshooting_guide.md` - Common issues and solutions
- **Testing Results**: `docs/testing_results.md` - Comprehensive test validation
- **Operation Manual**: `docs/operation_manual.md` - Daily usage and maintenance
