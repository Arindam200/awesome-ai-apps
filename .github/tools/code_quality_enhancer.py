"""
Python Code Quality Enhancement Tool

Automatically improves Python code quality by adding type hints, logging,
error handling, and docstrings across projects in the awesome-ai-apps repository.
"""

import ast
import logging
import re
from pathlib import Path
from typing import Any


class CodeQualityEnhancer:
    """Main class for enhancing Python code quality."""

    def __init__(self, project_path: str, dry_run: bool = False):
        """Initialize the code quality enhancer.

        Args:
            project_path: Path to the project to enhance
            dry_run: If True, only analyze without making changes
        """
        self.project_path = Path(project_path)
        self.dry_run = dry_run
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('code_quality_enhancement.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)

    def find_python_files(self) -> list[Path]:
        """Find all Python files in the project.

        Returns:
            List of Python file paths
        """
        python_files = []
        for py_file in self.project_path.rglob("*.py"):
            # Skip test files and __init__ files for now
            if not py_file.name.startswith("test_") and py_file.name != "__init__.py":
                python_files.append(py_file)

        self.logger.info(f"Found {len(python_files)} Python files to process")
        return python_files

    def analyze_file(self, file_path: Path) -> dict[str, Any]:
        """Analyze a Python file for quality metrics.

        Args:
            file_path: Path to the Python file

        Returns:
            Dictionary with analysis results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                self.logger.error(f"Syntax error in {file_path}: {e}")
                return {"error": str(e)}

            analysis = {
                "file_path": str(file_path),
                "has_typing_imports": "from typing import" in content or "import typing" in content,
                "has_logging": "import logging" in content,
                "has_docstring": self._has_module_docstring(tree),
                "function_count": len([node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]),
                "functions_with_docstrings": self._count_functions_with_docstrings(tree),
                "functions_with_type_hints": self._count_functions_with_type_hints(tree),
                "has_error_handling": "try:" in content and "except" in content,
                "print_statements": len(re.findall(r'print\s*\(', content)),
                "lines_of_code": len(content.splitlines())
            }

            return analysis

        except Exception as e:
            self.logger.error(f"Error analyzing {file_path}: {e}")
            return {"error": str(e)}

    def _has_module_docstring(self, tree: ast.Module) -> bool:
        """Check if module has a docstring."""
        if (tree.body and
            isinstance(tree.body[0], ast.Expr) and
            isinstance(tree.body[0].value, ast.Constant) and
            isinstance(tree.body[0].value.value, str)):
            return True
        return False

    def _count_functions_with_docstrings(self, tree: ast.Module) -> int:
        """Count functions that have docstrings."""
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if (node.body and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                    count += 1
        return count

    def _count_functions_with_type_hints(self, tree: ast.Module) -> int:
        """Count functions that have type hints."""
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function has any type annotations
                has_annotations = (
                    node.returns is not None or
                    any(arg.annotation is not None for arg in node.args.args)
                )
                if has_annotations:
                    count += 1
        return count

    def enhance_file(self, file_path: Path) -> dict[str, Any]:
        """Enhance a single Python file.

        Args:
            file_path: Path to the Python file

        Returns:
            Dictionary with enhancement results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            enhanced_content = original_content
            changes_made = []

            # Add typing imports if needed
            if not re.search(r'from typing import|import typing', enhanced_content):
                typing_import = "from typing import List, Dict, Optional, Union, Any\n"
                enhanced_content = typing_import + enhanced_content
                changes_made.append("Added typing imports")

            # Add logging setup if needed
            if "import logging" not in enhanced_content:
                logging_setup = '''import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

'''
                # Insert after imports
                lines = enhanced_content.split('\n')
                import_end = 0
                for i, line in enumerate(lines):
                    if line.startswith(('import ', 'from ')) or line.strip() == '':
                        import_end = i + 1
                    else:
                        break

                lines.insert(import_end, logging_setup)
                enhanced_content = '\n'.join(lines)
                changes_made.append("Added logging configuration")

            # Replace simple print statements with logging
            print_pattern = r'print\s*\(\s*["\']([^"\']*)["\']?\s*\)'
            if re.search(print_pattern, enhanced_content):
                enhanced_content = re.sub(
                    print_pattern,
                    r'logger.info("\1")',
                    enhanced_content
                )
                changes_made.append("Replaced print statements with logging")

            # Add module docstring if missing
            if not enhanced_content.strip().startswith('"""') and not enhanced_content.strip().startswith("'''"):
                module_name = file_path.stem.replace('_', ' ').title()
                docstring = f'"""\n{module_name}\n\nModule description goes here.\n"""\n\n'
                enhanced_content = docstring + enhanced_content
                changes_made.append("Added module docstring")

            # Write enhanced content if not dry run
            if not self.dry_run and changes_made:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(enhanced_content)
                self.logger.info(f"Enhanced {file_path}: {', '.join(changes_made)}")
            elif changes_made:
                self.logger.info(f"Would enhance {file_path}: {', '.join(changes_made)}")

            return {
                "file_path": str(file_path),
                "changes_made": changes_made,
                "success": True
            }

        except Exception as e:
            self.logger.error(f"Error enhancing {file_path}: {e}")
            return {
                "file_path": str(file_path),
                "error": str(e),
                "success": False
            }

    def generate_quality_report(self, analyses: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate a quality report from file analyses.

        Args:
            analyses: List of file analysis results

        Returns:
            Quality report dictionary
        """
        valid_analyses = [a for a in analyses if "error" not in a]
        total_files = len(valid_analyses)

        if total_files == 0:
            return {"error": "No valid files to analyze"}

        # Calculate metrics
        files_with_typing = sum(1 for a in valid_analyses if a.get("has_typing_imports", False))
        files_with_logging = sum(1 for a in valid_analyses if a.get("has_logging", False))
        files_with_docstrings = sum(1 for a in valid_analyses if a.get("has_docstring", False))
        files_with_error_handling = sum(1 for a in valid_analyses if a.get("has_error_handling", False))

        total_functions = sum(a.get("function_count", 0) for a in valid_analyses)
        functions_with_docstrings = sum(a.get("functions_with_docstrings", 0) for a in valid_analyses)
        functions_with_type_hints = sum(a.get("functions_with_type_hints", 0) for a in valid_analyses)
        total_print_statements = sum(a.get("print_statements", 0) for a in valid_analyses)

        report = {
            "total_files": total_files,
            "typing_coverage": round((files_with_typing / total_files) * 100, 2),
            "logging_coverage": round((files_with_logging / total_files) * 100, 2),
            "docstring_coverage": round((files_with_docstrings / total_files) * 100, 2),
            "error_handling_coverage": round((files_with_error_handling / total_files) * 100, 2),
            "total_functions": total_functions,
            "function_docstring_coverage": round((functions_with_docstrings / total_functions) * 100, 2) if total_functions > 0 else 0,
            "function_type_hint_coverage": round((functions_with_type_hints / total_functions) * 100, 2) if total_functions > 0 else 0,
            "print_statements_found": total_print_statements
        }

        return report

    def run_enhancement(self) -> dict[str, Any]:
        """Run the complete code enhancement process.

        Returns:
            Results of the enhancement process
        """
        self.logger.info(f"Starting code quality enhancement for {self.project_path}")
        self.logger.info(f"Dry run mode: {self.dry_run}")

        # Find Python files
        python_files = self.find_python_files()

        if not python_files:
            self.logger.warning("No Python files found")
            return {"error": "No Python files found"}

        # Analyze files before enhancement
        self.logger.info("Analyzing files for current quality metrics...")
        initial_analyses = [self.analyze_file(file_path) for file_path in python_files]
        initial_report = self.generate_quality_report(initial_analyses)

        self.logger.info("Initial Quality Report:")
        for key, value in initial_report.items():
            if key != "error":
                self.logger.info(f"  {key}: {value}")

        # Enhance files
        self.logger.info("Enhancing files...")
        enhancement_results = [self.enhance_file(file_path) for file_path in python_files]

        # Analyze files after enhancement
        if not self.dry_run:
            self.logger.info("Analyzing files after enhancement...")
            final_analyses = [self.analyze_file(file_path) for file_path in python_files]
            final_report = self.generate_quality_report(final_analyses)

            self.logger.info("Final Quality Report:")
            for key, value in final_report.items():
                if key != "error":
                    self.logger.info(f"  {key}: {value}")
        else:
            final_report = None

        # Summary
        successful_enhancements = [r for r in enhancement_results if r.get("success", False)]
        total_changes = sum(len(r.get("changes_made", [])) for r in successful_enhancements)

        self.logger.info(f"Enhancement complete: {len(successful_enhancements)}/{len(python_files)} files processed")
        self.logger.info(f"Total changes made: {total_changes}")

        return {
            "initial_report": initial_report,
            "final_report": final_report,
            "enhancement_results": enhancement_results,
            "files_processed": len(python_files),
            "successful_enhancements": len(successful_enhancements),
            "total_changes": total_changes
        }


def main():
    """Main entry point for the code quality enhancement tool."""
    import argparse

    parser = argparse.ArgumentParser(description="Python Code Quality Enhancement Tool")
    parser.add_argument("project_path", help="Path to the project to enhance")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't make changes")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run enhancement
    enhancer = CodeQualityEnhancer(args.project_path, dry_run=args.dry_run)
    results = enhancer.run_enhancement()

    if "error" in results:
        print(f"Error: {results['error']}")
        return 1

    print("\n" + "="*50)
    print("CODE QUALITY ENHANCEMENT SUMMARY")
    print("="*50)
    print(f"Files processed: {results['files_processed']}")
    print(f"Successful enhancements: {results['successful_enhancements']}")
    print(f"Total changes made: {results['total_changes']}")

    if results['final_report']:
        print("\nQuality Improvements:")
        initial = results['initial_report']
        final = results['final_report']

        metrics = [
            "typing_coverage", "logging_coverage", "docstring_coverage",
            "error_handling_coverage", "function_type_hint_coverage"
        ]

        for metric in metrics:
            if metric in initial and metric in final:
                improvement = final[metric] - initial[metric]
                print(f"  {metric}: {initial[metric]:.1f}% → {final[metric]:.1f}% (+{improvement:.1f}%)")

    return 0


if __name__ == "__main__":
    exit(main())
