import csv
from pathlib import Path
p = Path(r'E:\離線板\output\windows_1916_catalog_1\windows_1916_catalog_1_output\categories\remote_or_local_manifest.csv')
rows = list(csv.DictReader(p.open(encoding='utf-8-sig')))
remote = [r for r in rows if 'RemoteLoadPath' in r['internal_id']]
local = [r for r in rows if 'LocalLoadPath' in r['internal_id']]
size = sum(int(r['bundle_size'] or 0) for r in remote)
print('total bundle rows', len(rows))
print('remote rows', len(remote))
print('local rows', len(local))
print('remote size bytes', size)
print('remote size GiB', round(size/1024/1024/1024, 2))
for r in remote[:3]:
    print(r['primary_key'], r['internal_id'], r['bundle_size'])
