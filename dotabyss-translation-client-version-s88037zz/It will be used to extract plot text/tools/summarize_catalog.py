import json, re
from pathlib import Path
p = Path(r'E:\離線板\files\catalog_from_download.json')
data = json.loads(p.read_text(encoding='utf-8'))
assets = data.get('assets', [])
patterns = {
    'all_assets': lambda k: True,
    'novel_related': lambda k: 'novel' in k.lower(),
    'text_novel_bundles': lambda k: k.endswith('.bundle') and '.txt_' in k.lower() and ('_novel_' in k.lower() or 'r18-only_novel' in k.lower()),
    'voice_novel': lambda k: 'novel_voice' in k.lower(),
    'general_novel': lambda k: 'general-novel' in k.lower(),
}
print('catalog_info:', data.get('catalog_info', {}))
for name, fn in patterns.items():
    rows = [a for a in assets if fn(str(a.get('primary_key') or ''))]
    print(f'{name}: {len(rows)}')
    for a in rows[:8]:
        print('  -', a.get('primary_key'))
    if rows:
        print()
