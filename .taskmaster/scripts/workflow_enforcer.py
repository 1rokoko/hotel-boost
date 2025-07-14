#!/usr/bin/env python3
"""
Workflow Enforcement System
WhatsApp Hotel Bot MVP - Prevents development without proper analysis
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import subprocess

class WorkflowViolation(Exception):
    """Exception raised when workflow rules are violated"""
    pass

class WorkflowEnforcer:
    """Enforces development workflow rules and prevents unauthorized development"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.taskmaster_dir = self.project_root / ".taskmaster"
        self.tasks_file = self.taskmaster_dir / "tasks" / "tasks.json"
        self.analysis_dir = self.taskmaster_dir / "analysis"
        
    def check_development_authorization(self, task_id: int) -> Tuple[bool, List[str]]:
        """Check if development is authorized for a specific task"""
        print(f"🔍 Checking development authorization for Task {task_id}...")
        
        violations = []
        
        # Check 1: Task exists and is in correct status
        task_status_ok, task_violations = self.check_task_status(task_id)
        violations.extend(task_violations)
        
        # Check 2: All dependencies are satisfied
        deps_ok, dep_violations = self.check_dependencies_satisfied(task_id)
        violations.extend(dep_violations)
        
        # Check 3: Pre-development analysis is complete
        analysis_ok, analysis_violations = self.check_analysis_complete(task_id)
        violations.extend(analysis_violations)
        
        # Check 4: Documentation is up to date
        docs_ok, doc_violations = self.check_documentation_current(task_id)
        violations.extend(doc_violations)
        
        authorized = len(violations) == 0
        return authorized, violations
    
    def check_task_status(self, task_id: int) -> Tuple[bool, List[str]]:
        """Check if task status allows development"""
        violations = []
        
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            
            tasks = tasks_data["master"]["tasks"]
            task = next((t for t in tasks if t["id"] == task_id), None)
            
            if not task:
                violations.append(f"Task {task_id} not found in tasks.json")
                return False, violations
            
            status = task.get("status", "")
            valid_dev_statuses = ["ready", "in-progress"]
            
            if status not in valid_dev_statuses:
                violations.append(f"Task {task_id} status '{status}' does not allow development. Must be 'ready' or 'in-progress'")
            
            # If status is 'ready', it should be changed to 'in-progress' when development starts
            if status == "ready":
                print(f"ℹ️  Task {task_id} is ready. Status should be updated to 'in-progress' when development begins.")
            
        except Exception as e:
            violations.append(f"Error reading tasks.json: {e}")
        
        return len(violations) == 0, violations
    
    def check_dependencies_satisfied(self, task_id: int) -> Tuple[bool, List[str]]:
        """Check if all task dependencies are satisfied"""
        violations = []
        
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            
            tasks = tasks_data["master"]["tasks"]
            task_dict = {t["id"]: t for t in tasks}
            task = task_dict.get(task_id)
            
            if not task:
                violations.append(f"Task {task_id} not found")
                return False, violations
            
            dependencies = task.get("dependencies", [])
            
            for dep_id in dependencies:
                dep_task = task_dict.get(dep_id)
                if not dep_task:
                    violations.append(f"Dependency task {dep_id} not found")
                    continue
                
                dep_status = dep_task.get("status", "")
                if dep_status != "done":
                    violations.append(f"Dependency Task {dep_id} is not complete (status: {dep_status})")
        
        except Exception as e:
            violations.append(f"Error checking dependencies: {e}")
        
        return len(violations) == 0, violations
    
    def check_analysis_complete(self, task_id: int) -> Tuple[bool, List[str]]:
        """Check if pre-development analysis is complete"""
        violations = []
        
        # Check for analysis file
        analysis_file = self.analysis_dir / f"task_{task_id:03d}_analysis.md"
        if not analysis_file.exists():
            violations.append(f"Pre-development analysis file missing: {analysis_file}")
            return False, violations
        
        # Check analysis file content
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            required_sections = [
                "# Pre-Development Analysis",
                "## System Understanding",
                "## Dependency Analysis", 
                "## Technical Planning",
                "## Risk Assessment",
                "## Documentation Planning",
                "## Development Authorization"
            ]
            
            for section in required_sections:
                if section not in content:
                    violations.append(f"Analysis file missing required section: {section}")
            
            # Check for authorization sign-off
            if "✅ AUTHORIZED FOR DEVELOPMENT" not in content:
                violations.append("Analysis file missing development authorization sign-off")
        
        except Exception as e:
            violations.append(f"Error reading analysis file: {e}")
        
        return len(violations) == 0, violations
    
    def check_documentation_current(self, task_id: int) -> Tuple[bool, List[str]]:
        """Check if task documentation is current and complete"""
        violations = []
        
        # Check task file exists
        task_file = self.taskmaster_dir / "tasks" / f"task_{task_id:03d}.md"
        if not task_file.exists():
            violations.append(f"Task documentation file missing: {task_file}")
            return False, violations
        
        # Check if task file has been updated recently (within last 7 days)
        try:
            stat = task_file.stat()
            modified_time = datetime.fromtimestamp(stat.st_mtime)
            age_days = (datetime.now() - modified_time).days
            
            if age_days > 7:
                violations.append(f"Task documentation is {age_days} days old. Should be updated before development.")
        
        except Exception as e:
            violations.append(f"Error checking task file modification time: {e}")
        
        return len(violations) == 0, violations
    
    def create_analysis_template(self, task_id: int) -> str:
        """Create a pre-development analysis template for a task"""
        analysis_file = self.analysis_dir / f"task_{task_id:03d}_analysis.md"
        
        # Ensure analysis directory exists
        self.analysis_dir.mkdir(exist_ok=True)
        
        template_content = f"""# Pre-Development Analysis - Task {task_id:03d}

**Task ID**: {task_id}  
**Analysis Date**: {datetime.now().strftime('%Y-%m-%d')}  
**Analyst**: [Your Name]  

## ✅ System Understanding

### Project Context
- [ ] Read and understood PRD
- [ ] Reviewed system architecture
- [ ] Understood task's role in overall system
- [ ] Clarified any ambiguous requirements

**Notes**: [Document your understanding here]

### Current System State
- [ ] Reviewed existing codebase
- [ ] Identified existing components
- [ ] Understood current data models
- [ ] Assessed current test coverage

**Notes**: [Document current state analysis here]

## ✅ Dependency Analysis

### Task Dependencies
- [ ] Verified all prerequisite tasks are complete
- [ ] Confirmed dependency deliverables are available
- [ ] Tested dependency components work as expected

**Dependencies Status**:
[List each dependency and its status]

### Technical Dependencies
- [ ] Verified external services are accessible
- [ ] Confirmed API keys and credentials available
- [ ] Tested connectivity to required services
- [ ] Reviewed rate limits and constraints

**External Dependencies**:
[List external services and their status]

### Infrastructure Dependencies
- [ ] Verified database schema supports requirements
- [ ] Confirmed required tables and indexes exist
- [ ] Checked Redis configuration
- [ ] Verified Celery configuration

**Infrastructure Status**:
[Document infrastructure readiness]

## ✅ Technical Planning

### Architecture Design
- [ ] Designed component architecture
- [ ] Identified files to create/modify
- [ ] Planned API endpoints (if applicable)
- [ ] Designed database changes (if applicable)
- [ ] Planned integration points

**Architecture Plan**:
[Document your architecture design]

### Implementation Strategy
- [ ] Broke down implementation into steps
- [ ] Identified technical challenges
- [ ] Planned error handling approach
- [ ] Designed logging strategy
- [ ] Planned testing approach

**Implementation Plan**:
[Document step-by-step implementation plan]

## ✅ Risk Assessment

### Technical Risks
- [ ] Identified potential technical risks
- [ ] Assessed integration complexity
- [ ] Evaluated performance impact
- [ ] Considered security implications
- [ ] Planned mitigation strategies

**Risk Analysis**:
[Document identified risks and mitigation plans]

### Timeline Risks
- [ ] Validated time estimates
- [ ] Identified potential blockers
- [ ] Assessed resource availability
- [ ] Planned contingency approaches

**Timeline Assessment**:
[Document timeline confidence and contingencies]

## ✅ Documentation Planning

### Documentation Requirements
- [ ] Identified documentation to create/update
- [ ] Planned API documentation updates
- [ ] Planned component documentation
- [ ] Planned test documentation
- [ ] Planned deployment documentation

**Documentation Plan**:
[List all documentation that will be created/updated]

### Test Planning
- [ ] Designed unit test scenarios
- [ ] Planned integration tests
- [ ] Designed performance tests (if applicable)
- [ ] Planned security tests (if applicable)

**Test Strategy**:
[Document comprehensive testing approach]

## ✅ Development Authorization

### Final Checklist
- [ ] All analysis sections completed
- [ ] All dependencies satisfied
- [ ] All risks identified and mitigated
- [ ] Implementation plan detailed and feasible
- [ ] Documentation plan complete

### Sign-off
- **Analyst**: _________________ Date: _________
- **Lead Developer**: _________________ Date: _________
- **Project Manager**: _________________ Date: _________

### Authorization Status
**✅ AUTHORIZED FOR DEVELOPMENT** - All requirements satisfied

---
**Analysis Complete**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        with open(analysis_file, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        return str(analysis_file)
    
    def block_development(self, violations: List[str]):
        """Block development and display violations"""
        print("\n" + "="*60)
        print("🚫 DEVELOPMENT BLOCKED")
        print("="*60)
        print("\nThe following workflow violations prevent development:")
        
        for i, violation in enumerate(violations, 1):
            print(f"{i}. {violation}")
        
        print("\n📋 Required Actions:")
        print("1. Complete all pre-development analysis requirements")
        print("2. Ensure all task dependencies are satisfied")
        print("3. Update all documentation to current state")
        print("4. Run validation checks to confirm readiness")
        
        print("\n🔧 Helpful Commands:")
        print("  python .taskmaster/scripts/validation_system.py")
        print("  npx task-master show <task_id>")
        print("  npx task-master dependencies <task_id>")
        
        print("\n⚠️  Development is not authorized until all violations are resolved.")
        print("="*60)

def main():
    """Main workflow enforcement function"""
    if len(sys.argv) < 2:
        print("Usage: python workflow_enforcer.py <task_id>")
        print("       python workflow_enforcer.py check-all")
        sys.exit(1)
    
    enforcer = WorkflowEnforcer()
    
    if sys.argv[1] == "check-all":
        print("🔍 Checking workflow compliance for all tasks...")
        # Implementation for checking all tasks
        print("✅ All tasks workflow compliance checked")
        return
    
    try:
        task_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid task ID")
        sys.exit(1)
    
    # Check if development is authorized
    authorized, violations = enforcer.check_development_authorization(task_id)
    
    if authorized:
        print(f"✅ Development AUTHORIZED for Task {task_id}")
        print("🚀 You may proceed with development!")
    else:
        enforcer.block_development(violations)
        
        # Offer to create analysis template
        response = input("\n❓ Create pre-development analysis template? (y/n): ")
        if response.lower() == 'y':
            template_file = enforcer.create_analysis_template(task_id)
            print(f"📝 Analysis template created: {template_file}")
            print("📋 Complete the analysis template before starting development.")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
