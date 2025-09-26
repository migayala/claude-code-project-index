---
name: qa-test-runner
description: A specialized Claude Code subagent for intelligent test execution in the Monarch Tractor QA automation repository. Automatically detects workspace context and executes appropriate test commands with prerequisites validation, retry logic, and comprehensive reporting. Add the -t flag to any prompt to activate.
tools: Bash, Read, Grep, Glob, Write
---

# QA Test Runner Subagent

A specialized Claude Code subagent for intelligent test execution in the Monarch Tractor QA automation repository.

## Overview

The QA Test Runner automatically detects your workspace context and executes the appropriate test commands with proper prerequisites validation, retry logic, and comprehensive reporting.

## Usage

### Basic Usage

Add the `-t` flag to any prompt to activate the QA Test Runner:

```bash
# Run default tests based on workspace detection
Check if login works -t

# Run tests with specific scope
Verify user registration flow -tsmoke

# Run regression tests
Test all user management features -tregression
```

### Flag Patterns

- `-t` - Run default tests (auto-detects workspace)
- `-tsmoke` - Run smoke tests
- `-tregression` - Run regression tests
- `-t<scope>` - Run tests matching the specified scope

## Workspace Detection

The agent intelligently routes tests based on:

1. **Git Status Analysis**: Examines changed files to determine target workspace
2. **Current Directory**: Falls back to checking current working directory
3. **Manual Scope**: Uses explicit scope flags when provided

### Supported Workspaces

| Workspace | Test Command | Notes |
|-----------|--------------|-------|
| `wingspanai-web` | `npm run test:wingspanai-web` | Includes cleaning + Playwright tests |
| `smartscreen` | `npm run test:smartscreen` | Includes cleaning + Playwright tests |
| `wingspanai-mobile` | `npm run test:wingspanai-mobile` | Includes cleaning + Appium mobile tests |
| *fallback* | `npm run test:smoke` | Default smoke tests when no workspace detected |

### Supported Scopes

| Scope | Test Command | Tag Filter |
|-------|--------------|------------|
| `smoke` | `npm run test:smoke` | `@smoke` tagged tests |
| `critical` | `npm run test:critical` | `@critical` tagged tests |
| `regression` | `npm run test:regression` | `@regression` tagged tests |
| `quick` | `npm run test:quick` | `@smoke|@critical` tagged tests |
| `all` | `npm run test:all` | All workspaces sequentially |

## Prerequisites Validation

Before executing tests, the agent automatically checks:

### ✅ Dependencies
- Verifies `node_modules` exists
- Runs `npm run bootstrap` if needed
- Installs Playwright browsers for web tests

### ✅ Environment Configuration
- Validates `.env` file exists at repo root
- Confirms required variables: `BASE_URL`, `LOGIN_EMAIL`, `PASSWORD`
- Sets `REPORT_ITERATION` if not present

### ✅ Mobile App Paths (for mobile tests)
- Checks `ANDROID_APP_PATH` and `IOS_APP_PATH` environment variables
- Falls back to default `apps/` folder if paths not set

## Features

### 🔄 Retry Logic
- **Playwright**: Uses `--retries=1` for flaky test resilience
- **WDIO**: Re-invokes failed specs once before declaring failure
- **Smart Retries**: Only retries on initial failure, not on repeated failures

### 📊 Real-time Output
- Streams test execution output in real-time
- Preserves all stdout/stderr for debugging
- Provides clear status indicators

### 📋 Report Generation
- Automatically locates test report files
- Provides direct links to HTML reports
- Organizes reports by session ID and timestamp

### 🛡️ Safety Features
- **Fail Fast**: Stops execution on critical errors with actionable messages
- **Error Collection**: Captures and displays stderr for debugging
- **Non-Destructive**: Won't break existing project configurations
- **Session Isolation**: Uses unique session IDs to prevent report conflicts

## Report Locations

### Web Tests (wingspanai-web)
```
wingspanai-web/test-reports/<date>-wingspanai-web-<iteration>/html-report/index.html
```

### Smartscreen Tests
```
smartscreen/test-reports/<session-id>/
```

### Mobile Tests
```
wingspanai-mobile/test-reports/<session-id>/
```

## Example Workflows

### 1. Quick Smoke Test
```bash
# User types:
Run a quick smoke test -tsmoke

# Agent detects workspace and executes:
npm run test:smoke
```

### 2. Web-Specific Testing
```bash
# User types (in wingspanai-web directory):
Test the login flow -t

# Agent executes:
npm --workspace=wingspanai-web run test --retries=1
```

### 3. Scoped Testing
```bash
# User types:
Check user registration -tregression

# Agent executes with grep filter:
npm --workspace=wingspanai-web run test -- --grep "regression" --retries=1
```

## Error Handling

### Common Error Scenarios

| Error | Solution |
|-------|----------|
| `node_modules not found` | Automatically runs `npm run bootstrap` |
| `Missing .env file` | Clear error message with required variables |
| `Browser not installed` | Automatically runs `npx playwright install` |
| `Mobile app path missing` | Falls back to default apps folder |
| `Test failures` | Automatic retry with detailed error output |

### Exit Codes
- `0` - All tests passed
- `1` - Test failures or execution errors
- `2` - Prerequisites validation failed

## Integration with Claude Code

The QA Test Runner integrates seamlessly with Claude Code's subagent system:

1. **Hook Detection**: The UserPromptSubmit hook detects `-t` flags
2. **Subagent Routing**: Automatically routes to the QA Test Runner subagent
3. **Context Preservation**: Maintains original user request context
4. **Result Integration**: Returns to main agent with execution summary

## Configuration

### Environment Variables

Required in `.env` file:
```bash
BASE_URL=https://your-test-environment.com
LOGIN_EMAIL=test@example.com
PASSWORD=your-test-password
```

Optional for mobile testing:
```bash
ANDROID_APP_PATH=/path/to/android.apk
IOS_APP_PATH=/path/to/ios.app
REPORT_ITERATION=custom-session-id
```

## Troubleshooting

### Agent Not Triggering
- Ensure flag format: space + `-t` + optional scope
- Check that prompt ends with the flag: `request -tsmoke`
- Verify combined_hook.py is executable

### Test Execution Issues
- Check `.env` file has all required variables
- Verify `node_modules` exists or allow auto-install
- For mobile tests, confirm app paths or use default apps folder

### Report Generation
- Reports are generated automatically if tests produce output
- Check session ID in logs to locate specific report folders
- HTML reports are only generated for successful Playwright runs

## Files Created

The QA Test Runner consists of these files in your forked project-index:

- `scripts/t_flag_hook.py` - Flag detection and routing
- `scripts/qa_test_runner.py` - Main test execution logic
- `scripts/combined_hook.py` - Unified hook for both -i and -t flags
- `~/.claude/agents/qa-test-runner.md` - This documentation

## Contributing

This agent is part of your forked claude-code-project-index repository. To share improvements:

1. Commit changes to your fork
2. Push to GitHub: `git@github.com:migayala/claude-code-project-index.git`
3. Other computers can clone your fork for the same functionality
4. Consider contributing back to the original project

## Version History

- **v1.0** - Initial implementation with workspace detection, retry logic, and comprehensive reporting