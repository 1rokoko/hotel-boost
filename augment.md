Here's the English translation of your document with the same structure preserved:

```text
# 🤖 AUGMENT CODE AI INSTRUCTIONS - Hotel Boost / WhatsApp Hotel Bot Project

## 🚨 CRITICAL RULES - MANDATORY COMPLIANCE

### 🎯 MAIN RULE
**NEVER START DEVELOPMENT WITHOUT FULL ANALYSIS OF EXISTING CODE AND DOCUMENTATION!**

### 🛡️ CODE REWRITE PROTECTION

#### ⚠️ CRITICAL: PRESERVE EXISTING FUNCTIONALITY
**NEVER remove existing functionality from Hotels, Triggers, Templates, or other admin dashboard sections when editing admin_dashboard.html. Only add or modify specific requested features while preserving all existing code.**

#### MANDATORY SEQUENCE BEFORE ANY CHANGES:
```bash
# 1. ALWAYS verify development authorization
python .taskmaster/scripts/workflow_enforcer.py <task_id>

# 2. ALWAYS validate current documentation state
python .taskmaster/scripts/validation_system.py

# 3. ALWAYS check task status
npx task-master list

# 4. ALWAYS find related documentation
find .taskmaster/docs -name "*.md" | grep -i <keyword>
find docs -name "*.md" | grep -i <keyword>
```

### 📁 PROJECT STRUCTURE AND DOCUMENTATION
**Main documentation locations:**
1. `.taskmaster/` - Project and task management
   - `.taskmaster/docs/` - Main project documentation
   - `.taskmaster/tasks/` - Task documentation (task_001.md - task_015.md)
   - `.taskmaster/workflows/` - Development processes and rules
   - `.taskmaster/templates/` - Documentation templates
2. `docs/` - Technical documentation
   - `docs/api/` - API documentation
   - `docs/testing/` - Testing documentation
   - Specialized files (database.md, deployment.md, etc.)
3. Code-specific documentation
   - `app/*/README.md` - Component documentation
   - `tests/*/README.md` - Test documentation

### 📋 KEY FILES TO STUDY BEFORE WORKING:
**CRITICAL TO REVIEW:**
- `.taskmaster/tasks/tasks.json` - Complete registry of all tasks (CRITICAL!)
- `.taskmaster/docs/project_completion_summary.md` - What's already completed
- `.taskmaster/docs/documentation_structure.md` - Documentation structure
- `.taskmaster/workflows/development_workflow.md` - Development rules
- `docs/` - Component technical documentation
- Specific `task_XXX.md` for current task

### 🏗️ VALIDATION AND CONTROL SYSTEM
**Automated update system:**
1. Synchronous updates (MANDATORY):
   - Documentation updated BEFORE or DURING code changes
   - Never after!
2. Check frequency:
   - Daily: Automatic documentation freshness validation
   - Weekly: Manual accuracy check
   - On every commit: Validation via Git hooks
3. Development lock system:
   - Development BLOCKED without completed analysis
   - Code review REJECTED without documentation updates
   - Task status RESET on workflow violation

### 📋 TASK WORKING RULES
**All tasks ONLY through Task Master:**
```bash
# Check status
npx task-master status

# Find next task
npx task-master next

# Start working on task
npx task-master start <task_id>

# Complete task
npx task-master complete <task_id>
```

**Workflow for new tasks:**
1. Analysis: Study documentation and existing code
2. Planning: Create detailed plan in task_XXX.md
3. Authorization: Get approval via workflow_enforcer.py
4. Development: Follow rules in development_workflow.md
5. Testing: Update tests synchronously with code
6. Documentation: Update documentation in real-time
7. Completion: Validation and task closure

### 🚨 CRITICAL PROHIBITIONS AND REQUIREMENTS
**❌ NEVER DO:**
- Rewrite existing functionality without analysis
- Start development without studying documentation
- Modify code without updating documentation
- Skip workflow_enforcer.py validation
- Ignore existing tests
- Duplicate already implemented functionality

**✅ ALWAYS DO:**
- Use codebase-retrieval to search existing code
- Study `.taskmaster/docs/` before starting work
- Run validation_system.py for checks
- Update documentation synchronously with code
- Follow established architecture patterns
- Use existing components and services

### 🏗️ PROJECT ARCHITECTURE (IMPLEMENTED)
**Core components:**
- FastAPI Backend with complete project structure ✅
- PostgreSQL + Redis for data and caching ✅
- Green API integration for WhatsApp ✅
- DeepSeek AI for sentiment analysis and response generation ✅
- Multi-tenant architecture for 50+ hotels ✅
- Celery for asynchronous tasks ✅
- JWT Authentication and authorization ✅
- Comprehensive Testing Suite (>80% coverage) ✅
- Docker containerization and deployment ✅

### 🚀 ENHANCED FEATURES (TASKS 021-025)
**Advanced Trigger System:**
- Dynamic trigger settings based on trigger type ✅
- Minutes After First Message trigger for rapid response ✅
- Bangkok timezone integration (Asia/Bangkok) ✅
- Real-time trigger testing with seconds-based demos ✅
- Support for time-based, event-based, and condition-based triggers ✅

**DeepSeek AI Enhancements:**
- Comprehensive admin settings interface ✅
- Travel advisory system with conversation flow ✅
- Personalized recommendations based on guest profiles ✅
- Negative sentiment detection with staff notifications ✅
- Travel memory database for Phuket recommendations ✅

**Language Detection System:**
- Automatic language detection from phone numbers ✅
- Content-based language pattern analysis ✅
- Support for 25+ languages including Russian, Thai, Chinese ✅
- Confidence scoring for detection accuracy ✅
- Green API integration for enhanced user information ✅

**Enhanced Testing & Demos:**
- Interactive trigger demonstrations with real-time feedback ✅
- Travel advisor conversation flow testing ✅
- Language detection testing interface ✅
- Comprehensive Playwright automation testing ✅

### 🆘 SUPPORT AND ESCALATION
**For issues:**
1. Check troubleshooting guide: `.taskmaster/workflows/documentation_maintenance.md`
2. Run validation: `python .taskmaster/scripts/validation_system.py`
3. Check workflow: `python .taskmaster/scripts/workflow_enforcer.py <task_id>`
4. Study documentation: `.taskmaster/docs/documentation_system_guide.md`

**Project structure stored at:**
Full structure: `c:\Users\Arkadiy\Documents\augment-projects\hotel-boost\.taskmaster\docs\documentation_structure.md`

### ⚠️ VIOLATION CONSEQUENCES
**Missing Documentation Updates:**
- Violation: Code changes without corresponding documentation updates
- Consequence:
  - Development block until documentation is updated
  - Code review rejection
  - Task status reset to in-progress

### 📅 PROJECT STATUS
- Last update: December 19, 2024
- Project status: Enhanced Production System (tasks 001-025), fully operational
- Production Status: ✅ ENHANCED & READY
- Latest additions: Advanced Triggers, Travel Advisory, Language Detection
- **NEW: Standalone DeepSeek Pages** ✅
  - DeepSeek Testing: `/api/v1/admin/deepseek-testing` - Standalone AI testing interface
  - AI Configuration: `/api/v1/admin/ai-configuration` - Standalone AI settings page
  - Both pages are menu-free with modern gradient design and full functionality
- **FIXED: Admin Dashboard Navigation** ✅
  - Hotels section functionality restored
  - Triggers section functionality restored
  - Menu links updated to use correct section IDs
- Next phase: Continuous optimization and feature expansion

### 🎯 FINAL REMINDER
**MAIN RULE:** NEVER START DEVELOPMENT WITHOUT FULL ANALYSIS OF EXISTING CODE AND DOCUMENTATION!

**Always remember:** This project already has full implementation of all core components. Your task is to study existing code and extend it, not rewrite from scratch!
```