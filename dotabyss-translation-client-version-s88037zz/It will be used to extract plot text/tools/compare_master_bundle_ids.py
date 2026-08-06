import json, re
from pathlib import Path
md = json.loads(Path(r'E:\離線板\output\MasterData.json').read_text(encoding='utf-8'))
master_ids = set()
for table in ['m_novel_prologues','m_novel_others','m_novel_mains','m_novel_homes','m_novel_events','m_novel_characters','m_novel_character_skins']:
    for row in md.get(table, []) or []:
        if isinstance(row, dict) and row.get('script_id'):
            master_ids.add(str(row['script_id']))
assets = json.loads(Path(r'E:\離線板\output\assets.json').read_text(encoding='utf-8'))['assets']
bundle_ids = set()
for a in assets:
    k = str(a.get('primary_key') or '')
    low = k.lower()
    if k.endswith('.bundle') and '.txt_' in low and ('_novel_' in low or 'r18-only_novel' in low):
        ids = re.findall(r'(?:mas|hmn|hmr|men|evs)_\d+', k, re.I)
        if ids: bundle_ids.add(ids[-1])
print('master ids:', len(master_ids))
print('bundle ids:', len(bundle_ids))
print('bundle-only ids:', len(bundle_ids - master_ids))
print('hmr master ids:', sum(1 for x in master_ids if x.startswith('hmr_')))
print('hmr bundle ids:', sum(1 for x in bundle_ids if x.startswith('hmr_')))
print('hmr bundle-only ids:', sum(1 for x in (bundle_ids-master_ids) if x.startswith('hmr_')))
print('sample hmr bundle-only:', ', '.join(sorted(x for x in (bundle_ids-master_ids) if x.startswith('hmr_'))[:30]))
