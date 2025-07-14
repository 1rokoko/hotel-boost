#!/usr/bin/env python3
"""
Database migration runner for WhatsApp Hotel Bot
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {command}")
    print(f"{'='*60}")
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"❌ {description} failed with return code {result.returncode}")
        return False
    else:
        print(f"✅ {description} completed successfully")
        return True

def check_alembic_setup():
    """Check if Alembic is properly set up"""
    print("Checking Alembic setup...")
    
    # Check if alembic is installed
    try:
        import alembic
        print(f"✅ Alembic version: {alembic.__version__}")
    except ImportError:
        print("❌ Alembic not installed")
        return False
    
    # Check if alembic.ini exists
    if os.path.exists("alembic.ini"):
        print("✅ alembic.ini exists")
    else:
        print("❌ alembic.ini missing")
        return False
    
    # Check if alembic directory exists
    if os.path.exists("alembic"):
        print("✅ alembic directory exists")
    else:
        print("❌ alembic directory missing")
        return False
    
    # Check if migration files exist
    migration_files = [
        "alembic/versions/001_create_all_tables.py",
        "alembic/versions/002_create_indexes.py",
        "alembic/versions/003_setup_row_level_security.py"
    ]
    
    for migration_file in migration_files:
        if os.path.exists(migration_file):
            print(f"✅ {migration_file} exists")
        else:
            print(f"⚠️  {migration_file} missing (will be created)")
    
    return True

def init_alembic():
    """Initialize Alembic"""
    return run_command(
        "alembic init alembic",
        "Initialize Alembic"
    )

def create_migration(message):
    """Create a new migration"""
    return run_command(
        f"alembic revision --autogenerate -m \"{message}\"",
        f"Create migration: {message}"
    )

def upgrade_database(revision="head"):
    """Upgrade database to specified revision"""
    return run_command(
        f"alembic upgrade {revision}",
        f"Upgrade database to {revision}"
    )

def downgrade_database(revision):
    """Downgrade database to specified revision"""
    return run_command(
        f"alembic downgrade {revision}",
        f"Downgrade database to {revision}"
    )

def show_current_revision():
    """Show current database revision"""
    return run_command(
        "alembic current",
        "Show current revision"
    )

def show_migration_history():
    """Show migration history"""
    return run_command(
        "alembic history --verbose",
        "Show migration history"
    )

def run_sql_script(script_path):
    """Run a SQL script directly"""
    if not os.path.exists(script_path):
        print(f"❌ SQL script {script_path} not found")
        return False
    
    # For PostgreSQL
    if "postgresql" in os.getenv("DATABASE_URL", ""):
        return run_command(
            f"psql $DATABASE_URL -f {script_path}",
            f"Run SQL script: {script_path}"
        )
    else:
        print(f"⚠️  SQL script execution not supported for current database")
        return True

def setup_database_roles():
    """Set up database roles and permissions"""
    return run_sql_script("scripts/setup_database_roles.sql")

def setup_row_level_security():
    """Set up Row Level Security"""
    return run_sql_script("scripts/setup_row_level_security.sql")

def create_performance_indexes():
    """Create performance indexes"""
    return run_sql_script("scripts/create_performance_indexes.sql")

def reset_database():
    """Reset database (downgrade to base and upgrade again)"""
    print("⚠️  This will reset the entire database!")
    confirm = input("Are you sure? (yes/no): ")
    
    if confirm.lower() != "yes":
        print("Database reset cancelled")
        return True
    
    success = True
    success &= downgrade_database("base")
    success &= upgrade_database("head")
    
    return success

def install_dependencies():
    """Install migration dependencies"""
    dependencies = [
        "alembic>=1.8.0",
        "psycopg2-binary>=2.9.0",  # For PostgreSQL
        "aiosqlite>=0.17.0"        # For SQLite async
    ]
    
    for dep in dependencies:
        success = run_command(
            f"pip install {dep}",
            f"Installing {dep}"
        )
        if not success:
            return False
    
    return True

def main():
    """Main migration runner function"""
    parser = argparse.ArgumentParser(description="WhatsApp Hotel Bot Database Migration Runner")
    parser.add_argument("--check", action="store_true", help="Check Alembic setup")
    parser.add_argument("--install", action="store_true", help="Install migration dependencies")
    parser.add_argument("--init", action="store_true", help="Initialize Alembic")
    parser.add_argument("--create", type=str, help="Create new migration with message")
    parser.add_argument("--upgrade", nargs="?", const="head", help="Upgrade database (default: head)")
    parser.add_argument("--downgrade", type=str, help="Downgrade database to revision")
    parser.add_argument("--current", action="store_true", help="Show current revision")
    parser.add_argument("--history", action="store_true", help="Show migration history")
    parser.add_argument("--setup-roles", action="store_true", help="Set up database roles")
    parser.add_argument("--setup-rls", action="store_true", help="Set up Row Level Security")
    parser.add_argument("--create-indexes", action="store_true", help="Create performance indexes")
    parser.add_argument("--reset", action="store_true", help="Reset database (DANGEROUS)")
    parser.add_argument("--sql", type=str, help="Run SQL script file")
    
    args = parser.parse_args()
    
    # Change to project directory
    os.chdir(project_root)
    
    if args.check:
        if check_alembic_setup():
            print("\n✅ Alembic setup is ready!")
            return 0
        else:
            print("\n❌ Alembic setup has issues")
            return 1
    
    if args.install:
        if install_dependencies():
            print("\n✅ Migration dependencies installed successfully!")
            return 0
        else:
            print("\n❌ Failed to install migration dependencies")
            return 1
    
    # Check setup before running migrations
    if not check_alembic_setup() and not args.init:
        print("\n❌ Alembic setup check failed. Run with --init to initialize.")
        return 1
    
    success = True
    
    if args.init:
        success &= init_alembic()
    
    if args.create:
        success &= create_migration(args.create)
    
    if args.upgrade is not None:
        success &= upgrade_database(args.upgrade)
    
    if args.downgrade:
        success &= downgrade_database(args.downgrade)
    
    if args.current:
        success &= show_current_revision()
    
    if args.history:
        success &= show_migration_history()
    
    if args.setup_roles:
        success &= setup_database_roles()
    
    if args.setup_rls:
        success &= setup_row_level_security()
    
    if args.create_indexes:
        success &= create_performance_indexes()
    
    if args.reset:
        success &= reset_database()
    
    if args.sql:
        success &= run_sql_script(args.sql)
    
    # If no specific action was requested, show current status
    if not any([args.init, args.create, args.upgrade is not None, args.downgrade,
                args.current, args.history, args.setup_roles, args.setup_rls,
                args.create_indexes, args.reset, args.sql]):
        print("No specific action requested. Showing current status...")
        success &= show_current_revision()
        success &= show_migration_history()
    
    if success:
        print("\n🎉 All requested migration operations completed successfully!")
        return 0
    else:
        print("\n💥 Some migration operations failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
