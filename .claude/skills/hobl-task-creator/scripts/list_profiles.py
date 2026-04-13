"""列出 Dashboard 中已注册的 profile。

从 /plan/Create 页面提取 JS 中嵌入的 profile 数据。

用法：
    python list_profiles.py [--base-url URL]
"""

import urllib.request
import re
import json
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description='List Dashboard registered profiles')
    parser.add_argument('--base-url', default='http://localhost', help='Dashboard base URL')
    args = parser.parse_args()

    resp = urllib.request.urlopen(f'{args.base_url}/plan/Create')
    html = resp.read().decode()

    # Dashboard embeds profile data as: var data = [{...},...];
    match = re.search(r'var\s+data\s*=\s*(\[.*?\])\s*;', html, re.DOTALL)
    if not match:
        sys.stderr.write("Could not find profile data in Dashboard page.\n")
        sys.exit(1)

    profiles = json.loads(match.group(1))
    for p in profiles:
        pid = p.get('id', '?')
        dut = p.get('DUT_name', '?')
        sys.stdout.write(f"{pid}  (DUT: {dut})\n")


if __name__ == '__main__':
    main()
