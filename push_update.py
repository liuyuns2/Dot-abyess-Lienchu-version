"""
用法：python push_update.py "commit 訊息"
功能：自動更新 manifest hash → git add → commit → push
"""
import json, sys, hashlib, time, subprocess
from pathlib import Path

repo = Path(r'D:\dotabyss-translation\GITHUB-dotabyss-translation\Dot-abyess-Lienchu-version')
ver2 = repo / 'dotabyss-translation-new-structure-Ver2'
manifest_f = ver2 / 'manifest' / 'zh_Hant.json'

# 1. 更新 manifest hash
data = json.loads(manifest_f.read_text(encoding='utf-8'))
old_hash = data.get('hash', '')
new_hash = hashlib.md5(str(time.time()).encode()).hexdigest()
data['hash'] = new_hash
manifest_f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'manifest hash 更新: {old_hash[:8]}... → {new_hash[:8]}...')

# 2. git add all
subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)

# 3. commit
msg = sys.argv[1] if len(sys.argv) > 1 else 'update translations'
subprocess.run(['git', 'commit', '-m', msg], cwd=repo, check=True)

# 4. push
subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo, check=True)
print('完成！')
