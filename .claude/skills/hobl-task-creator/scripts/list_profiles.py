"""列出 Dashboard 中已注册的 profile。

从 /plan/Create 页面提取 JS 中嵌入的 profile 数据。

用法：
    python list_profiles.py [--base-url URL]
"""

import urllib.request
import urllib.error
import re
import json
import sys
import argparse

HTTP_TIMEOUT = 30


def main():
    parser = argparse.ArgumentParser(description='List Dashboard registered profiles')
    parser.add_argument('--base-url', default='http://localhost', help='Dashboard base URL')
    args = parser.parse_args()

    try:
        resp = urllib.request.urlopen(f'{args.base_url}/plan/Create', timeout=HTTP_TIMEOUT)
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"ERROR: Dashboard returned HTTP {e.code} — {e.reason}\n")
        sys.stderr.write("Fallback: ask the user to provide the profile name manually.\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"ERROR: Cannot connect to Dashboard at {args.base_url} — {e}\n")
        sys.stderr.write("Please ensure Dashboard is running and the URL is correct.\n")
        sys.exit(1)

    html = resp.read().decode()

    # Dashboard embeds profile data as: var data = [{...},...];
    match = re.search(r'var\s+data\s*=\s*(\[.*?\])\s*;', html, re.DOTALL)
    if not match:
        sys.stderr.write("ERROR: Could not parse profile data from Dashboard page.\n")
        sys.stderr.write("The Dashboard page structure may have changed.\n")
        sys.stderr.write("Fallback: ask the user to provide the profile name manually.\n")
        sys.exit(1)

    try:
        profiles = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        sys.stderr.write(f"ERROR: Failed to parse profile JSON — {e}\n")
        sys.stderr.write("Fallback: ask the user to provide the profile name manually.\n")
        sys.exit(1)

    # Sanity check: verify parsed data contains expected fields
    if profiles and not all(isinstance(p, dict) and 'id' in p for p in profiles):
        sys.stderr.write("ERROR: Parsed profile data missing expected 'id' field.\n")
        sys.stderr.write("The Dashboard page structure may have changed.\n")
        sys.stderr.write("Fallback: ask the user to provide the profile name manually.\n")
        sys.exit(1)

    if not profiles:
        sys.stderr.write("WARNING: No profiles registered in Dashboard.\n")
        sys.exit(1)

    for p in profiles:
        pid = p.get('id', '?')
        dut = p.get('DUT_name', '?')
        sys.stdout.write(f"{pid}  (DUT: {dut})\n")


if __name__ == '__main__':
    main()
