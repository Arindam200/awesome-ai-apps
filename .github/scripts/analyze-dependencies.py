#!/usr/bin/env python3
"""Analyze dependency management across the repository."""

import os
import glob

def main():
    """Analyze dependency management modernization status."""
    print("Analyzing dependency management...")
    
    # Find all Python projects
    projects = []
    for root, dirs, files in os.walk('.'):
        if 'requirements.txt' in files or 'pyproject.toml' in files:
            if not any(exclude in root for exclude in ['.git', '__pycache__', '.venv', 'node_modules']):
                projects.append(root)
    
    print(f'Found {len(projects)} Python projects')
    
    modern_projects = 0
    legacy_projects = 0
    
    for project in projects:
        pyproject_path = os.path.join(project, 'pyproject.toml')
        requirements_path = os.path.join(project, 'requirements.txt')
        
        if os.path.exists(pyproject_path):
            with open(pyproject_path, 'r') as f:
                content = f.read()
            if 'requires-python' in content and 'hatchling' in content:
                print(f' {project} - Modern pyproject.toml')
                modern_projects += 1
            else:
                print(f' {project} - Basic pyproject.toml (needs enhancement)')
        elif os.path.exists(requirements_path):
            print(f' {project} - Legacy requirements.txt only')
            legacy_projects += 1
    
    modernization_rate = (modern_projects / len(projects)) * 100 if projects else 0
    print(f'Modernization rate: {modernization_rate:.1f}% ({modern_projects}/{len(projects)})')
    
    if modernization_rate < 50:
        print(' Less than 50% of projects use modern dependency management')
    else:
        print(' Good adoption of modern dependency management')

if __name__ == '__main__':
    main()