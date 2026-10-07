# Fonts bundled in the worker image

Used by `modules/notes/worker/export.py` for text boxes, sticky numbers and the appendix of a flattened PDF export.

| File | Family | Licence |
| --- | --- | --- |
| `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf` | Noto Sans (Latin, Greek, Cyrillic) 2.015 | SIL Open Font License 1.1 |
| `NotoSansDevanagari-Regular.ttf`, `NotoSansDevanagari-Bold.ttf` | Noto Sans Devanagari 2.007 | SIL Open Font License 1.1 |

**Licence check (2026-10-08).** The licence string is read from the `name` table of each downloaded file ("This Font Software is
licensed under the SIL Open Font License, Version 1.1", https://scripts.sil.org/OFL), and the copyright line is "Copyright 2022 The
Noto Project Authors". OFL 1.1 allows bundling, embedding in documents and redistribution; the fonts must not be sold on their own and
the licence text travels with them. The image therefore keeps `OFL.txt` next to the fonts (see the Dockerfile). The repository
`notofonts/notofonts.github.io` publishes no separate OFL file at `fonts/<Family>/`, so the licence text is taken from the font
`name` table (nameID 13) and the upstream project page https://github.com/notofonts/notofonts.github.io. **Counsel should
confirm before launch**, as the ERD asks ("verify each licence at adoption").

## Exact sources (hinted TTF, `main` branch of github.com/notofonts/notofonts.github.io)

```
https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSans/hinted/ttf/NotoSans-Regular.ttf
https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSans/hinted/ttf/NotoSans-Bold.ttf
https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Regular.ttf
https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Bold.ttf
```

The branch can move, so the Dockerfile verifies SHA-256 checksums and fails the build if upstream changes a file:

```
478c558ea716033cd60c03438f628dfa75694dcf6b5f6d505a2f05fd2b4f3823  NotoSans-Regular.ttf
1df075a380fc7cb898acf64c1f7b3b4dd780de3caa860178bf929de35817a913  NotoSans-Bold.ttf
4e3c66638958c3e2ab5d37f47a8deb89fffeb7be9985c665a519bbc7ba762313  NotoSansDevanagari-Regular.ttf
6a09c8d797cfc803d32cdc731e809424d74cbaff59f503de34ade421a08e5bc2  NotoSansDevanagari-Bold.ttf
```

To update: download the new files, review the version in the `name` table, replace the hashes in the Dockerfile and here.
(A commit-pinned URL would be stronger; GitHub's API was not reachable when this was written, so the content hash is the pin.)

## Where they live

- Image: `/usr/share/fonts/truetype/artha` (env `WORKER_FONTS_DIR` overrides). The export function takes `fonts_dir` explicitly.
- Local tests: `WORKER_FONTS_DIR`, else `~/.cache/artha-test-fonts`, else the tests download the four files there once;
  they skip (not fail) only when the fonts are missing and there is no network.
- Not committed to git (about 1.7 MB).
