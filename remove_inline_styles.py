#!/usr/bin/env python3
"""
Remove inline styles from admin_dashboard.html
"""

def remove_inline_styles():
    """Remove all inline styles between the comment and empty line"""
    
    with open('app/templates/admin_dashboard.html', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the start and end of the styles block
    start_idx = None
    end_idx = None
    
    for i, line in enumerate(lines):
        if '<!-- Styles moved to external CSS file -->' in line:
            start_idx = i + 1  # Start after the comment
        elif start_idx is not None and line.strip() == '':
            end_idx = i
            break
    
    if start_idx is not None and end_idx is not None:
        # Remove the lines between start and end
        new_lines = lines[:start_idx] + lines[end_idx:]
        
        with open('app/templates/admin_dashboard.html', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✅ Removed {end_idx - start_idx} lines of inline styles")
        print(f"   Lines {start_idx + 1} to {end_idx} removed")
    else:
        print("❌ Could not find style block boundaries")

if __name__ == "__main__":
    remove_inline_styles()
