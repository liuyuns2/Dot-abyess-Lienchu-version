"""
用法：python push_update.py "commit 訊息"
功能：自動補齊 manifest novels → 更新 manifest hash → git add → commit → push
"""
import json, sys, hashlib, time, subprocess
from pathlib import Path

repo = Path(r'D:\dotabyss-translation\GITHUB-dotabyss-translation\Dot-abyess-Lienchu-version')
ver2 = repo / 'dotabyss-translation-new-structure-Ver2'
manifest_f = ver2 / 'manifest' / 'zh_Hant.json'

data = json.loads(manifest_f.read_text(encoding='utf-8'))

# 1. 掃描 novels 資料夾，補齊 manifest 裡缺少的 novel hash
def compute_novel_hash(d: dict) -> str:
    sb = []
    for k in sorted(d.keys()):
        sb.append(k); sb.append('\0')
        sb.append(d.get(k) or ''); sb.append('\0')
    return hashlib.md5(''.join(sb).encode('utf-8')).hexdigest()

novels_dir = ver2 / 'novels'
registered = set(data.get('novels', {}).keys())
added_novels = 0
for novel_dir in sorted(novels_dir.iterdir()):
    if not novel_dir.is_dir():
        continue
    novel_id = novel_dir.name
    if novel_id in registered:
        continue
    zh_f = novel_dir / 'zh_Hant.json'
    if not zh_f.exists():
        continue
    novel_data = json.loads(zh_f.read_text(encoding='utf-8'))
    data['novels'][novel_id] = compute_novel_hash(novel_data)
    added_novels += 1
    print(f'  manifest 新增 novel: {novel_id}')

if added_novels:
    print(f'共補齊 {added_novels} 個 novel')

# 2. 更新 manifest hash（強制 AbyssMod 重新下載）
old_hash = data.get('hash', '')
new_hash = hashlib.md5(str(time.time()).encode()).hexdigest()
data['hash'] = new_hash
manifest_f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'manifest hash 更新: {old_hash[:8]}... -> {new_hash[:8]}...')

# 3. git add all
subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)

# 4. commit
msg = sys.argv[1] if len(sys.argv) > 1 else 'update translations'
subprocess.run(['git', 'commit', '-m', msg], cwd=repo, check=True)

# 5. push
subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo, check=True)
print('完成！')
