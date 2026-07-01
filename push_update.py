"""
用法：python push_update.py "commit 訊息"
功能：自動同步所有檔案 hash 到 manifest → 更新 manifest hash → git add → commit → push
"""
import json, sys, hashlib, time, subprocess
from pathlib import Path

repo = Path(r'D:\dotabyss-translation\GITHUB-dotabyss-translation\Dot-abyess-Lienchu-version')
ver2 = repo / 'dotabyss-translation-new-structure-Ver2'
manifest_f = ver2 / 'manifest' / 'zh_Hant.json'

data = json.loads(manifest_f.read_text(encoding='utf-8'))

def compute_flat_hash(d: dict) -> str:
    """ui_texts / names 用的 hash（flat dict）"""
    sb = []
    for k in sorted(d.keys()):
        sb.append(k); sb.append('\0')
        sb.append(d.get(k) or ''); sb.append('\0')
    return hashlib.md5(''.join(sb).encode('utf-8')).hexdigest()

def compute_novel_hash(d: dict) -> str:
    return compute_flat_hash(d)

# 1. 同步 novels：新增或修改都更新 hash
novels_dir = ver2 / 'novels'
novel_changes = 0
for novel_dir in sorted(novels_dir.iterdir()):
    if not novel_dir.is_dir():
        continue
    novel_id = novel_dir.name
    zh_f = novel_dir / 'zh_Hant.json'
    if not zh_f.exists():
        continue
    novel_data = json.loads(zh_f.read_text(encoding='utf-8'))
    new_h = compute_novel_hash(novel_data)
    old_h = data['novels'].get(novel_id)
    if old_h != new_h:
        data['novels'][novel_id] = new_h
        novel_changes += 1
        label = '新增' if not old_h else '更新'
        print(f'  novels {label}: {novel_id}')

if novel_changes:
    print(f'novels 共 {novel_changes} 個變更')

# 2. 同步 ui_texts hash
for name in ['ui_texts', 'names']:
    f = ver2 / name / 'zh_Hant.json'
    if not f.exists():
        continue
    d = json.loads(f.read_text(encoding='utf-8'))
    new_h = compute_flat_hash(d)
    old_h = data.get(name)
    if old_h != new_h:
        data[name] = new_h
        print(f'  {name} hash 更新: {(old_h or "")[:8]}... -> {new_h[:8]}...')

# 3. 更新頂層 manifest hash（強制 AbyssMod 重新下載 manifest）
old_hash = data.get('hash', '')
new_hash = hashlib.md5(str(time.time()).encode()).hexdigest()
data['hash'] = new_hash
manifest_f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'manifest hash: {old_hash[:8]}... -> {new_hash[:8]}...')

# 3. git add all
subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)

# 4. commit
msg = sys.argv[1] if len(sys.argv) > 1 else 'update translations'
subprocess.run(['git', 'commit', '-m', msg], cwd=repo, check=True)

# 5. push
subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo, check=True)
print('完成！')
