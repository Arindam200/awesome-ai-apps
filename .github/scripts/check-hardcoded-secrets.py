#!/usr/bin/env python3
"""Check for potential hardcoded secrets in Python files."""

import os
import re
import glob

def main():
    """Scan Python files for potential hardcoded secrets."""
    print("Checking for potential hardcoded secrets...")
    
    # Patterns for potential secrets
    secret_patterns = [
        r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
        r'password\s*=\s*["\'][^"\']+["\']',
        r'secret\s*=\s*["\'][^"\']+["\']',
        r'token\s*=\s*["\'][^"\']+["\']',
    ]
    
    issues_found = 0
    
    for py_file in glob.glob('**/*.py', recursive=True):
        if any(exclude in py_file for exclude in ['.git', '__pycache__', '.venv']):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for pattern in secret_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    match_text = match.group()
                    if 'your_' not in match_text.lower() and 'example' not in match_text.lower():
                        print(f'⚠ Potential hardcoded secret in {py_file}: {match_text[:50]}...')
                        issues_found += 1
        except Exception:
            continue
    
    if issues_found == 0:
        print('✓ No hardcoded secrets detected')
    else:
        print(f'Found {issues_found} potential hardcoded secrets')

if __name__ == '__main__':
    main()