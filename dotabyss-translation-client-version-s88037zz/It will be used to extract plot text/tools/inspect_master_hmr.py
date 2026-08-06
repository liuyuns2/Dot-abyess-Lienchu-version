import json
from pathlib import Path
md = json.loads(Path(r'E:\離線板\output\MasterData.json').read_text(encoding='utf-8'))
for table in ['m_novel_mains','m_novel_homes','m_novel_characters','m_novel_character_skins','m_novel_events','m_novel_others']:
    rows = [r for r in md.get(table, []) if isinstance(r, dict) and str(r.get('script_id','')).startswith('hmr_1001010001')]
    if rows:
        print('\nTABLE', table, 'rows', len(rows))
        for r in rows:
            keys = ['id','novel_id','episode_id','script_id','title','name','description','sort_order','release_condition_id']
            print({k:r.get(k) for k in keys if k in r})
