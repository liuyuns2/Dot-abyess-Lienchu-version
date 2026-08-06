import json, re, csv
from collections import Counter
from pathlib import Path
import UnityPy
sid = 'hmr_10010100012'
assets = json.loads(Path(r'E:\離線板\output\assets.json').read_text(encoding='utf-8'))['assets']
key = None
for a in assets:
    k = str(a.get('primary_key') or '')
    if sid in k and k.endswith('.bundle') and '.txt_' in k.lower():
        key = k; break
print('key:', key)
bundle = Path(r'E:\離線板\output\downloads') / key
print('bundle exists:', bundle.exists(), bundle)
env = UnityPy.load(str(bundle))
for obj in env.objects:
    if getattr(obj.type, 'name', '') != 'TextAsset':
        continue
    data = obj.read()
    script = getattr(data, 'm_Script', '')
    if isinstance(script, (bytes, bytearray)):
        script = script.decode('utf-8-sig', 'ignore')
    else:
        script = str(script).lstrip('\ufeff')
    lines = [ln for ln in script.splitlines() if ln.strip() and not ln.strip().startswith('//')]
    commands = Counter()
    nonempty_arg_commands = Counter()
    samples = {}
    for ln in lines:
        if ln.strip().startswith(':'):
            commands[':label'] += 1
            continue
        try:
            parts = next(csv.reader([ln]))
        except Exception:
            parts = ln.split(',')
        cmd = parts[0].strip().lower() if parts else ''
        commands[cmd] += 1
        if any(p.strip() for p in parts[1:]):
            nonempty_arg_commands[cmd] += 1
        samples.setdefault(cmd, ln[:160])
    print('line count:', len(lines))
    print('command counts:')
    for cmd, count in commands.most_common(60):
        print(f'  {cmd}: {count} | sample: {samples.get(cmd)}')
