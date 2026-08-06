import json
from pathlib import Path
p = Path(r'E:\離線板\output\windows_1916_catalog_1\assets.json')
data = json.loads(p.read_text(encoding='utf-8'))
assets = data.get('assets', [])

def count(fn):
    return sum(1 for a in assets if fn(str(a.get('primary_key') or '')))

lines = []
lines.append('# windows_1916_catalog_1 summary')
lines.append('')
info = data.get('catalog_info', {})
for k in ['version', 'locator_id', 'build_result_hash', 'total_resource_keys', 'total_locations']:
    lines.append(f'- {k}: {info.get(k)}')
lines.append('')
lines.append('## Counts')
checks = [
    ('all_assets', lambda k: True),
    ('bundle_files', lambda k: k.endswith('.bundle')),
    ('novel_related', lambda k: 'novel' in k.lower()),
    ('text_novel_bundles', lambda k: k.endswith('.bundle') and '.txt_' in k.lower() and ('_novel_' in k.lower() or 'r18-only_novel' in k.lower())),
    ('r18_related', lambda k: 'r18' in k.lower()),
    ('hmr_related', lambda k: 'hmr_' in k.lower()),
    ('voice_novel', lambda k: 'novel_voice' in k.lower()),
]
for name, fn in checks:
    lines.append(f'- {name}: {count(fn)}')
lines.append('')
lines.append('## Sample text novel bundles')
printed = 0
for a in assets:
    k = str(a.get('primary_key') or '')
    low = k.lower()
    if k.endswith('.bundle') and '.txt_' in low and ('_novel_' in low or 'r18-only_novel' in low):
        lines.append(f'- {k}')
        printed += 1
        if printed >= 20:
            break
out = Path(r'E:\離線板\output\windows_1916_catalog_1\summary.md')
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines[:30]))
print(f'Wrote: {out}')
