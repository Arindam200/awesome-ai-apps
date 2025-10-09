#!/usr/bin/env python3
"""Validate project structures across the repository."""

import os
import sys
def main():
    """Validate project structures and file requirements."""
    print("Validating project structures...")

    categories = {
        'starter_ai_agents': 'Starter AI Agents',
        'simple_ai_agents': 'Simple AI Agents',
        'rag_apps': 'RAG Applications',
        'advance_ai_agents': 'Advanced AI Agents',
        'mcp_ai_agents': 'MCP Agents',
        'memory_agents': 'Memory Agents'
    }

    required_files = ['README.md']
    recommended_files = ['.env.example', 'requirements.txt', 'pyproject.toml']

    total_projects = 0
    compliant_projects = 0

    for category, name in categories.items():
        if not os.path.exists(category):
            print(f' Category missing: {category}')
            continue

        projects = [d for d in os.listdir(category) if os.path.isdir(os.path.join(category, d))]
        print(f'{name}: {len(projects)} projects')

        for project in projects:
            project_path = os.path.join(category, project)
            total_projects += 1

            missing_required = []
            missing_recommended = []

            for file in required_files:
                if not os.path.exists(os.path.join(project_path, file)):
                    missing_required.append(file)

            for file in recommended_files:
                if not os.path.exists(os.path.join(project_path, file)):
                    missing_recommended.append(file)

            if not missing_required:
                compliant_projects += 1
                if not missing_recommended:
                    print(f'   {project} - Complete')
                else:
                    print(f'   {project} - Missing: {missing_recommended}')
            else:
                print(f'   {project} - Missing required: {missing_required}')

    compliance_rate = (compliant_projects / total_projects) * 100 if total_projects else 0
    print(f'Overall compliance: {compliance_rate:.1f}% ({compliant_projects}/{total_projects})')

    if compliance_rate < 90:
        print(' Project structure compliance below 90%')
        sys.exit(1)
    else:
        print(' Good project structure compliance')

if __name__ == '__main__':
    main()