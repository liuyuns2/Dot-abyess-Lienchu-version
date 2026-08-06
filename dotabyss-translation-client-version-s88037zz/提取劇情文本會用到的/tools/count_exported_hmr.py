import json
from pathlib import Path
for sid in ['hmr_10010100012','hmr_10010100011','hmr_10160100012']:
    p = Path(r'E:\離線板\output\bundle_novels_merged') / sid / 'zh_Hant.json'
    if p.exists():
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        print(sid, len(data), 'first=', next(iter(data))[:60], 'last=', next(reversed(data))[:60])
    else:
        print(sid, 'missing')
