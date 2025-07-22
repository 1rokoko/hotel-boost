#!/usr/bin/env python3
"""
Admin Dashboard Version Management Script

This script helps manage versions and track changes in admin_dashboard.html

Usage:
    python scripts/update_dashboard_version.py --version "2.2.0" --changes "Added new feature X"
    python scripts/update_dashboard_version.py --list-versions
    python scripts/update_dashboard_version.py --current-version
"""

import argparse
import re
import datetime
from pathlib import Path

# File paths
DASHBOARD_FILE = Path("app/templates/admin_dashboard.html")
CHANGELOG_FILE = Path("app/templates/admin_dashboard_changelog.md")

def get_current_version():
    """Extract current version from admin_dashboard.html"""
    if not DASHBOARD_FILE.exists():
        return None
    
    content = DASHBOARD_FILE.read_text(encoding='utf-8')
    match = re.search(r'Admin Dashboard v(\d+\.\d+\.\d+)', content)
    return match.group(1) if match else None

def update_dashboard_version(new_version, changes):
    """Update version in admin_dashboard.html header comment"""
    if not DASHBOARD_FILE.exists():
        print(f"Error: {DASHBOARD_FILE} not found")
        return False
    
    content = DASHBOARD_FILE.read_text(encoding='utf-8')
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # Create new header comment
    new_header = f'''<!--
    Admin Dashboard v{new_version} - {today}
    
    🎯 LATEST CHANGES:
    {changes}
    
    📝 See admin_dashboard_changelog.md for complete version history
    🔧 Total Functions: 50+ | API Endpoints: 15+ | Lines: 4800+
-->'''
    
    # Replace existing header comment
    pattern = r'<!--.*?-->'
    updated_content = re.sub(pattern, new_header, content, flags=re.DOTALL)
    
    DASHBOARD_FILE.write_text(updated_content, encoding='utf-8')
    print(f"✅ Updated admin_dashboard.html to version {new_version}")
    return True

def add_changelog_entry(version, changes):
    """Add new entry to changelog"""
    if not CHANGELOG_FILE.exists():
        print(f"Error: {CHANGELOG_FILE} not found")
        return False
    
    content = CHANGELOG_FILE.read_text(encoding='utf-8')
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # Create new changelog entry
    new_entry = f'''### Version {version} - {today}
**🎯 {changes}**

#### ✅ Changes:
- {changes}

---

'''
    
    # Insert after the first "### Version" line
    lines = content.split('\n')
    insert_index = None
    
    for i, line in enumerate(lines):
        if line.startswith('### Version') and 'Current' in line:
            # Update current version line
            lines[i] = f"### Version {version} - {today} (Current)"
            insert_index = i + 1
            break
    
    if insert_index:
        # Find next version entry and mark it as not current
        for j in range(insert_index, len(lines)):
            if lines[j].startswith('### Version') and '(Current)' not in lines[j]:
                break
            if lines[j].startswith('### Version') and '(Current)' in lines[j]:
                lines[j] = lines[j].replace(' (Current)', '')
                break
        
        # Insert new entry after current version
        lines.insert(insert_index + 1, '')
        lines.insert(insert_index + 2, new_entry)
    
    CHANGELOG_FILE.write_text('\n'.join(lines), encoding='utf-8')
    print(f"✅ Added changelog entry for version {version}")
    return True

def list_versions():
    """List all versions from changelog"""
    if not CHANGELOG_FILE.exists():
        print(f"Error: {CHANGELOG_FILE} not found")
        return
    
    content = CHANGELOG_FILE.read_text(encoding='utf-8')
    versions = re.findall(r'### Version (\d+\.\d+\.\d+) - (\d{4}-\d{2}-\d{2})', content)
    
    print("📋 Version History:")
    for version, date in versions:
        current = " (Current)" if version == get_current_version() else ""
        print(f"  • v{version} - {date}{current}")

def main():
    parser = argparse.ArgumentParser(description="Manage admin dashboard versions")
    parser.add_argument("--version", help="New version number (e.g., 2.2.0)")
    parser.add_argument("--changes", help="Description of changes")
    parser.add_argument("--list-versions", action="store_true", help="List all versions")
    parser.add_argument("--current-version", action="store_true", help="Show current version")
    
    args = parser.parse_args()
    
    if args.current_version:
        current = get_current_version()
        print(f"Current version: {current}" if current else "No version found")
    
    elif args.list_versions:
        list_versions()
    
    elif args.version and args.changes:
        if update_dashboard_version(args.version, args.changes):
            add_changelog_entry(args.version, args.changes)
            print(f"🎉 Successfully updated to version {args.version}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
