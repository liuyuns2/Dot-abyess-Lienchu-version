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

## AbyssMod dump lookup memory

Treat dump files as runtime lookup evidence, not as translation-category names.

Core rules:

1. Dump keys are authoritative exact lookup strings.
   - Do not guess keys from screenshots.
   - Do not normalize mixed Chinese/Japanese dump keys back into pure Japanese.
   - Preserve `<br>`, `\n`, `\r\n`, color tags, empty tags, extra tags, fullwidth spaces, punctuation, and literal escape forms such as `\uff5e` exactly.

2. Always compare before writing.
   - Build a key set from `static/zh_Hant.json`, `ui_texts/zh_Hant.json`, `add-on/ui_misc/zh_Hant.json`, `names/zh_Hant.json`, and existing `other/**/zh_Hant.json`.
   - Only keys missing from that set are true misses.
   - Skip developer dummy strings, kana filler, dynamic date strings, and already-Chinese second-pass residue unless there is clear in-game evidence that they must be translated.
   - Skip composed keys that include specific dynamic tail values. If the same frame appears with different generated suffixes, such as `報酬受け取り期間：～2025/12/31` and `報酬受け取り期間：～2026/08/01`, or `累計報酬ポイントLv：Lv999` and `Lv30`, the suffix is runtime data. Keep only the pure framework prefix such as `報酬受け取り期間：` or `累計報酬ポイントLv：`; do not add dead-date or dead-level variants.
   - Additional dummy/test patterns to skip: repeated test descriptions like `敵全体に100％...` repeated three times, duplicated same-sentence tests like `対象のやけど耐性を...対象のやけど耐性を...`, skill tests containing `1ダメージを与える`, extreme placeholder levels such as `Lv999`, fullwidth-brace templates such as `｛フロア名｝`, placeholder labels such as `ページ名` or `○○名` (`マナクリスタル名`), and broken escape keys containing literal backslashes such as `\\uff5e...`.

3. Runtime fallback is more important than semantic category neatness.
   - For true dump misses, prefer adding exact keys to both `ui_texts/zh_Hant.json` and `static/zh_Hant.json` under `m_texts.ja` as fallback coverage.
   - Do not create new `other/*` categories just because a dump file has that name.
   - Semantic tables such as `m_ability_details` or `m_nether_codes` may help locate meaning, but the first priority is matching the string the mod actually queries.

4. Mixed keys are real keys.
   - AbyssMod can translate fragments first, compose a new sentence, then query the composed sentence again.
   - Therefore dump strings like `「已翻譯標題」<br>を再生します。よろしいですか？` must be stored exactly in that mixed form.
   - Placeholder abstractions such as `{0}` often do not match these composed runtime strings.
   - When changing a translated term that appears inside generated mixed keys, grep and update those generated keys too.

5. Some UI strings are functional and should not be translated blindly.
   - Strings such as `タッチでプレイヤーIDを表示` may be used by code as state-comparison text.
   - If translating a UI label could break click/toggle behavior, leave it alone or verify the mod/game logic first.

6. Keep diffs small.
   - Do not re-dump large JSON files just to add a few keys.
   - Use minimal patches or careful insertion scripts.
   - Temporary probe/apply scripts are allowed during work, but delete them before finishing.

7. After dump fixes:
   - Validate JSON parse.
   - Check duplicate keys when possible.
   - Re-run dump coverage if dump access is available.
   - Run `python tools\update_manifest.py`.
   - Stage only explicit intended files; never use `git add .` or `git add -A` in this repo.
