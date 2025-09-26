#!/usr/bin/env python3
"""
Combined UserPromptSubmit hook for both index (-i) and test (-t) flags.
Routes to appropriate subagent based on flag detection.
"""

import json
import sys
import subprocess
import os

def main():
    """Process UserPromptSubmit hook for both -i and -t flags."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)
        prompt = input_data.get('prompt', '')

        # Check for test flag first (-t)
        if '-t' in prompt and (prompt.strip().endswith('-t') or ' -t' in prompt):
            # Route to test hook
            script_dir = os.path.dirname(os.path.abspath(__file__))
            test_hook_path = os.path.join(script_dir, 't_flag_hook.py')

            # Execute test hook with the same input
            result = subprocess.run(
                ['python3', test_hook_path],
                input=json.dumps(input_data),
                text=True,
                capture_output=True
            )

            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, file=sys.stderr, end='')
            sys.exit(result.returncode)

        # Check for index flag (-i)
        elif '-i' in prompt:
            # Route to index hook
            script_dir = os.path.dirname(os.path.abspath(__file__))
            index_hook_path = os.path.join(script_dir, 'i_flag_hook.py')

            # Execute index hook with the same input
            result = subprocess.run(
                ['python3', index_hook_path],
                input=json.dumps(input_data),
                text=True,
                capture_output=True
            )

            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, file=sys.stderr, end='')
            sys.exit(result.returncode)

        # No recognized flags, let prompt proceed normally
        sys.exit(0)

    except Exception as e:
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": f"❌ Combined hook error: {str(e)}"
            }
        }
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()