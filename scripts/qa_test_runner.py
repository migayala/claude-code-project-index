#!/usr/bin/env python3
"""
QA Test Runner subagent for intelligent test execution.
Handles workspace detection, prerequisite validation, and test execution with retries.
"""

import json
import sys
import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
import time

class QATestRunner:
    def __init__(self, project_root, workspace=None, scope=None):
        self.project_root = Path(project_root)
        self.workspace = workspace
        self.scope = scope
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def log(self, message, level="INFO"):
        """Log messages with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def check_prerequisites(self):
        """Verify all prerequisites before running tests."""
        self.log("🔍 Checking prerequisites...")

        # Check if we're in the right directory
        os.chdir(self.project_root)

        # 1. Check node_modules and run bootstrap
        if not (self.project_root / 'node_modules').exists():
            self.log("📦 node_modules not found, running npm run bootstrap...")
            try:
                subprocess.run(['npm', 'run', 'bootstrap'], check=True, capture_output=True)
                self.log("✅ npm run bootstrap completed")
            except subprocess.CalledProcessError as e:
                self.log(f"❌ npm run bootstrap failed: {e}", "ERROR")
                return False

        # 2. Check .env file
        env_file = self.project_root / '.env'
        if not env_file.exists():
            self.log("❌ .env file not found at repo root", "ERROR")
            return False

        # Check required environment variables
        required_vars = ['BASE_URL']
        with open(env_file) as f:
            env_content = f.read()

        missing_vars = []
        for var in required_vars:
            if f'{var}=' not in env_content:
                missing_vars.append(var)

        if missing_vars:
            self.log(f"❌ Missing required environment variables: {', '.join(missing_vars)}", "ERROR")
            return False

        # Check optional but recommended variables
        optional_vars = ['ANDROID_APP_PATH', 'ELECTRON_APP_PATH']
        for var in optional_vars:
            if f'{var}=' not in env_content:
                self.log(f"⚠️ Optional environment variable {var} not set", "WARN")

        self.log("✅ .env file validated")

        # 3. Check mobile app paths if testing mobile
        if self.workspace == 'wingspanai-mobile':
            android_path = os.environ.get('ANDROID_APP_PATH')
            electron_path = os.environ.get('ELECTRON_APP_PATH')

            if not android_path:
                self.log("⚠️ ANDROID_APP_PATH not set, using default", "WARN")
            if not electron_path:
                self.log("⚠️ ELECTRON_APP_PATH not set, using default", "WARN")

        # 4. Set REPORT_ITERATION if not set
        if not os.environ.get('REPORT_ITERATION'):
            os.environ['REPORT_ITERATION'] = self.session_id
            self.log(f"📊 Set REPORT_ITERATION to {self.session_id}")

        # 5. Check browser installation for Playwright
        if self.workspace in ['wingspanai-web', 'smartscreen'] or self.scope in ['smoke', 'critical', 'regression', 'quick']:
            self.check_playwright_browsers()

        return True

    def check_playwright_browsers(self):
        """Check if Playwright browsers are installed."""
        try:
            result = subprocess.run(['npx', 'playwright', 'install', '--dry-run'],
                                  capture_output=True, text=True)
            if 'needs to be installed' in result.stdout or result.returncode != 0:
                self.log("🌐 Installing Playwright browsers...")
                subprocess.run(['npx', 'playwright', 'install'], check=True)
                self.log("✅ Playwright browsers installed")
            else:
                self.log("✅ Playwright browsers already installed")
        except subprocess.CalledProcessError as e:
            self.log(f"⚠️ Could not verify Playwright browsers: {e}", "WARN")

    def get_test_command(self):
        """Generate the appropriate test command based on actual project structure."""
        # If scope is provided, use root-level scoped commands that include cleaning
        if self.scope:
            scope_commands = {
                'smoke': ['npm', 'run', 'test:smoke'],
                'critical': ['npm', 'run', 'test:critical'],
                'regression': ['npm', 'run', 'test:regression'],
                'quick': ['npm', 'run', 'test:quick'],
                'all': ['npm', 'run', 'test:all']
            }
            if self.scope in scope_commands:
                return scope_commands[self.scope]

        # Workspace-specific commands (include cleaning)
        if self.workspace == 'wingspanai-web':
            return ['npm', 'run', 'test:wingspanai-web']
        elif self.workspace == 'smartscreen':
            return ['npm', 'run', 'test:smartscreen']
        elif self.workspace == 'wingspanai-mobile':
            return ['npm', 'run', 'test:wingspanai-mobile']
        else:
            # Default fallback - smoke tests
            return ['npm', 'run', 'test:smoke']

    def execute_tests(self):
        """Execute tests with streaming output and retry logic."""
        command = self.get_test_command()
        self.log(f"🧪 Executing: {' '.join(command)}")

        try:
            # Execute test command with streaming output
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())
                    output_lines.append(output.strip())

            exit_code = process.poll()

            # Note: Retry logic is built into the npm scripts via Playwright config
            # No need for additional retries here

            return exit_code, output_lines

        except subprocess.CalledProcessError as e:
            self.log(f"❌ Test execution failed: {e}", "ERROR")
            return e.returncode, [str(e)]

    def execute_single_command(self, command):
        """Execute a single command and return results."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            output_lines = result.stdout.split('\n') + result.stderr.split('\n')
            return result.returncode, [line for line in output_lines if line.strip()]
        except Exception as e:
            return 1, [str(e)]

    def generate_report_summary(self, exit_code, output_lines):
        """Generate a summary of test results and report locations."""
        status = "✅ PASSED" if exit_code == 0 else "❌ FAILED"
        self.log(f"🏁 Test execution completed: {status}")

        # Find report directories based on actual project structure
        report_paths = []

        # Check for test-reports directories in each workspace
        for workspace in ['wingspanai-web', 'smartscreen', 'wingspanai-mobile']:
            report_base = self.project_root / workspace / 'test-reports'
            if report_base.exists():
                for report_dir in report_base.iterdir():
                    if report_dir.is_dir():
                        # Look for HTML reports
                        html_report = report_dir / 'html-report' / 'index.html'
                        if html_report.exists():
                            report_paths.append(str(html_report))
                        else:
                            # Include directory even without HTML report
                            report_paths.append(str(report_dir))

        # Also check root test-reports
        root_reports = self.project_root / 'test-reports'
        if root_reports.exists():
            for report_dir in root_reports.iterdir():
                if report_dir.is_dir():
                    report_paths.append(str(report_dir))

        # Generate summary
        summary = {
            "status": "PASSED" if exit_code == 0 else "FAILED",
            "exit_code": exit_code,
            "workspace": self.workspace or "auto-detected",
            "scope": self.scope or "default",
            "session_id": self.session_id,
            "report_paths": report_paths,
            "timestamp": datetime.now().isoformat()
        }

        return summary

    def run(self):
        """Main execution flow."""
        self.log(f"🚀 Starting QA Test Runner (Session: {self.session_id})")
        self.log(f"📁 Project root: {self.project_root}")
        self.log(f"🎯 Workspace: {self.workspace or 'auto-detect'}")
        self.log(f"🏷️ Scope: {self.scope or 'default'}")

        # Check prerequisites
        if not self.check_prerequisites():
            return {"status": "FAILED", "error": "Prerequisites check failed"}

        # Execute tests
        exit_code, output_lines = self.execute_tests()

        # Generate summary
        summary = self.generate_report_summary(exit_code, output_lines)

        # Print final summary
        print("\n" + "="*60)
        print("📊 QA TEST RUNNER SUMMARY")
        print("="*60)
        print(f"Status: {summary['status']}")
        print(f"Workspace: {summary['workspace']}")
        print(f"Scope: {summary['scope']}")
        print(f"Session ID: {summary['session_id']}")

        if summary['report_paths']:
            print("📋 Report locations:")
            for path in summary['report_paths']:
                print(f"  • {path}")
        else:
            print("📋 No test reports found")

        return summary

def main():
    """Entry point for the QA Test Runner."""
    if len(sys.argv) < 2:
        print("Usage: qa_test_runner.py <project_root> [workspace] [scope]")
        sys.exit(1)

    project_root = sys.argv[1]
    workspace = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != 'None' else None
    scope = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'None' else None

    runner = QATestRunner(project_root, workspace, scope)
    summary = runner.run()

    # Exit with test result code
    sys.exit(0 if summary['status'] == 'PASSED' else 1)

if __name__ == "__main__":
    main()