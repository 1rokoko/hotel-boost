# 📋 TASK MASTER INTEGRATION PROCEDURES
## WhatsApp Hotel Bot MVP - Task Management Rules

## 🎯 TASK MASTER SYSTEM OVERVIEW

The Task Master system consists of:
- **`tasks.json`**: Master task registry (SINGLE SOURCE OF TRUTH)
- **`task_XXX.md`**: Individual task documentation files
- **Task-master CLI**: Command-line interface for task management
- **Validation Scripts**: Automated checks for task consistency

## 🔒 CRITICAL TASK MANAGEMENT RULES

### Rule 1: tasks.json is IMMUTABLE during development
- **NEVER** modify `tasks.json` while a task is in progress
- **ONLY** update task status through task-master CLI commands
- **ALL** task modifications must be logged and tracked

### Rule 2: Task files are LIVING DOCUMENTS
- **MUST** be updated in real-time during development
- **REQUIRED** to reflect actual implementation details
- **MANDATORY** to document any deviations from original plan

### Rule 3: Task status MUST match reality
- **Status in `tasks.json`** must reflect actual development state
- **Subtask completion** must be tracked in individual task files
- **Progress percentage** must be updated daily

## 📊 TASK STATUS LIFECYCLE

### Task Status Definitions
```json
{
  "pending": "Task not started, all prerequisites not met",
  "ready": "Task ready to start, all dependencies satisfied",
  "in-progress": "Task currently being worked on",
  "blocked": "Task blocked by external dependency or issue",
  "review": "Task complete, awaiting review/testing",
  "done": "Task fully complete and validated"
}
```

### Status Transition Rules
```
pending → ready → in-progress → review → done
    ↓         ↓         ↓         ↓
  blocked   blocked   blocked   blocked
```

**Transition Requirements:**
- **pending → ready**: All dependencies marked "done"
- **ready → in-progress**: Pre-development analysis complete
- **in-progress → review**: All subtasks complete, documentation updated
- **review → done**: All validation checks passed
- **any → blocked**: Document blocker reason and resolution plan

## 🔄 TASK UPDATE PROCEDURES

### Starting a New Task

#### Step 1: Validate Prerequisites
```bash
# Check task dependencies
npx task-master show <task_id>

# Verify all dependencies are "done"
npx task-master dependencies <task_id>
```

#### Step 2: Update Task Status
```bash
# Mark task as in-progress
npx task-master set-status --id=<task_id> --status=in-progress
```

#### Step 3: Update Task Documentation
- **Open** `.taskmaster/tasks/task_XXX.md`
- **Add** "Development Started" section with:
  - Start date and developer name
  - Detailed implementation plan
  - Risk assessment and mitigation plans
  - Updated time estimates if needed

#### Step 4: Create Development Branch
```bash
# Create feature branch following naming convention
git checkout -b task-<task_id>-<brief-description>
```

### During Task Development

#### Daily Updates (MANDATORY)
1. **Update subtask completion** in task file
2. **Log progress percentage** in task file
3. **Document any blockers** or issues encountered
4. **Update time estimates** if significantly different from original

#### Subtask Completion Process
```markdown
## Subtask Status Tracking

### Subtask X.Y: [Subtask Name]
- **Status**: ✅ Complete / 🔄 In Progress / ❌ Blocked
- **Estimated Hours**: X
- **Actual Hours**: Y
- **Completion Date**: YYYY-MM-DD
- **Notes**: Any important implementation details or issues
- **Files Modified**: List of files created/modified
```

#### Code-Documentation Synchronization
**MANDATORY**: Every code change must have corresponding documentation update:

1. **New Files Created**: Add to task file under "Files Created"
2. **API Changes**: Update API documentation immediately
3. **Database Changes**: Update schema documentation
4. **Configuration Changes**: Update deployment documentation

### Completing a Task

#### Step 1: Subtask Verification
- [ ] **All subtasks marked complete** in task file
- [ ] **All acceptance criteria met** and documented
- [ ] **All files listed** in task documentation
- [ ] **All tests passing** and documented

#### Step 2: Documentation Finalization
- [ ] **Component documentation updated** (README files)
- [ ] **API documentation updated** (if applicable)
- [ ] **Architecture documentation updated** (if structural changes)
- [ ] **Test documentation complete** with coverage reports

#### Step 3: Task Status Update
```bash
# Mark task for review
npx task-master set-status --id=<task_id> --status=review
```

#### Step 4: Review Process
- [ ] **Code review completed** and approved
- [ ] **Documentation review completed**
- [ ] **Security review completed** (if applicable)
- [ ] **Performance testing completed** (if applicable)

#### Step 5: Final Completion
```bash
# Mark task as done
npx task-master set-status --id=<task_id> --status=done
```

## 🔍 TASK VALIDATION RULES

### Automated Validation Checks

#### Task File Validation
```bash
# Validate task file completeness
npx task-master validate <task_id>
```

**Checks performed:**
- All required sections present
- All subtasks have status
- Estimated vs actual time logged
- All files listed and exist
- All acceptance criteria addressed

#### Dependency Validation
```bash
# Check dependency satisfaction
npx task-master check-dependencies <task_id>
```

**Checks performed:**
- All dependency tasks marked "done"
- No circular dependencies
- Dependency chain is valid
- Required files from dependencies exist

#### Documentation Synchronization Check
```bash
# Verify documentation is up-to-date
npx task-master check-docs <task_id>
```

**Checks performed:**
- Task file updated within last 24 hours
- All referenced files exist
- API documentation matches implementation
- Test documentation covers implementation

### Manual Validation Requirements

#### Pre-Development Validation
- [ ] **Task requirements understood** by developer
- [ ] **All dependencies available** and documented
- [ ] **Technical approach planned** and documented
- [ ] **Risk assessment completed** and mitigation planned

#### Development Validation
- [ ] **Progress tracking accurate** and up-to-date
- [ ] **Documentation synchronized** with implementation
- [ ] **Code quality standards met**
- [ ] **Test coverage adequate** (>85%)

#### Completion Validation
- [ ] **All acceptance criteria met**
- [ ] **Documentation complete and accurate**
- [ ] **No known issues or technical debt**
- [ ] **Ready for next dependent tasks**

## 🚨 TASK MANAGEMENT VIOLATIONS

### Common Violations and Consequences

#### 1. Outdated Task Documentation
- **Violation**: Task file not updated for >24 hours during active development
- **Consequence**: Development block until documentation updated
- **Resolution**: Update task file with current status and progress

#### 2. Status Mismatch
- **Violation**: Task status in `tasks.json` doesn't match actual development state
- **Consequence**: Task status reset to accurate state
- **Resolution**: Correct status and document reason for mismatch

#### 3. Missing Subtask Documentation
- **Violation**: Subtasks marked complete without proper documentation
- **Consequence**: Subtask status reset to in-progress
- **Resolution**: Complete documentation before re-marking as complete

#### 4. Dependency Violations
- **Violation**: Starting task before dependencies are complete
- **Consequence**: Task blocked until dependencies satisfied
- **Resolution**: Complete dependency tasks or update dependency chain

## 📊 TASK METRICS AND REPORTING

### Tracked Metrics
1. **Task Completion Rate**: % of tasks completed on time
2. **Estimation Accuracy**: Actual vs estimated time variance
3. **Documentation Compliance**: % of tasks with complete documentation
4. **Dependency Satisfaction**: % of tasks with satisfied dependencies
5. **Blocker Resolution Time**: Average time to resolve blockers

### Reporting Schedule
- **Daily**: Task progress updates
- **Weekly**: Task completion and blocker reports
- **Monthly**: Estimation accuracy and process improvement analysis

### Task Master Commands Reference
```bash
# View all tasks
npx task-master list

# Show specific task details
npx task-master show <task_id>

# Update task status
npx task-master set-status --id=<task_id> --status=<status>

# Check dependencies
npx task-master dependencies <task_id>

# Validate task
npx task-master validate <task_id>

# Generate reports
npx task-master report --type=<report_type>
```
