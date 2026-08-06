import json, re
from pathlib import Path
assets = json.loads(Path(r'E:\離線板\output\assets.json').read_text(encoding='utf-8'))['assets']
text = []
for a in assets:
    key = str(a.get('primary_key') or '')
    low = key.lower()
    if key.endswith('.bundle') and '.txt_' in low and ('_novel_' in low or 'r18-only_novel' in low):
        ids = re.findall(r'(?:mas|hmn|hmr|men|evs)_\d+', key, re.I)
        text.append((key, ids[-1] if ids else ''))

hmr = [(k,sid) for k,sid in text if sid.startswith('hmr_')]
r18_hmr = [(k,sid) for k,sid in hmr if 'r18-only' in k.lower()]
general_hmr = [(k,sid) for k,sid in hmr if 'r18-only' not in k.lower()]
print('text bundles:', len(text))
print('hmr text bundles:', len(hmr))
print('general hmr text bundles:', len(general_hmr))
print('r18 hmr text bundles:', len(r18_hmr))
print('\nfirst general hmr:')
for k,sid in general_hmr[:10]: print(sid, k)
print('\nfirst r18 hmr:')
for k,sid in r18_hmr[:20]: print(sid, k)
print('\nids with both general and r18 exact:')
g = {sid for _,sid in general_hmr}; r = {sid for _,sid in r18_hmr}
for sid in sorted(g & r)[:20]: print(sid)
print('overlap count', len(g & r))
print('r18 only sample ids', ', '.join(sorted(r - g)[:20]))
