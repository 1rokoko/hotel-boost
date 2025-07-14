#!/usr/bin/env python3
"""
Documentation and Workflow Validation System
WhatsApp Hotel Bot MVP - Automated Validation Checks
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import sys

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class DocumentationValidator:
    """Validates documentation completeness and consistency"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.taskmaster_dir = self.project_root / ".taskmaster"
        self.tasks_file = self.taskmaster_dir / "tasks" / "tasks.json"
        self.validation_errors = []
        self.validation_warnings = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validation checks"""
        print("🔍 Starting comprehensive validation...")
        
        # Core validation checks
        self.validate_project_structure()
        self.validate_tasks_json()
        self.validate_task_files()
        self.validate_documentation_freshness()
        self.validate_task_dependencies()
        self.validate_documentation_completeness()
        
        # Report results
        success = len(self.validation_errors) == 0
        return success, self.validation_errors, self.validation_warnings
    
    def validate_project_structure(self):
        """Validate that required project structure exists"""
        print("📁 Validating project structure...")
        
        required_dirs = [
            ".taskmaster",
            ".taskmaster/docs",
            ".taskmaster/tasks",
            ".taskmaster/templates",
            ".taskmaster/analysis",
            ".taskmaster/workflows",
            "docs",
            "docs/api",
            "docs/architecture",
            "docs/database",
            "docs/integrations",
            "docs/deployment",
            "docs/testing"
        ]
        
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                self.validation_errors.append(f"Missing required directory: {dir_path}")
        
        required_files = [
            ".taskmaster/docs/prd.txt",
            ".taskmaster/docs/documentation_structure.md",
            ".taskmaster/workflows/development_workflow.md",
            ".taskmaster/workflows/task_master_integration.md",
            ".taskmaster/templates/task_template.md",
            ".taskmaster/templates/pre_development_checklist.md"
        ]
        
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                self.validation_errors.append(f"Missing required file: {file_path}")
    
    def validate_tasks_json(self):
        """Validate tasks.json structure and content"""
        print("📋 Validating tasks.json...")
        
        if not self.tasks_file.exists():
            self.validation_errors.append("tasks.json file not found")
            return
        
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
        except json.JSONDecodeError as e:
            self.validation_errors.append(f"Invalid JSON in tasks.json: {e}")
            return
        
        # Validate structure
        if "master" not in tasks_data:
            self.validation_errors.append("tasks.json missing 'master' key")
            return
        
        if "tasks" not in tasks_data["master"]:
            self.validation_errors.append("tasks.json missing 'tasks' array")
            return
        
        tasks = tasks_data["master"]["tasks"]
        
        # Validate each task
        for task in tasks:
            self.validate_task_structure(task)
        
        # Validate task IDs are sequential and unique
        task_ids = [task.get("id") for task in tasks]
        expected_ids = list(range(1, len(tasks) + 1))
        
        if task_ids != expected_ids:
            self.validation_errors.append(f"Task IDs not sequential: expected {expected_ids}, got {task_ids}")
    
    def validate_task_structure(self, task: Dict):
        """Validate individual task structure"""
        required_fields = ["id", "title", "description", "status", "priority", "dependencies", "complexity", "estimatedHours"]
        
        for field in required_fields:
            if field not in task:
                self.validation_errors.append(f"Task {task.get('id', 'unknown')} missing required field: {field}")
        
        # Validate status values
        valid_statuses = ["pending", "ready", "in-progress", "blocked", "review", "done"]
        if task.get("status") not in valid_statuses:
            self.validation_errors.append(f"Task {task.get('id')} has invalid status: {task.get('status')}")
        
        # Validate priority values
        valid_priorities = ["high", "medium", "low"]
        if task.get("priority") not in valid_priorities:
            self.validation_errors.append(f"Task {task.get('id')} has invalid priority: {task.get('priority')}")
        
        # Validate subtasks if present
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                self.validate_subtask_structure(task.get("id"), subtask)
    
    def validate_subtask_structure(self, task_id: int, subtask: Dict):
        """Validate subtask structure"""
        required_fields = ["id", "title", "description", "estimatedHours", "files"]
        
        for field in required_fields:
            if field not in subtask:
                self.validation_errors.append(f"Task {task_id} subtask {subtask.get('id', 'unknown')} missing field: {field}")
    
    def validate_task_files(self):
        """Validate that task files exist and are properly structured"""
        print("📄 Validating task files...")
        
        # Load tasks to check which files should exist
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            tasks = tasks_data["master"]["tasks"]
        except:
            return  # Already handled in validate_tasks_json
        
        for task in tasks:
            task_id = task.get("id")
            if task_id:
                task_file = self.taskmaster_dir / "tasks" / f"task_{task_id:03d}.md"
                
                if not task_file.exists():
                    self.validation_errors.append(f"Missing task file: {task_file}")
                else:
                    self.validate_task_file_content(task_file, task)
    
    def validate_task_file_content(self, task_file: Path, task_data: Dict):
        """Validate task file content structure"""
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.validation_errors.append(f"Cannot read task file {task_file}: {e}")
            return
        
        # Check for required sections
        required_sections = [
            "# Task",
            "## Описание",
            "## Приоритет:",
            "## Сложность:",
            "## Оценка времени:",
            "## Зависимости:",
            "## Детальный план выполнения",
            "## Критерии готовности"
        ]
        
        for section in required_sections:
            if section not in content:
                self.validation_warnings.append(f"Task file {task_file} missing section: {section}")
        
        # Check if subtasks are documented
        if "subtasks" in task_data:
            for subtask in task_data["subtasks"]:
                subtask_id = subtask.get("id", "")
                if f"### Подзадача {subtask_id}" not in content:
                    self.validation_warnings.append(f"Task file {task_file} missing subtask documentation: {subtask_id}")
    
    def validate_documentation_freshness(self):
        """Validate that documentation is not stale"""
        print("🕒 Validating documentation freshness...")
        
        # Check task files for staleness
        tasks_dir = self.taskmaster_dir / "tasks"
        if tasks_dir.exists():
            for task_file in tasks_dir.glob("task_*.md"):
                try:
                    stat = task_file.stat()
                    modified_time = datetime.fromtimestamp(stat.st_mtime)
                    age = datetime.now() - modified_time
                    
                    if age > timedelta(days=7):
                        self.validation_warnings.append(f"Task file {task_file.name} not updated in {age.days} days")
                except Exception as e:
                    self.validation_warnings.append(f"Cannot check modification time for {task_file}: {e}")
    
    def validate_task_dependencies(self):
        """Validate task dependencies are logical and satisfied"""
        print("🔗 Validating task dependencies...")
        
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            tasks = tasks_data["master"]["tasks"]
        except:
            return
        
        task_dict = {task["id"]: task for task in tasks}
        
        for task in tasks:
            task_id = task.get("id")
            dependencies = task.get("dependencies", [])
            
            # Check that all dependencies exist
            for dep_id in dependencies:
                if dep_id not in task_dict:
                    self.validation_errors.append(f"Task {task_id} depends on non-existent task {dep_id}")
                
                # Check for circular dependencies (basic check)
                if dep_id >= task_id:
                    self.validation_warnings.append(f"Task {task_id} depends on later task {dep_id} - possible circular dependency")
            
            # Check dependency status for in-progress tasks
            if task.get("status") == "in-progress":
                for dep_id in dependencies:
                    dep_task = task_dict.get(dep_id)
                    if dep_task and dep_task.get("status") != "done":
                        self.validation_errors.append(f"Task {task_id} is in-progress but dependency {dep_id} is not done")
    
    def validate_documentation_completeness(self):
        """Validate that all required documentation exists"""
        print("📚 Validating documentation completeness...")
        
        # Check for core documentation files
        core_docs = [
            ".taskmaster/docs/prd.txt",
            ".taskmaster/docs/architecture.md",
            ".taskmaster/docs/security_checklist.md"
        ]
        
        for doc_path in core_docs:
            full_path = self.project_root / doc_path
            if not full_path.exists():
                self.validation_errors.append(f"Missing core documentation: {doc_path}")
            else:
                # Check if file is not empty
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    if len(content) < 100:  # Arbitrary minimum content length
                        self.validation_warnings.append(f"Documentation file appears incomplete: {doc_path}")
                except Exception as e:
                    self.validation_warnings.append(f"Cannot read documentation file {doc_path}: {e}")

def run_task_master_validation():
    """Run task-master CLI validation if available"""
    try:
        result = subprocess.run(
            ["npx", "task-master", "validate-all"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Task-master validation timed out"
    except FileNotFoundError:
        return False, "", "Task-master CLI not found"
    except Exception as e:
        return False, "", f"Task-master validation error: {e}"

def main():
    """Main validation function"""
    print("🚀 Starting WhatsApp Hotel Bot MVP Documentation Validation")
    print("=" * 60)
    
    # Initialize validator
    validator = DocumentationValidator()
    
    # Run validation
    success, errors, warnings = validator.validate_all()
    
    # Run task-master validation if available
    print("\n🔧 Running task-master validation...")
    tm_success, tm_stdout, tm_stderr = run_task_master_validation()
    
    # Report results
    print("\n" + "=" * 60)
    print("📊 VALIDATION RESULTS")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"  • {error}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  • {warning}")
    
    if tm_stderr:
        print(f"\n🔧 TASK-MASTER ISSUES:")
        print(f"  • {tm_stderr}")
    
    # Final status
    overall_success = success and tm_success
    
    if overall_success:
        print("\n✅ ALL VALIDATIONS PASSED")
        print("🚀 Project is ready for development!")
    else:
        print("\n❌ VALIDATION FAILED")
        print("🚫 Fix all errors before proceeding with development!")
        sys.exit(1)
    
    return overall_success

if __name__ == "__main__":
    main()
