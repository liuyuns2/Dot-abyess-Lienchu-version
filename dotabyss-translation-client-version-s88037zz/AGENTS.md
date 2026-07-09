# DotAbyss Localization Workflow Memory

Before committing or pushing translation changes, always refresh the manifest hashes.

Required flow:

1. Edit translation files.
2. Rebuild novel bundles and update novel bundle hashes:
   `python tools\build_novels_all.py`
3. Recalculate non-novel hashes and the manifest hash:
   `python tools\update_manifest.py`
4. Validate JSON.
5. Review `git status` and stage only intended files.
6. Commit and push.

Hash ownership:

- `novels/<id>/zh_Hant.json` changes require rebuilding `novels_*_all/zh_Hant.json` and updating `manifest/zh_Hant.json` fields `novels_evs_all`, `novels_hmn_all`, `novels_hmr_all`, `novels_mas_all`, and `novels_men_all`.
- `names/zh_Hant.json`, `ui_texts/zh_Hant.json`, `static/zh_Hant.json`, `add-on/**/zh_Hant.json`, and `other/**/zh_Hant.json` changes require updating their corresponding manifest MD5 fields.
- After any manifest content changes, update `manifest/zh_Hant.json` field `hash`.

Never assume CDN or local game cache will refresh correctly unless manifest hashes match the current file contents.
