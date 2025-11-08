#!/usr/bin/env python3
"""Validate .env.example files for documentation quality."""

import os
import glob

def check_env_example(file_path):
    """Check a single .env.example file for quality issues."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    issues = []
    if len(content) < 200:
        issues.append('Too basic - needs more documentation')
    if 'studio.nebius.ai' not in content:
        issues.append('Missing Nebius API key link')
    if '# Description:' not in content and '# Get your key:' not in content:
        issues.append('Missing detailed comments')
        
    return issues

def main():
    """Validate all .env.example files in the repository."""
    print("Validating .env.example files...")
    
    env_files = glob.glob('**/.env.example', recursive=True)
    total_issues = 0
    
    for env_file in env_files:
        issues = check_env_example(env_file)
        if issues:
            print(f'Issues in {env_file}:')
            for issue in issues:
                print(f'  - {issue}')
            total_issues += len(issues)
        else:
            print(f'✓ {env_file} is well documented')
    
    if total_issues > 10:
        print(f'Too many documentation issues ({total_issues})')
        exit(1)
    else:
        print(f'Documentation quality acceptable ({total_issues} minor issues)')

if __name__ == '__main__':
    main()