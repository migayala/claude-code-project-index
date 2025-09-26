#!/usr/bin/env python3
"""
UserPromptSubmit hook for QA Test Runner subagent.
Detects -t[scope] flags for intelligent test execution.
"""

import json
import sys
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime

def find_project_root():
    """Find project root by looking for .git or common project markers."""
    current = Path.cwd()

    # First check current directory for project markers
    if (current / '.git').exists():
        return current

    # Check for other project markers
    project_markers = ['package.json', 'pyproject.toml', 'setup.py', 'Cargo.toml', 'go.mod']
    for marker in project_markers:
        if (current / marker).exists():
            return current

    # Search up the tree for .git
    for parent in current.parents:
        if (parent / '.git').exists():
            return parent

    # Default to current directory
    return current

def parse_test_flag(prompt):
    """
    Parse test flags from prompt: -t, -tsmoke, -tregression, etc.
    Returns: (scope, cleaned_prompt) or (None, prompt)
    """
    # Match -t followed by optional scope
    pattern = r'\s+-t([a-zA-Z0-9_-]*)\s*$'
    match = re.search(pattern, prompt)

    if match:
        scope = match.group(1) if match.group(1) else None
        cleaned_prompt = prompt[:match.start()].strip()
        return scope, cleaned_prompt

    return None, prompt

def detect_workspace_changes():
    """
    Analyze git status and current directory to determine which workspace to test.
    Returns: workspace name or None
    """
    try:
        project_root = find_project_root()
        os.chdir(project_root)

        # Check git status for changed files
        result = subprocess.run(['git', 'status', '--porcelain'],
                              capture_output=True, text=True, check=True)

        changed_files = result.stdout.strip().split('\n') if result.stdout.strip() else []

        # Analyze file paths to determine workspace
        wingspanai_web_files = any('wingspanai-web/' in file for file in changed_files)
        smartscreen_files = any('smartscreen/' in file for file in changed_files)
        mobile_files = any('wingspanai-mobile/' in file for file in changed_files)

        if wingspanai_web_files:
            return 'wingspanai-web'
        elif smartscreen_files:
            return 'smartscreen'
        elif mobile_files:
            return 'wingspanai-mobile'

        # Check current working directory as fallback
        cwd = Path.cwd()
        if 'wingspanai-web' in str(cwd):
            return 'wingspanai-web'
        elif 'smartscreen' in str(cwd):
            return 'smartscreen'
        elif 'wingspanai-mobile' in str(cwd):
            return 'wingspanai-mobile'

        return None

    except subprocess.CalledProcessError:
        return None

def get_test_command(workspace, scope):
    """
    Generate the appropriate test command based on workspace and scope.
    """
    if workspace == 'wingspanai-web':
        base_cmd = 'npm --workspace=wingspanai-web run test'
        if scope:
            return f'{base_cmd} -- --grep "{scope}"'
        return base_cmd
    elif workspace == 'smartscreen':
        return 'npm --workspace=smartscreen run test'
    elif workspace == 'wingspanai-mobile':
        return 'npx wdio run appium.config.ts'
    else:
        # Default fallback
        if scope:
            return f'npm run test:{scope}'
        return 'npm run test:smoke'

def main():
    """Process UserPromptSubmit hook for -t flag detection."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)
        prompt = input_data.get('prompt', '')

        # Parse test flag
        scope, cleaned_prompt = parse_test_flag(prompt)

        if scope is None:
            # No test flag, let prompt proceed normally
            sys.exit(0)

        # Detect workspace
        workspace = detect_workspace_changes()

        # Generate test command
        test_command = get_test_command(workspace, scope)

        # Prepare instructions for QA Test Runner subagent
        workspace_info = f" in {workspace}" if workspace else ""
        scope_info = f" with scope '{scope}'" if scope else ""

        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"""
## 🧪 QA Test Runner Activated

**Test Configuration:**
- Workspace: {workspace or 'auto-detect'}
- Scope: {scope or 'default'}
- Command: `{test_command}`

**IMPORTANT**: Use the QA Test Runner subagent to execute tests. Launch it with this prompt:

"Execute QA tests{workspace_info}{scope_info}. Original request: {cleaned_prompt}"

The subagent will:
1. Verify prerequisites (npm install, .env, mobile app paths)
2. Execute: `{test_command}`
3. Handle retries for flaky tests
4. Stream output and summarize results
5. Provide report links

**For the QA Test Runner subagent:**
- Project root: {find_project_root()}
- Target workspace: {workspace or 'auto-detect from git status'}
- Test scope: {scope or 'default'}
- Retry failed tests once before declaring failure
- Set REPORT_ITERATION if not present
- Check browser installation for Playwright tests

DO NOT execute tests directly - use the specialized QA Test Runner subagent.
""",
                "replacePrompt": f"Execute QA tests{workspace_info}{scope_info}. Original request: {cleaned_prompt}"
            }
        }

        print(json.dumps(output))

    except Exception as e:
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"❌ QA Test Runner hook error: {str(e)}"
            }
        }
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()