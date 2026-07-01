"""
用法：python push_update.py "commit 訊息"
功能：自動掃描所有有變動的檔案 → 更新 manifest hash → git add → commit → push
"""
import json, sys, hashlib, time, subprocess
from pathlib import Path

repo = Path(r'D:\dotabyss-translation\GITHUB-dotabyss-translation\Dot-abyess-Lienchu-version')
ver2 = repo / 'dotabyss-translation-new-structure-Ver2'
manifest_f = ver2 / 'manifest' / 'zh_Hant.json'

data = json.loads(manifest_f.read_text(encoding='utf-8'))

def flat_hash(d: dict) -> str:
    sb = []
    for k in sorted(d.keys()):
        sb.append(k); sb.append('\0')
        sb.append(d.get(k) or ''); sb.append('\0')
    return hashlib.md5(''.join(sb).encode('utf-8')).hexdigest()

changes = 0

SKIP = {'manifest', 'static'}  # static 是 m_* 的合併包，不在 manifest 裡單獨 hash

for folder in sorted(ver2.iterdir()):
    if not folder.is_dir() or folder.name in SKIP:
        continue

    # novels / add-on：子資料夾各自有 zh_Hant.json
    if folder.name in ('novels', 'add-on'):
        manifest_key = 'novels' if folder.name == 'novels' else 'add_on'
        if manifest_key not in data:
            data[manifest_key] = {}
        for sub in sorted(folder.iterdir()):
            if not sub.is_dir(): continue
            zh_f = sub / 'zh_Hant.json'
            if not zh_f.exists(): continue
            d = json.loads(zh_f.read_text(encoding='utf-8'))
            new_h = flat_hash(d)
            old_h = data[manifest_key].get(sub.name)
            if old_h != new_h:
                data[manifest_key][sub.name] = new_h
                label = '新增' if not old_h else '更新'
                print(f'  {folder.name}/{sub.name} {label}')
                changes += 1

    # 其他資料夾：直接含 zh_Hant.json
    else:
        zh_f = folder / 'zh_Hant.json'
        if not zh_f.exists(): continue
        d = json.loads(zh_f.read_text(encoding='utf-8'))
        new_h = flat_hash(d)
        # manifest key：資料夾名稱（靜態 bundle 以外都同名）
        manifest_key = folder.name
        old_h = data.get(manifest_key)
        if old_h != new_h:
            data[manifest_key] = new_h
            print(f'  {folder.name} hash 更新: {(old_h or "")[:8]}... -> {new_h[:8]}...')
            changes += 1

# 頂層 manifest hash（每次都更新，確保遊戲重下載 manifest）
old_hash = data.get('hash', '')
new_hash = hashlib.md5(str(time.time()).encode()).hexdigest()
data['hash'] = new_hash
manifest_f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'manifest hash: {old_hash[:8]}... -> {new_hash[:8]}... ({changes} 個檔案有變動)')

subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)
msg = sys.argv[1] if len(sys.argv) > 1 else 'update translations'
subprocess.run(['git', 'commit', '-m', msg], cwd=repo, check=True)
subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo, check=True)
print('完成！')
