from pathlib import Path
from PIL import Image
root = Path(r'E:\離線板\output\windows_1916_catalog_1\windows_1916_catalog_1_output\extracted')
folders = [p for p in root.iterdir() if p.is_dir() and 'charastand109601000g' in p.name.lower()]
for folder in folders:
    print('FOLDER', folder.name)
    for png in sorted(folder.rglob('*.png')):
        with Image.open(png) as im:
            print(' ', png.relative_to(folder), im.size, png.stat().st_size)
