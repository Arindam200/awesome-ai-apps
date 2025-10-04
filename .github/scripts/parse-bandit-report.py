#!/usr/bin/env python3
"""Parse Bandit security scan report and display results."""

import json
import sys
def main():
    """Parse bandit JSON report and display security issues."""
    try:
        with open('bandit-report.json', 'r') as f:
            report = json.load(f)

        high_severity = len([issue for issue in report.get('results', [])
                           if issue.get('issue_severity') == 'HIGH'])
        medium_severity = len([issue for issue in report.get('results', [])
                             if issue.get('issue_severity') == 'MEDIUM'])

        print(f'Security scan: {high_severity} high, {medium_severity} medium severity issues')

        if high_severity > 0:
            print(' High severity security issues found')
            for issue in report.get('results', []):
                if issue.get('issue_severity') == 'HIGH':
                    test_name = issue.get('test_name', 'Unknown')
                    filename = issue.get('filename', 'Unknown')
                    line_number = issue.get('line_number', 'Unknown')
                    print(f'  - {test_name}: {filename}:{line_number}')
        else:
            print(' No high severity security issues')

    except FileNotFoundError:
        print('Could not find bandit-report.json')
    except json.JSONDecodeError:
        print('Could not parse bandit report - invalid JSON')
    except Exception as e:
        print(f'Could not parse security report: {e}')

if __name__ == '__main__':
    main()