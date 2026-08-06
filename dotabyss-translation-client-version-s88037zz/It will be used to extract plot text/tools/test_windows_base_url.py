import urllib.request
base_candidates = [
    'https://api.abyss-prod-r18.dotabyss.dmmgames.com/resources/windows/r18/aas/1916/aa',
    'https://api.abyss-prod-r18.dotabyss.dmmgames.com/resources/windows/r18/aa/1916/aa',
    'https://api.abyss-prod-r18.dotabyss.dmmgames.com/resources/StandaloneWindows64/r18/aas/1916/aa',
    'https://api.abyss-prod-r18.dotabyss.dmmgames.com/resources/webgl/r18/aas/1916/aa',
]
path = '/0.1.0_unitybuiltinassets_55471b955dce4cf3a6882805deff361b.bundle'
headers = {'User-Agent':'UnityPlayer/6000.0.43f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)','X-Unity-Version':'6000.0.43f1','Range':'bytes=0-15'}
for base in base_candidates:
    url = base + path
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(16)
            print(base, r.status, r.headers.get('Content-Length'), r.headers.get('Content-Range'))
            print('  first bytes', data)
    except Exception as e:
        print(base, 'ERR', repr(e))
