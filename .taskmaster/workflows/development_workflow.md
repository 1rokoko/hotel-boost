# 🔒 STRICT DEVELOPMENT WORKFLOW RULES
## WhatsApp Hotel Bot MVP - Mandatory Development Process

## 🚨 CRITICAL RULE: NO CODE WITHOUT DOCUMENTATION

**ABSOLUTE REQUIREMENT**: No code development may begin until all prerequisite documentation and analysis is complete and validated.

## 📋 MANDATORY PRE-DEVELOPMENT CHECKLIST

### ✅ Phase 1: System Analysis (REQUIRED BEFORE ANY CODE)

#### 1.1 Current State Analysis
- [ ] **Read and understand** `.taskmaster/docs/prd.txt`
- [ ] **Review** current system architecture in `.taskmaster/docs/architecture.md`
- [ ] **Analyze** existing codebase structure and dependencies
- [ ] **Verify** all external API documentation is current
- [ ] **Document findings** in `.taskmaster/analysis/current_state_analysis.md`

#### 1.2 Task-Specific Analysis
- [ ] **Read** the specific task file (e.g., `.taskmaster/tasks/task_001.md`)
- [ ] **Understand** all subtasks and their requirements
- [ ] **Verify** all task dependencies are completed
- [ ] **Check** that all prerequisite tasks are marked as "done" in `tasks.json`
- [ ] **Confirm** estimated hours and complexity are realistic

#### 1.3 Dependency Analysis
- [ ] **Map** all technical dependencies for the current task
- [ ] **Verify** all required external services are available
- [ ] **Check** database schema requirements
- [ ] **Confirm** API endpoint dependencies
- [ ] **Document** dependency analysis in `.taskmaster/analysis/dependency_analysis.md`

#### 1.4 Risk Assessment
- [ ] **Identify** potential technical risks
- [ ] **Assess** integration complexity
- [ ] **Evaluate** security implications
- [ ] **Plan** mitigation strategies
- [ ] **Document** risks in `.taskmaster/analysis/risk_assessment.md`

### ✅ Phase 2: Documentation Preparation (REQUIRED BEFORE CODING)

#### 2.1 Task Documentation Update
- [ ] **Update** task status to "in-progress" in `tasks.json`
- [ ] **Add** detailed implementation plan to task file
- [ ] **Specify** exact files to be created/modified
- [ ] **Define** acceptance criteria for each subtask
- [ ] **Estimate** realistic completion timeline

#### 2.2 Technical Documentation Preparation
- [ ] **Create** API endpoint documentation (if applicable)
- [ ] **Design** database schema changes (if applicable)
- [ ] **Plan** component architecture
- [ ] **Define** integration points
- [ ] **Specify** error handling approach

#### 2.3 Test Documentation Preparation
- [ ] **Define** test scenarios for each subtask
- [ ] **Plan** unit test coverage
- [ ] **Design** integration test cases
- [ ] **Specify** performance test requirements
- [ ] **Create** test data requirements

## 🔄 DEVELOPMENT PHASE RULES

### During Development (MANDATORY UPDATES)

#### Code Development Rules
1. **File Creation**: Every new file must have corresponding documentation
2. **API Changes**: Must update API documentation immediately
3. **Database Changes**: Must update schema documentation
4. **Configuration Changes**: Must update deployment documentation
5. **Dependency Changes**: Must update dependency documentation

#### Task Tracking Rules
1. **Subtask Completion**: Mark subtasks as complete in task file immediately
2. **Progress Updates**: Update task progress percentage daily
3. **Blocker Documentation**: Document any blockers immediately in task file
4. **Time Tracking**: Log actual vs estimated time for each subtask

#### Documentation Synchronization Rules
1. **Code Comments**: All complex logic must be documented in code
2. **README Updates**: Component README must be updated with new functionality
3. **API Documentation**: OpenAPI/Swagger specs must be updated with code
4. **Architecture Updates**: System architecture docs updated for structural changes

## 🚫 DEVELOPMENT BLOCKERS

### Automatic Development Blocks
Development is **AUTOMATICALLY BLOCKED** if:

1. **Missing Analysis**: Any Phase 1 checklist item is incomplete
2. **Outdated Documentation**: Any related documentation is >7 days old without review
3. **Dependency Issues**: Required dependencies are not available or documented
4. **Task Status Mismatch**: Task status in `tasks.json` doesn't match actual progress
5. **Missing Prerequisites**: Previous tasks marked as dependencies are not complete

### Manual Development Blocks
Development must be **MANUALLY STOPPED** if:

1. **Documentation Drift**: Code implementation differs from documented design
2. **Scope Creep**: Implementation exceeds defined task scope
3. **Quality Issues**: Code quality doesn't meet established standards
4. **Test Failures**: Any existing tests fail due to changes
5. **Security Concerns**: Implementation introduces security vulnerabilities

## ✅ COMPLETION PHASE RULES

### Before Marking Task Complete

#### 1. Code Quality Verification
- [ ] **All tests pass** (unit, integration, performance)
- [ ] **Code coverage** meets minimum requirements (>85%)
- [ ] **Code review** completed and approved
- [ ] **Security review** completed (for security-sensitive tasks)
- [ ] **Performance benchmarks** meet requirements

#### 2. Documentation Completion
- [ ] **All documentation updated** to reflect final implementation
- [ ] **API documentation** matches actual implementation
- [ ] **Component documentation** is complete and accurate
- [ ] **Test documentation** covers all implemented scenarios
- [ ] **Deployment documentation** updated if needed

#### 3. Task Documentation Finalization
- [ ] **All subtasks marked complete** in task file
- [ ] **Actual time logged** vs estimated time
- [ ] **Lessons learned** documented
- [ ] **Known issues** documented (if any)
- [ ] **Task status updated** to "done" in `tasks.json`

## 🔍 VALIDATION MECHANISMS

### Automated Validation (To Be Implemented)
1. **Documentation Freshness Check**: Verify docs are updated within required timeframes
2. **Task Status Validation**: Ensure task status matches actual implementation
3. **Dependency Verification**: Check that all dependencies are satisfied
4. **Documentation Completeness**: Verify all required documentation sections exist

### Manual Validation (Required)
1. **Peer Review**: Another team member must review all documentation
2. **Architecture Review**: System architect must approve architectural changes
3. **Security Review**: Security specialist must review security-sensitive changes
4. **Product Review**: Product owner must approve feature implementations

## 🚨 VIOLATION CONSEQUENCES

### Documentation Violations
- **Minor**: Warning and requirement to fix within 24 hours
- **Major**: Development block until documentation is corrected
- **Critical**: Task rollback and restart of development process

### Process Violations
- **First Offense**: Process training and documentation review
- **Second Offense**: Mandatory pair programming with senior developer
- **Repeated Offenses**: Escalation to project management

## 📞 ESCALATION PROCEDURES

### When to Escalate
1. **Blocked Development**: Cannot proceed due to external dependencies
2. **Documentation Conflicts**: Conflicting information in different documents
3. **Scope Questions**: Uncertainty about task requirements or scope
4. **Technical Blockers**: Technical issues preventing progress

### Escalation Contacts
- **Technical Issues**: Lead Developer
- **Documentation Issues**: Technical Writer/Documentation Lead
- **Process Issues**: Project Manager
- **Architecture Issues**: System Architect
- **Security Issues**: Security Lead

## 📊 WORKFLOW METRICS

### Tracked Metrics
1. **Documentation Compliance Rate**: % of tasks with complete documentation
2. **Process Adherence Rate**: % of tasks following complete workflow
3. **Documentation Freshness**: Average age of documentation
4. **Task Completion Accuracy**: Actual vs estimated time and scope
5. **Blocker Resolution Time**: Time to resolve development blockers

### Success Criteria
- **Documentation Compliance**: >95%
- **Process Adherence**: >90%
- **Documentation Freshness**: <7 days average
- **Task Accuracy**: <20% variance from estimates
- **Blocker Resolution**: <24 hours average
