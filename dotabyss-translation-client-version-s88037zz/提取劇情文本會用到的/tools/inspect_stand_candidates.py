import csv
from collections import Counter
from pathlib import Path
p=Path(r'E:\離線板\output\windows_1916_catalog_1\windows_1916_catalog_1_output\categories\image_related.csv')
rows=list(csv.DictReader(p.open(encoding='utf-8-sig')))
patterns={
 'stand': lambda k:'stand' in k.lower(),
 'enemy_stand': lambda k:'enemy' in k.lower() and 'stand' in k.lower(),
 'chara_stand': lambda k:'chara' in k.lower() and 'stand' in k.lower(),
 'character_stand': lambda k:'character' in k.lower() and 'stand' in k.lower(),
 'charaicon': lambda k:'charaicon' in k.lower() or 'chara_icon' in k.lower(),
 'characutin': lambda k:'characutin' in k.lower() or 'chara_cutin' in k.lower(),
 'r18_chara': lambda k:'r18' in k.lower() and 'chara' in k.lower(),
 'novel_chara': lambda k:'novel' in k.lower() and 'chara' in k.lower(),
 'story_s': lambda k:'story_s' in k.lower(),
}
for name,fn in patterns.items():
    selected=[r for r in rows if fn((r.get('primary_key') or '')+' '+(r.get('internal_id') or ''))]
    print(name, len(selected))
    for r in selected[:20]: print(' ', r['primary_key'] or r['internal_id'])
    print()
