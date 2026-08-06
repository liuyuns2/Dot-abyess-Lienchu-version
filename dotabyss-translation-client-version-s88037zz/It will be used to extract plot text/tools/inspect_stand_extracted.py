import csv, os
from pathlib import Path
base=Path(r'E:\離線板\output\windows_1916_catalog_1\windows_1916_catalog_1_output')
rows=list(csv.DictReader((base/'categories'/'image_related.csv').open(encoding='utf-8-sig')))
for needle in ['pregacha_charastand_s_100201000g', 'enemy_stand_2014001', 'characutin100101000g', 'story_s_hmr_1001010001']:
    row=next((r for r in rows if needle in ((r.get('primary_key') or '')+(r.get('internal_id') or '')).lower()), None)
    print('\nneedle', needle)
    if row:
        print(row['primary_key'])
        folder=base/'extracted'/row['primary_key']
        print('folder exists', folder.exists(), folder)
        if folder.exists():
            for p in list(folder.rglob('*.png'))[:10]: print(' ', p.relative_to(folder), p.stat().st_size)
