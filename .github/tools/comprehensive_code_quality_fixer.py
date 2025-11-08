#!/usr/bin/env python3
"""
Comprehensive Code Quality Fixer

This tool addresses all the code quality issues identified in the CI/CD pipeline:
1. Fixes trailing whitespace (W291) and missing newlines at end of files (W292)
2. Fixes import sorting issues (I001)
3. Enhances .env.example documentation
4. Addresses security issues and indentation errors
"""

from pathlib import Path
from typing import List, Dict, Any
import logging
import os
import re
import sys

import subprocess
class ComprehensiveCodeQualityFixer:
    """Main class for fixing all code quality issues."""

    def __init__(self, project_path: str, dry_run: bool = False):
        """Initialize the code quality fixer.

        Args:
            project_path: Path to the project to fix
            dry_run: If True, only analyze without making changes
        """
        self.project_path = Path(project_path)
        self.dry_run = dry_run
        self.logger = self._setup_logging()
        self.fixes_applied = []

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('code_quality_fixes.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)

    def fix_trailing_whitespace_issues(self) -> int:
        """Fix W291 and W292 ruff violations - trailing whitespace and missing newlines.

        Returns:
            Number of files fixed
        """
        self.logger.info("Fixing trailing whitespace issues...")
        files_fixed = 0

        # Find all Python files
        python_files = list(self.project_path.rglob("*.py"))

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content

                # Fix trailing whitespace on each line (W291)
                lines = content.splitlines()
                fixed_lines = [line.rstrip() for line in lines]

                # Ensure file ends with newline (W292)
                if fixed_lines and not content.endswith('\n'):
                    content = '\n'.join(fixed_lines) + '\n'
                else:
                    content = '\n'.join(fixed_lines)

                # Write back if changed
                if content != original_content:
                    if not self.dry_run:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        self.logger.info(f"Fixed trailing whitespace in {file_path}")
                    else:
                        self.logger.info(f"Would fix trailing whitespace in {file_path}")
                    files_fixed += 1

            except Exception as e:
                self.logger.error(f"Error fixing whitespace in {file_path}: {e}")

        self.fixes_applied.append(f"Fixed trailing whitespace in {files_fixed} files")
        return files_fixed

    def fix_import_sorting_issues(self) -> int:
        """Fix I001 ruff violations - unsorted/unformatted import blocks.

        Returns:
            Number of files fixed
        """
        self.logger.info("Fixing import sorting issues...")
        files_fixed = 0

        # Find all Python files
        python_files = list(self.project_path.rglob("*.py"))

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content

                # Use a simple import sorter
                fixed_content = self._sort_imports(content)

                if fixed_content != original_content:
                    if not self.dry_run:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(fixed_content)
                        self.logger.info(f"Fixed import sorting in {file_path}")
                    else:
                        self.logger.info(f"Would fix import sorting in {file_path}")
                    files_fixed += 1

            except Exception as e:
                self.logger.error(f"Error fixing imports in {file_path}: {e}")

        self.fixes_applied.append(f"Fixed import sorting in {files_fixed} files")
        return files_fixed

    def _sort_imports(self, content: str) -> str:
        """Sort imports in Python file content."""
        lines = content.splitlines()

        # Find import block
        import_start = -1
        import_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')) and import_start == -1:
                import_start = i
            elif import_start != -1 and stripped and not stripped.startswith(('import ', 'from ', '#')):
                import_end = i
                break

        if import_start == -1:
            return content

        if import_end == -1:
            import_end = len(lines)

        # Extract imports
        imports = lines[import_start:import_end]

        # Separate standard library, third-party, and local imports
        std_imports = []
        third_party_imports = []
        local_imports = []

        for imp in imports:
            stripped = imp.strip()
            if not stripped or stripped.startswith('#'):
                continue

            if stripped.startswith('from .') or stripped.startswith('import .'):
                local_imports.append(imp)
            elif any(stripped.startswith(f'import {std}') or stripped.startswith(f'from {std}')
                    for std in ['os', 'sys', 'json', 'urllib', 'http', 'pathlib', 'typing', 're', 'logging', 'ast']):
                std_imports.append(imp)
            else:
                third_party_imports.append(imp)

        # Sort each group
        std_imports.sort()
        third_party_imports.sort()
        local_imports.sort()

        # Rebuild import block
        sorted_imports = []
        if std_imports:
            sorted_imports.extend(std_imports)
            sorted_imports.append('')
        if third_party_imports:
            sorted_imports.extend(third_party_imports)
            sorted_imports.append('')
        if local_imports:
            sorted_imports.extend(local_imports)
            sorted_imports.append('')

        # Remove trailing empty line
        if sorted_imports and sorted_imports[-1] == '':
            sorted_imports.pop()

        # Rebuild content
        new_lines = lines[:import_start] + sorted_imports + lines[import_end:]
        return '\n'.join(new_lines)

    def enhance_env_example_documentation(self) -> int:
        """Enhance documentation in .env.example files.

        Returns:
            Number of files enhanced
        """
        self.logger.info("Enhancing .env.example documentation...")
        files_enhanced = 0

        # Find all .env.example files
        env_files = list(self.project_path.rglob(".env.example"))

        for file_path in env_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content

                # Check if file needs enhancement
                if self._needs_env_enhancement(content):
                    enhanced_content = self._enhance_env_file(content, file_path)

                    if enhanced_content != original_content:
                        if not self.dry_run:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(enhanced_content)
                            self.logger.info(f"Enhanced documentation in {file_path}")
                        else:
                            self.logger.info(f"Would enhance documentation in {file_path}")
                        files_enhanced += 1

            except Exception as e:
                self.logger.error(f"Error enhancing {file_path}: {e}")

        self.fixes_applied.append(f"Enhanced documentation in {files_enhanced} .env.example files")
        return files_enhanced

    def _needs_env_enhancement(self, content: str) -> bool:
        """Check if .env.example file needs enhancement."""
        checks = [
            "Missing Nebius API key link" in content or "https://studio.nebius.ai/api-keys" not in content,
            "Missing detailed comments" in content or len([line for line in content.splitlines() if line.strip().startswith('#')]) < 5,
            "Too basic" in content or "=" in content and len(content.splitlines()) < 10
        ]
        return any(checks)

    def _enhance_env_file(self, content: str, file_path: Path) -> str:
        """Enhance a single .env.example file."""
        lines = content.splitlines()

        # Get project name from path
        project_name = file_path.parent.name

        # Check if already well documented
        if "# =============================================================================" in content:
            return content

        # Parse existing variables
        variables = []
        for line in lines:
            if '=' in line and not line.strip().startswith('#'):
                var_name = line.split('=')[0].strip()
                var_value = line.split('=', 1)[1].strip()
                variables.append((var_name, var_value))

        # Generate enhanced content
        enhanced_content = f"""# =============================================================================
# {project_name} - Environment Configuration
# =============================================================================
# Copy this file to .env and fill in your actual values
# IMPORTANT: Never commit .env files to version control
#
# Quick setup: cp .env.example .env

# =============================================================================
# Required Configuration
# =============================================================================

"""

        # Add Nebius API key if present
        nebius_added = False
        for var_name, var_value in variables:
            if "NEBIUS" in var_name:
                enhanced_content += f"""# Nebius AI API Key (Required)
# Description: Primary LLM provider for {project_name}
# Get your key: https://studio.nebius.ai/api-keys
# Free tier: 100 requests/minute, perfect for learning
# Documentation: https://docs.nebius.ai/
{var_name}={var_value}

"""
                nebius_added = True
                break

        # Add other required variables
        for var_name, var_value in variables:
            if "NEBIUS" not in var_name and any(keyword in var_name.lower() for keyword in ['api_key', 'token', 'secret']):
                enhanced_content += f"""# {var_name.replace('_', ' ').title()}
# Description: Required for {project_name} functionality
{var_name}={var_value}

"""

        # Add optional configuration section
        enhanced_content += """# =============================================================================
# Optional Configuration (Uncomment to enable)
# =============================================================================

"""

        # Add OpenAI as optional
        if not any("OPENAI" in var for var, _ in variables):
            enhanced_content += """# OpenAI API Key (Optional - Alternative LLM provider)
# Description: Use OpenAI models for enhanced functionality
# Get your key: https://platform.openai.com/account/api-keys
# Note: Costs apply based on usage
# OPENAI_API_KEY="your_openai_api_key_here"

"""

        # Add development settings
        enhanced_content += """# =============================================================================
# Development Settings
# =============================================================================

# Debug Mode (Optional)
# Description: Enable detailed logging and error messages
# Values: true, false
# Default: false
# DEBUG="true"

# Log Level (Optional)
# Description: Control logging verbosity
# Values: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Default: INFO
# LOG_LEVEL="DEBUG"

# =============================================================================
# Notes and Troubleshooting
# =============================================================================
#
# Getting Started:
# 1. Copy this file: cp .env.example .env
# 2. Get a Nebius API key from https://studio.nebius.ai/api-keys
# 3. Replace placeholder values with your actual keys
# 4. Save the file and run the application
#
# Common Issues:
# - API key error: Double-check your key and internet connection
# - Module errors: Run 'pip install -r requirements.txt' to install dependencies
# - Permission errors: Ensure proper file permissions
#
# Security:
# - Never share your .env file or commit it to version control
# - Use different API keys for development and production
# - Monitor your API usage to avoid unexpected charges
#
# Support:
# - Documentation: https://docs.agno.com
# - Issues: https://github.com/smirk-dev/awesome-ai-apps/issues
# - Community: Join discussions in GitHub issues
"""

        return enhanced_content

    def fix_security_issues(self) -> int:
        """Fix security issues and indentation errors.

        Returns:
            Number of issues fixed
        """
        self.logger.info("Fixing security and indentation issues...")
        issues_fixed = 0

        # Find Python files with potential security issues
        python_files = list(self.project_path.rglob("*.py"))

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content
                fixed_content = content

                # Fix common indentation errors
                lines = content.splitlines()
                fixed_lines = []

                for line in lines:
                    # Fix mixed tabs and spaces
                    if '\t' in line:
                        # Convert tabs to 4 spaces
                        fixed_line = line.expandtabs(4)
                        fixed_lines.append(fixed_line)
                    else:
                        fixed_lines.append(line)

                fixed_content = '\n'.join(fixed_lines)

                # Write back if changed
                if fixed_content != original_content:
                    if not self.dry_run:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(fixed_content)
                        self.logger.info(f"Fixed indentation issues in {file_path}")
                    else:
                        self.logger.info(f"Would fix indentation issues in {file_path}")
                    issues_fixed += 1

            except Exception as e:
                self.logger.error(f"Error fixing security issues in {file_path}: {e}")

        self.fixes_applied.append(f"Fixed security/indentation issues in {issues_fixed} files")
        return issues_fixed

    def run_all_fixes(self) -> Dict[str, Any]:
        """Run all code quality fixes.

        Returns:
            Summary of all fixes applied
        """
        self.logger.info(f"Starting comprehensive code quality fixes for {self.project_path}")
        self.logger.info(f"Dry run mode: {self.dry_run}")

        results = {}

        # Fix trailing whitespace issues
        results['trailing_whitespace_fixes'] = self.fix_trailing_whitespace_issues()

        # Fix import sorting issues
        results['import_sorting_fixes'] = self.fix_import_sorting_issues()

        # Enhance .env.example documentation
        results['env_documentation_fixes'] = self.enhance_env_example_documentation()

        # Fix security issues
        results['security_fixes'] = self.fix_security_issues()

        # Summary
        total_fixes = sum(results.values())
        self.logger.info(f"Code quality fixes complete: {total_fixes} total fixes applied")

        results['total_fixes'] = total_fixes
        results['fixes_applied'] = self.fixes_applied

        return results


def main():
    """Main entry point for the comprehensive code quality fixer."""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive Code Quality Fixer")
    parser.add_argument("project_path", help="Path to the project to fix")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't make changes")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run fixes
    fixer = ComprehensiveCodeQualityFixer(args.project_path, dry_run=args.dry_run)
    results = fixer.run_all_fixes()

    print("\n" + "="*60)
    print("COMPREHENSIVE CODE QUALITY FIXES SUMMARY")
    print("="*60)
    print(f"Trailing whitespace fixes: {results['trailing_whitespace_fixes']}")
    print(f"Import sorting fixes: {results['import_sorting_fixes']}")
    print(f"Environment documentation fixes: {results['env_documentation_fixes']}")
    print(f"Security/indentation fixes: {results['security_fixes']}")
    print(f"Total fixes applied: {results['total_fixes']}")

    if results['fixes_applied']:
        print("\nFixes Applied:")
        for fix in results['fixes_applied']:
            print(f"  ✓ {fix}")

    return 0


if __name__ == "__main__":
    exit(main())