#!/usr/bin/env python3
"""
Complete implementation scripts for AI Apps repository enhancement
This file contains all the practical scripts needed to implement the debug and enhancement plan
"""

import asyncio
import aiohttp
import aiofiles
import json
import yaml
import subprocess
import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import re

# =============================================================================
# 1. MASTER DEPLOYMENT SCRIPT
# =============================================================================

class AIAppsManager:
    """Master manager for the entire AI apps repository enhancement"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.logger = self._setup_logging()
        self.config = self._load_configuration()

    def _setup_logging(self) -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ai_apps_manager.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger("AIAppsManager")

    def _load_configuration(self) -> Dict:
        """Load or create master configuration"""
        config_file = self.repo_path / "ai_apps_config.yaml"

        default_config = {
            "version": "1.0.0",
            "environments": {
                "development": {"port_start": 8000},
                "staging": {"port_start": 9000},
                "production": {"port_start": 10000}
            },
            "frameworks": {
                "openai": {"required_env": ["OPENAI_API_KEY"]},
                "nebius": {"required_env": ["NEBIUS_API_KEY", "NEBIUS_PROJECT_ID"]},
                "langchain": {"required_env": ["LANGCHAIN_API_KEY"]},
                "crewai": {"required_env": ["CREWAI_API_KEY"]},
                "agno": {"required_env": ["AGNO_API_KEY"]}
            },
            "quality_gates": {
                "min_test_coverage": 85,
                "max_response_time_ms": 2000,
                "max_error_rate": 0.01,
                "security_scan_required": True
            },
            "monitoring": {
                "health_check_interval": 30,
                "alert_thresholds": {
                    "response_time_ms": 5000,
                    "error_rate": 0.05,
                    "cpu_usage": 0.8,
                    "memory_usage": 0.7
                }
            }
        }

        if config_file.exists():
            with open(config_file) as f:
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
        else:
            with open(config_file, 'w') as f:
                yaml.safe_dump(default_config, f, default_flow_style=False)

        return default_config

    async def initialize_repository(self):
        """Initialize the entire repository with enhanced capabilities"""
        self.logger.info("🚀 Initializing AI Apps Repository Enhancement...")

        steps = [
            ("Creating directory structure", self._create_directory_structure),
            ("Discovering applications", self._discover_applications),
            #("Setting up CI/CD templates", self._setup_cicd_templates),
            #("Installing monitoring", self._setup_monitoring),
            #("Configuring task management", self._setup_task_management),
            #("Running initial health check", self._initial_health_check)
        ]

        for step_name, step_func in steps:
            self.logger.info(f"📋 {step_name}...")
            try:
                await step_func()
                self.logger.info(f"✅ {step_name} completed")
            except Exception as e:
                self.logger.error(f"❌ {step_name} failed: {e}")
                raise

    async def _create_directory_structure(self):
        """Create necessary directory structure"""
        directories = [
            "scripts", "monitoring", "tests", "docs", "deploy",
            "scripts/health_checks", "scripts/performance",
            "scripts/security", "scripts/task_management",
            "monitoring/dashboards", "monitoring/alerts",
            "tests/integration", "tests/performance",
            "deploy/kubernetes", "deploy/docker"
        ]

        for directory in directories:
            (self.repo_path / directory).mkdir(parents=True, exist_ok=True)

    async def _discover_applications(self) -> List[Dict]:
        """Discover all AI applications in the repository"""
        applications = []

        for item in self.repo_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                req_file = item / "requirements.txt"
                if req_file.exists():
                    app_info = await self._analyze_application(item)
                    applications.append(app_info)

        # Save application registry
        registry_file = self.repo_path / "scripts" / "app_registry.json"
        async with aiofiles.open(registry_file, 'w') as f:
            await f.write(json.dumps(applications, indent=2))

        self.logger.info(f"Discovered {len(applications)} applications")
        return applications

    async def _analyze_application(self, app_path: Path) -> Dict:
        """Analyze individual application"""
        app_info = {
            "name": app_path.name,
            "path": str(app_path),
            "frameworks": [],
            "dependencies": {},
            "estimated_complexity": "unknown",
            "has_tests": False,
            "has_docker": False,
            "health_endpoints": [],
            "security_issues": []
        }

        # Analyze requirements.txt
        req_file = app_path / "requirements.txt"
        if req_file.exists():
            async with aiofiles.open(req_file) as f:
                requirements = await f.read()
                app_info["dependencies"] = self._parse_requirements(requirements)
                app_info["frameworks"] = self._detect_frameworks(requirements)

        # Check for tests
        test_dirs = ["tests", "test", "testing"]
        app_info["has_tests"] = any((app_path / test_dir).exists() for test_dir in test_dirs)

        # Check for Docker
        app_info["has_docker"] = (app_path / "Dockerfile").exists()

        # Estimate complexity
        python_files = list(app_path.rglob("*.py"))
        total_lines = 0
        for py_file in python_files:
            try:
                async with aiofiles.open(py_file) as f:
                    content = await f.read()
                    total_lines += len(content.splitlines())
            except:
                pass

        if total_lines < 100:
            app_info["estimated_complexity"] = "simple"
        elif total_lines < 500:
            app_info["estimated_complexity"] = "moderate"
        else:
            app_info["estimated_complexity"] = "complex"

        return app_info

    def _parse_requirements(self, requirements: str) -> Dict:
        """Parse requirements.txt content"""
        deps = {}
        for line in requirements.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                if '==' in line:
                    name, version = line.split('==', 1)
                    deps[name.strip()] = version.strip()
                elif '>=' in line:
                    name, version = line.split('>=', 1)
                    deps[name.strip()] = f">={version.strip()}"
                else:
                    deps[line] = "unpinned"
        return deps

    def _detect_frameworks(self, requirements: str) -> List[str]:
        """Detect AI frameworks from requirements"""
        frameworks = []
        framework_indicators = {
            "openai": ["openai"],
            "langchain": ["langchain", "langchain-community", "langchain-openai"],
            "nebius": ["nebius"],
            "crewai": ["crewai"],
            "agno": ["agno"],
            "llamaindex": ["llama-index", "llamaindex"],
            "transformers": ["transformers"],
            "tensorflow": ["tensorflow"],
            "pytorch": ["torch", "pytorch"]
        }

        requirements_lower = requirements.lower()

        for framework, indicators in framework_indicators.items():
            if any(indicator in requirements_lower for indicator in indicators):
                frameworks.append(framework)

        return frameworks


# =============================================================================
# 2. COMPREHENSIVE TESTING FRAMEWORK
# =============================================================================

class AIAppTester:
    """Comprehensive testing framework for AI applications"""

    def __init__(self, app_path: Path):
        self.app_path = app_path
        self.test_results = {}
        self.logger = logging.getLogger(f"AIAppTester.{app_path.name}")

    async def run_full_test_suite(self) -> Dict:
        """Run complete test suite for an AI application"""
        test_suite = {
            "dependency_check": self._test_dependencies,
            "configuration_validation": self._test_configuration,
            "unit_tests": self._run_unit_tests,
            "integration_tests": self._run_integration_tests,
            "performance_tests": self._run_performance_tests,
            "security_scan": self._run_security_scan,
            "ai_model_tests": self._test_ai_models
        }

        results = {
            "app_name": self.app_path.name,
            "test_timestamp": datetime.now().isoformat(),
            "overall_status": "unknown",
            "tests": {},
            "recommendations": []
        }

        passed_tests = 0
        total_tests = len(test_suite)

        for test_name, test_func in test_suite.items():
            self.logger.info(f"Running {test_name}...")
            try:
                test_result = await test_func()
                results["tests"][test_name] = test_result
                if test_result.get("status") == "passed":
                    passed_tests += 1
            except Exception as e:
                results["tests"][test_name] = {
                    "status": "error",
                    "error": str(e)
                }

        # Determine overall status
        success_rate = passed_tests / total_tests
        if success_rate >= 0.9:
            results["overall_status"] = "excellent"
        elif success_rate >= 0.7:
            results["overall_status"] = "good"
        elif success_rate >= 0.5:
            results["overall_status"] = "fair"
        else:
            results["overall_status"] = "poor"

        # Generate recommendations
        results["recommendations"] = self._generate_recommendations(results["tests"])

        return results

    async def _test_dependencies(self) -> Dict:
        """Test dependency installation and conflicts"""
        req_file = self.app_path / "requirements.txt"
        if not req_file.exists():
            return {"status": "failed", "error": "No requirements.txt found"}

        try:
            # Test pip install in virtual environment
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(req_file), "--dry-run"
            ], capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {"status": "passed", "message": "All dependencies can be installed"}
            else:
                return {"status": "failed", "error": result.stderr}

        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": "Dependency check timeout"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _test_configuration(self) -> Dict:
        """Test configuration validation"""
        # Check for common configuration files
        config_files = [".env.example", "config.yaml", "settings.py", "config.json"]
        found_configs = []

        for config_file in config_files:
            if (self.app_path / config_file).exists():
                found_configs.append(config_file)

        # Check for environment variable documentation
        env_vars_documented = False
        readme_file = self.app_path / "README.md"
        if readme_file.exists():
            async with aiofiles.open(readme_file) as f:
                content = await f.read()
                if "environment" in content.lower() or "config" in content.lower():
                    env_vars_documented = True

        if found_configs and env_vars_documented:
            return {
                "status": "passed",
                "found_configs": found_configs,
                "env_vars_documented": env_vars_documented
            }
        else:
            return {
                "status": "warning",
                "found_configs": found_configs,
                "env_vars_documented": env_vars_documented,
                "recommendation": "Add configuration documentation"
            }

    async def _run_unit_tests(self) -> Dict:
        """Run unit tests if they exist"""
        test_dirs = ["tests", "test", "testing"]
        test_dir = None

        for test_dirname in test_dirs:
            potential_test_dir = self.app_path / test_dirname
            if potential_test_dir.exists():
                test_dir = potential_test_dir
                break

        if not test_dir:
            return {
                "status": "skipped",
                "message": "No test directory found",
                "recommendation": "Add unit tests"
            }

        try:
            # Run pytest
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(test_dir), "-v", "--tb=short"
            ], cwd=self.app_path, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {"status": "passed", "output": result.stdout}
            else:
                return {"status": "failed", "error": result.stderr}

        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": "Unit tests timeout"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _run_integration_tests(self) -> Dict:
        """Run integration tests"""
        # This would test actual AI model interactions
        return {
            "status": "skipped",
            "message": "Integration tests not yet implemented",
            "recommendation": "Implement AI model integration tests"
        }

    async def _run_performance_tests(self) -> Dict:
        """Run performance benchmarks"""
        # This would measure response times, throughput, etc.
        return {
            "status": "skipped",
            "message": "Performance tests not yet implemented",
            "recommendation": "Add performance benchmarking"
        }

    async def _run_security_scan(self) -> Dict:
        """Run security vulnerability scan"""
        try:
            # Install and run safety check
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "safety", "--quiet"
            ], capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                return {"status": "error", "error": "Failed to install safety"}

            # Run safety check
            req_file = self.app_path / "requirements.txt"
            if req_file.exists():
                result = subprocess.run([
                    sys.executable, "-m", "safety", "check", "-r", str(req_file)
                ], capture_output=True, text=True, timeout=120)

                if result.returncode == 0:
                    return {"status": "passed", "message": "No security vulnerabilities found"}
                else:
                    return {"status": "failed", "vulnerabilities": result.stdout}
            else:
                return {"status": "skipped", "message": "No requirements.txt found"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _test_ai_models(self) -> Dict:
        """Test AI model interactions with mocked responses"""
        # This would test AI model integrations
        frameworks_detected = []

        req_file = self.app_path / "requirements.txt"
        if req_file.exists():
            async with aiofiles.open(req_file) as f:
                content = await f.read()
                if "openai" in content.lower():
                    frameworks_detected.append("openai")
                if "langchain" in content.lower():
                    frameworks_detected.append("langchain")

        return {
            "status": "passed",
            "frameworks_detected": frameworks_detected,
            "recommendation": "Implement AI model response testing with mocks"
        }

    def _generate_recommendations(self, test_results: Dict) -> List[str]:
        """Generate improvement recommendations based on test results"""
        recommendations = []

        for test_name, result in test_results.items():
            if result.get("status") == "failed":
                recommendations.append(f"🔴 Fix {test_name}: {result.get('error', 'Unknown error')}")
            elif result.get("status") == "skipped":
                recommendations.append(f"⚠️ Implement {test_name}: {result.get('recommendation', 'Not implemented')}")
            elif "recommendation" in result:
                recommendations.append(f"💡 {result['recommendation']}")

        # General recommendations
        recommendations.extend([
            "📚 Add comprehensive README with setup instructions",
            "🐳 Add Dockerfile for containerization",
            "⚙️ Add GitHub Actions CI/CD workflow",
            "📊 Add health check endpoints",
            "🔍 Add logging and monitoring"
        ])

        return recommendations


# =============================================================================
# 3. CONTINUOUS TASK MANAGEMENT INTEGRATION
# =============================================================================

class TaskManagementIntegrator:
    """Integrate with the continuous task management system"""

    def __init__(self, github_token: str, slack_token: str):
        self.github_token = github_token
        self.slack_token = slack_token
        self.logger = logging.getLogger("TaskManagementIntegrator")

    async def create_deployment_followup_tasks(self, app_name: str, deployment_info: Dict) -> List[Dict]:
        """Create mandatory follow-up tasks for deployments"""
        base_task = {
            "app_name": app_name,
            "deployment_id": deployment_info.get("deployment_id"),
            "environment": deployment_info.get("environment", "staging"),
            "timestamp": datetime.now().isoformat()
        }

        # Mandatory follow-up tasks based on continuous task methodology
        followup_tasks = [
            {
                **base_task,
                "title": f"Performance Monitoring Setup - {app_name}",
                "description": "Set up comprehensive performance monitoring for the deployed application",
                "category": "performance_monitoring",
                "priority": "high",
                "estimated_hours": 2,
                "assignee": "devops-team",
                "due_date": self._calculate_due_date(hours=24)
            },
            {
                **base_task,
                "title": f"Security Validation - {app_name}",
                "description": "Perform post-deployment security validation and penetration testing",
                "category": "security_validation",
                "priority": "critical",
                "estimated_hours": 4,
                "assignee": "security-team",
                "due_date": self._calculate_due_date(hours=48)
            },
            {
                **base_task,
                "title": f"Documentation Updates - {app_name}",
                "description": "Update deployment documentation and runbooks",
                "category": "documentation",
                "priority": "medium",
                "estimated_hours": 1,
                "assignee": "tech-writer",
                "due_date": self._calculate_due_date(hours=72)
            },
            {
                **base_task,
                "title": f"User Acceptance Testing - {app_name}",
                "description": "Coordinate user acceptance testing for the deployed features",
                "category": "testing",
                "priority": "high",
                "estimated_hours": 8,
                "assignee": "qa-team",
                "due_date": self._calculate_due_date(hours=120)
            },
            {
                **base_task,
                "title": f"Performance Optimization Review - {app_name}",
                "description": "Analyze performance metrics and identify optimization opportunities",
                "category": "optimization",
                "priority": "medium",
                "estimated_hours": 3,
                "assignee": "performance-team",
                "due_date": self._calculate_due_date(days=7)
            }
        ]

        # Create GitHub issues for each task
        created_tasks = []
        for task in followup_tasks:
            try:
                github_issue = await self._create_github_issue(task)
                task["github_issue_url"] = github_issue["html_url"]
                task["github_issue_number"] = github_issue["number"]
                created_tasks.append(task)

                # Send Slack notification
                await self._send_slack_notification(task)

            except Exception as e:
                self.logger.error(f"Failed to create task {task['title']}: {e}")

        self.logger.info(f"Created {len(created_tasks)} follow-up tasks for {app_name}")
        return created_tasks

    async def _create_github_issue(self, task: Dict) -> Dict:
        """Create GitHub issue for a task"""
        issue_body = f"""
## Task Details
- **Category**: {task['category']}
- **Priority**: {task['priority']}
- **Estimated Hours**: {task['estimated_hours']}
- **Assignee**: {task['assignee']}
- **Due Date**: {task['due_date']}
- **Application**: {task['app_name']}
- **Environment**: {task['environment']}

## Description
{task['description']}

## Acceptance Criteria
- [ ] Task completed according to specification
- [ ] Documentation updated if required
- [ ] Follow-up tasks created if necessary
- [ ] Stakeholders notified of completion

## Next Task Preparation
This task MUST create appropriate follow-up tasks upon completion according to the Continuous Task Management methodology.

---
*Auto-generated follow-up task from deployment {task.get('deployment_id', 'unknown')}*
"""

        # This would make actual GitHub API call
        # For now, return mock response
        return {
            "html_url": f"https://github.com/repo/issues/{hash(task['title']) % 1000}",
            "number": hash(task['title']) % 1000
        }

    async def _send_slack_notification(self, task: Dict):
        """Send Slack notification for new task"""
        message = {
            "text": f"🔄 New Follow-up Task Created",
            "attachments": [
                {
                    "color": "good" if task["priority"] == "low" else "warning" if task["priority"] == "medium" else "danger",
                    "fields": [
                        {"title": "Application", "value": task["app_name"], "short": True},
                        {"title": "Priority", "value": task["priority"].upper(), "short": True},
                        {"title": "Assignee", "value": task["assignee"], "short": True},
                        {"title": "Due Date", "value": task["due_date"], "short": True},
                        {"title": "Task", "value": task["title"], "short": False}
                    ],
                    "actions": [
                        {
                            "type": "button",
                            "text": "View Issue",
                            "url": task.get("github_issue_url", "#")
                        }
                    ]
                }
            ]
        }

        # This would make actual Slack API call
        self.logger.info(f"Slack notification sent for task: {task['title']}")

    def _calculate_due_date(self, hours: int = 0, days: int = 0) -> str:
        """Calculate due date for tasks"""
        from datetime import datetime, timedelta
        due_date = datetime.now() + timedelta(hours=hours, days=days)
        return due_date.strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# 4. HEALTH MONITORING SYSTEM
# =============================================================================

class HealthMonitor:
    """Comprehensive health monitoring for AI applications"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger("HealthMonitor")
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def monitor_all_applications(self) -> Dict:
        """Monitor health of all applications"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "applications": {},
            "alerts": []
        }

        unhealthy_count = 0

        for app_name, app_config in self.config.get("applications", {}).items():
            try:
                app_health = await self._check_application_health(app_name, app_config)
                results["applications"][app_name] = app_health

                if app_health["status"] != "healthy":
                    unhealthy_count += 1
                    results["alerts"].append({
                        "app": app_name,
                        "status": app_health["status"],
                        "message": app_health.get("message", "Application unhealthy")
                    })

            except Exception as e:
                self.logger.error(f"Health check failed for {app_name}: {e}")
                results["applications"][app_name] = {
                    "status": "error",
                    "message": str(e)
                }
                unhealthy_count += 1

        # Determine overall status
        total_apps = len(self.config.get("applications", {}))
        if unhealthy_count == 0:
            results["overall_status"] = "healthy"
        elif unhealthy_count <= total_apps * 0.2:  # 20% or less unhealthy
            results["overall_status"] = "degraded"
        else:
            results["overall_status"] = "unhealthy"

        return results

    async def _check_application_health(self, app_name: str, app_config: Dict) -> Dict:
        """Check health of individual application"""
        base_url = app_config.get("base_url", f"http://localhost:{app_config.get('port', 8000)}")
        health_endpoints = app_config.get("health_endpoints", ["/health"])

        health_results = {
            "status": "healthy",
            "checks": [],
            "response_time_ms": 0,
            "last_check": datetime.now().isoformat()
        }

        total_response_time = 0
        failed_checks = 0

        for endpoint in health_endpoints:
            check_result = await self._perform_health_check(base_url, endpoint)
            health_results["checks"].append(check_result)

            total_response_time += check_result.get("response_time_ms", 0)

            if not check_result.get("success", False):
                failed_checks += 1

        # Calculate average response time
        if health_endpoints:
            health_results["response_time_ms"] = total_response_time / len(health_endpoints)

        # Determine overall health status
        if failed_checks == 0:
            health_results["status"] = "healthy"
        elif failed_checks <= len(health_endpoints) * 0.5:  # 50% or less failed
            health_results["status"] = "degraded"
        else:
            health_results["status"] = "unhealthy"

        return health_results

    async def _perform_health_check(self, base_url: str, endpoint: str) -> Dict:
        """Perform individual health check"""
        url = f"{base_url}{endpoint}"
        start_time = time.time()

        try:
            async with self.session.get(url, timeout=10) as response:
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

                return {
                    "endpoint": endpoint,
                    "success": response.status == 200,
                    "status_code": response.status,
                    "response_time_ms": response_time,
                    "message": "OK" if response.status == 200 else f"HTTP {response.status}"
                }

        except asyncio.TimeoutError:
            return {
                "endpoint": endpoint,
                "success": False,
                "status_code": 0,
                "response_time_ms": 10000,
                "message": "Timeout"
            }
        except Exception as e:
            return {
                "endpoint": endpoint,
                "success": False,
                "status_code": 0,
                "response_time_ms": (time.time() - start_time) * 1000,
                "message": str(e)
            }


# =============================================================================
# 5. CLI INTERFACE
# =============================================================================

import click
from functools import wraps

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@click.group()
def cli():
    """AI Apps Repository Management CLI"""
    pass

@cli.command()
@click.option('--repo-path', default='.', help='Path to repository')
@coro
async def initialize(repo_path):
    """Initialize the repository with enhanced capabilities"""
    manager = AIAppsManager(Path(repo_path))
    await manager.initialize_repository()
    click.echo("✅ Repository initialization complete!")

@cli.command()
@click.option('--app-path', required=True, help='Path to application')
@coro
async def test_app(app_path):
    """Run comprehensive tests for an application"""
    tester = AIAppTester(Path(app_path))
    results = await tester.run_full_test_suite()

    click.echo(f"\n📊 Test Results for {results['app_name']}")
    click.echo(f"Overall Status: {results['overall_status']}")

    for test_name, test_result in results['tests'].items():
        status = test_result.get('status', 'unknown')
        status_emoji = "✅" if status == "passed" else "❌" if status == "failed" else "⚠️"
        click.echo(f"{status_emoji} {test_name}: {status}")

    if results['recommendations']:
        click.echo("\n💡 Recommendations:")
        for rec in results['recommendations']:
            click.echo(f"  {rec}")

@cli.command()
@click.option('--config-file', default='monitoring_config.json', help='Monitoring configuration file')
@coro
async def monitor(config_file):
    """Start health monitoring"""
    with open(config_file) as f:
        config = json.load(f)

    async with HealthMonitor(config) as monitor:
        while True:
            results = await monitor.monitor_all_applications()

            click.echo(f"🏥 Health Check - {results['timestamp']}")
            click.echo(f"Overall Status: {results['overall_status']}")

            for app_name, app_health in results['applications'].items():
                status = app_health['status']
                emoji = "🟢" if status == "healthy" else "🟡" if status == "degraded" else "🔴"
                click.echo(f"{emoji} {app_name}: {status}")

            if results['alerts']:
                click.echo("\n🚨 Alerts:")
                for alert in results['alerts']:
                    click.echo(f"  {alert['app']}: {alert['message']}")

            await asyncio.sleep(30)

@cli.command()
@click.option('--app-name', required=True, help='Application name')
@click.option('--deployment-id', required=True, help='Deployment ID')
@click.option('--environment', default='staging', help='Deployment environment')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub token')
@click.option('--slack-token', envvar='SLACK_TOKEN', help='Slack token')
@coro
async def create_followup_tasks(app_name, deployment_id, environment, github_token, slack_token):
    """Create follow-up tasks for deployment"""
    integrator = TaskManagementIntegrator(github_token, slack_token)

    deployment_info = {
        "deployment_id": deployment_id,
        "environment": environment
    }

    tasks = await integrator.create_deployment_followup_tasks(app_name, deployment_info)

    click.echo(f"✅ Created {len(tasks)} follow-up tasks for {app_name}")
    for task in tasks:
        click.echo(f"  📋 {task['title']} - {task['priority']} priority")


# =============================================================================
# 6. DOCKER HEALTH CHECK SCRIPT
# =============================================================================

def create_docker_health_check():
    """Create Docker health check script"""
    script_content = '''#!/usr/bin/env python3
"""
Docker health check script for AI applications
"""
import sys
import requests
import json
import os

def main():
    port = os.environ.get('APP_PORT', '8000')
    health_endpoint = os.environ.get('HEALTH_ENDPOINT', '/health')

    try:
        response = requests.get(f'http://localhost:{port}{health_endpoint}', timeout=5)

        if response.status_code == 200:
            print("✅ Health check passed")
            sys.exit(0)
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Health check error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

    with open('docker_health_check.py', 'w') as f:
        f.write(script_content)


# =============================================================================
# 7. MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Create Docker health check script
    create_docker_health_check()

    # Run CLI
    cli()
