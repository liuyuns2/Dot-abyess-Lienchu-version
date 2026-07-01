"""
用法：python push_update.py "commit 訊息"
功能：
  1. 同步 static/zh_Hant.json（從 m_* 彙整）
  2. 同步 dotabyss-translation-client-version（開發區 → 用戶區）
  3. 更新 manifest hash
  4. git add → commit → push
"""
import json, sys, hashlib, time, subprocess, shutil
from pathlib import Path


def sync_static(ver2: Path):
    """將所有 m_*/zh_Hant.json 的最新翻譯同步到 static/zh_Hant.json"""
    static_path = ver2 / 'static' / 'zh_Hant.json'
    if not static_path.exists():
        return 0
    static_data = json.loads(static_path.read_text(encoding='utf-8'))
    updated = 0
    for m_dir in sorted(ver2.glob('m_*')):
        if not m_dir.is_dir():
            continue
        zh_f = m_dir / 'zh_Hant.json'
        if not zh_f.exists() or m_dir.name not in static_data:
            continue
        individual = json.loads(zh_f.read_text(encoding='utf-8'))
        section = static_data[m_dir.name]
        for jp_key, new_val in individual.items():
            for sub_entries in section.values():
                if isinstance(sub_entries, dict) and jp_key in sub_entries:
                    if sub_entries[jp_key] != new_val:
                        sub_entries[jp_key] = new_val
                        updated += 1
                    break
    if updated > 0:
        static_path.write_text(
            json.dumps(static_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        print(f'static/zh_Hant.json 同步完成：{updated} 筆更新')
    return updated

def sync_client(ver2: Path, client: Path):
    """將開發區的更動同步到用戶區（只同步 zh_Hant.json）"""
    # 單一檔案資料夾：names, ui_texts, static, manifest
    for folder_name in ('names', 'ui_texts', 'static', 'manifest'):
        src = ver2 / folder_name / 'zh_Hant.json'
        dst = client / folder_name / 'zh_Hant.json'
        if src.exists() and dst.exists():
            src_text = src.read_text(encoding='utf-8')
            if dst.read_text(encoding='utf-8') != src_text:
                dst.write_text(src_text, encoding='utf-8')
                print(f'  [用戶區] {folder_name}/zh_Hant.json 已更新')

    # novels：逐子資料夾同步
    src_novels = ver2 / 'novels'
    dst_novels = client / 'novels'
    if src_novels.exists() and dst_novels.exists():
        synced = 0
        for src_f in src_novels.glob('*/zh_Hant.json'):
            sub = src_f.parent.name
            dst_f = dst_novels / sub / 'zh_Hant.json'
            if dst_f.exists():
                src_text = src_f.read_text(encoding='utf-8')
                if dst_f.read_text(encoding='utf-8') != src_text:
                    dst_f.write_text(src_text, encoding='utf-8')
                    synced += 1
            # 新增的劇情（開發區有但用戶區沒有）
            else:
                dst_f.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_f, dst_f)
                synced += 1
        if synced:
            print(f'  [用戶區] novels 同步：{synced} 個劇情更新')


repo = Path(r'D:\dotabyss-translation\GITHUB-dotabyss-translation\Dot-abyess-Lienchu-version')
ver2 = repo / 'dotabyss-translation-new-structure-Ver2'
client = repo / 'dotabyss-translation-client-version'
manifest_f = ver2 / 'manifest' / 'zh_Hant.json'

data = json.loads(manifest_f.read_text(encoding='utf-8'))

# 步驟1：同步 static/zh_Hant.json（m_* → static）
sync_static(ver2)

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

# 步驟2：manifest 更新完畢後，再同步用戶區（確保用戶拿到最新 hash）
sync_client(ver2, client)

subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)
msg = sys.argv[1] if len(sys.argv) > 1 else 'update translations'
subprocess.run(['git', 'commit', '-m', msg], cwd=repo, check=True)
subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo, check=True)
print('完成！')
