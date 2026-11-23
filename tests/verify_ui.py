import re
import sys

with open('src/web/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Check all getElementById in scripts
ids_used = set(re.findall(r'document\.getElementById\([\'"]([^\'"]+)[\'"]\)', content))
ids_in_html = set(re.findall(r'id=[\'"]([^\'"]+)[\'"]', content))

missing_ids = ids_used - ids_in_html
print(f"Missing IDs count: {len(missing_ids)}")
if missing_ids:
    print(f"Missing IDs: {missing_ids}")

# Check all onclick functions
onclicks = set(re.findall(r'onclick=[\'"]([a-zA-Z0-9_]+)\(', content))
defined_funcs = set(re.findall(r'(?:async\s+)?function\s+([a-zA-Z0-9_]+)\s*\(', content))
missing_funcs = onclicks - defined_funcs
print(f"Missing onclick functions count: {len(missing_funcs)}")
if missing_funcs:
    print(f"Missing onclick functions: {missing_funcs}")

# Check script syntax with node
import subprocess
scripts = '\n'.join(re.findall(r'<script[^>]*>([\s\S]*?)</script>', content, re.IGNORECASE))
with open('temp_script_check.js', 'w', encoding='utf-8') as sf:
    sf.write(scripts)

try:
    res = subprocess.run(['node', '--check', 'temp_script_check.js'], capture_output=True, text=True)
    if res.returncode != 0:
        print("Node syntax check failed:")
        print(res.stderr)
        sys.exit(1)
    else:
        print("Node syntax check PASSED! No JS syntax errors.")
finally:
    import os
    if os.path.exists('temp_script_check.js'):
        os.remove('temp_script_check.js')

print("All UI checks verified.")
