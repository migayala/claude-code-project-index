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

        # 1. Check node_modules and npm install
        if not (self.project_root / 'node_modules').exists():
            self.log("📦 node_modules not found, running npm install...")
            try:
                subprocess.run(['npm', 'run', 'bootstrap'], check=True, capture_output=True)
                self.log("✅ npm install completed")
            except subprocess.CalledProcessError as e:
                self.log(f"❌ npm install failed: {e}", "ERROR")
                return False

        # 2. Check .env file
        env_file = self.project_root / '.env'
        if not env_file.exists():
            self.log("❌ .env file not found at repo root", "ERROR")
            return False

        # Check required environment variables
        required_vars = ['BASE_URL', 'LOGIN_EMAIL', 'PASSWORD']
        with open(env_file) as f:
            env_content = f.read()

        missing_vars = []
        for var in required_vars:
            if f'{var}=' not in env_content:
                missing_vars.append(var)

        if missing_vars:
            self.log(f"❌ Missing required environment variables: {', '.join(missing_vars)}", "ERROR")
            return False

        self.log("✅ .env file validated")

        # 3. Check mobile app paths if testing mobile
        if self.workspace == 'wingspanai-mobile':
            android_path = os.environ.get('ANDROID_APP_PATH')
            ios_path = os.environ.get('IOS_APP_PATH')
            default_apps = self.project_root / 'apps'

            if not android_path and not ios_path and not default_apps.exists():
                self.log("⚠️ No mobile app paths found, using default apps folder", "WARN")

        # 4. Set REPORT_ITERATION if not set
        if not os.environ.get('REPORT_ITERATION'):
            os.environ['REPORT_ITERATION'] = self.session_id
            self.log(f"📊 Set REPORT_ITERATION to {self.session_id}")

        # 5. Check browser installation for Playwright
        if self.workspace == 'wingspanai-web':
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
        """Generate the appropriate test command."""
        if self.workspace == 'wingspanai-web':
            base_cmd = ['npm', '--workspace=wingspanai-web', 'run', 'test']
            if self.scope:
                base_cmd.extend(['--', '--grep', self.scope])
            # Add retry flag for resilience
            base_cmd.extend(['--', '--retries=1'])
            return base_cmd
        elif self.workspace == 'smartscreen':
            return ['npm', '--workspace=smartscreen', 'run', 'test']
        elif self.workspace == 'wingspanai-mobile':
            return ['npx', 'wdio', 'run', 'appium.config.ts']
        else:
            # Default fallback
            if self.scope:
                return ['npm', 'run', f'test:{self.scope}']
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

            # If tests failed and this is a Playwright test, try retry
            if exit_code != 0 and self.workspace == 'wingspanai-web' and '--retries=1' not in ' '.join(command):
                self.log("🔄 Tests failed, attempting retry with --retries=1...")
                retry_command = command + ['--', '--retries=1']
                return self.execute_single_command(retry_command)

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

        # Find report directories
        report_paths = []
        if self.workspace == 'wingspanai-web':
            report_base = self.project_root / 'wingspanai-web' / 'test-reports'
            if report_base.exists():
                for report_dir in report_base.iterdir():
                    if report_dir.is_dir() and self.session_id in report_dir.name:
                        html_report = report_dir / 'html-report' / 'index.html'
                        if html_report.exists():
                            report_paths.append(str(html_report))

        elif self.workspace == 'smartscreen':
            report_base = self.project_root / 'smartscreen' / 'test-reports'
            if report_base.exists():
                for report_dir in report_base.iterdir():
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
            print("📋 No HTML reports found")

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