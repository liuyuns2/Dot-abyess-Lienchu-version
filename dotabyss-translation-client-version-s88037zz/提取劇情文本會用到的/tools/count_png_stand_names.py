from pathlib import Path
root=Path(r'E:\離線板\output\windows_1916_catalog_1\windows_1916_catalog_1_output\extracted')
patterns=['Enemy_Stand','CharaStand','CharaCutin','Story_S_hmr']
for pat in patterns:
    hits=[]
    for p in root.rglob('*.png'):
        if pat.lower() in p.name.lower():
            hits.append(p)
    print(pat, len(hits))
    for p in hits[:10]: print(' ', p.name)
