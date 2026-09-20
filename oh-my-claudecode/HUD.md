# Combined Statusline: OMC HUD + graft

OpenClaude hanya mendukung **satu** `statusLine` di `settings.json`. Panduan ini menggabungkan [oh-my-claudecode HUD](https://github.com/Yeachan-Heo/oh-my-claudecode) (branch, model, session, context) dengan graft statusline (nodes/edges, sync status, token savings) dalam satu tampilan, mendukung **Windows** dan **Linux/macOS**.

## Prasyarat

- Plugin OMC terpasang di OpenClaude (lihat [INSTALL.md](./INSTALL.md)) — `omc setup` harus sudah dijalankan sehingga HUD ada di jalur Claude Code:
  - Linux/macOS: `~/.claude/hud/omc-hud.mjs`
  - Windows: `%USERPROFILE%\.claude\hud\omc-hud.mjs`
- Plugin graft terpasang — statusline script ada di:
  - Linux/macOS: `~/.openclaude/plugins/cache/local-plugins/graft/<versi>/hooks/graft-statusline.cjs`
  - Windows: `%USERPROFILE%\.openclaude\plugins\cache\local-plugins\graft\<versi>\hooks\graft-statusline.cjs`

Kedua script membaca JSON statusline yang sama dari stdin, jadi bisa dijalankan berturut-turut dengan input yang sama.

## Linux / macOS

Buat file `~/.claude/hud/omc-graft-hud.sh`:

```bash
#!/bin/bash
# Combined statusline: OMC HUD (main) + graft info (appended)
input=$(cat)
GRAFT_CJS=$(ls -d "$HOME"/.openclaude/plugins/cache/local-plugins/graft/*/hooks/graft-statusline.cjs 2>/dev/null | sort -V | tail -1)

printf '%s' "$input" | node "$HOME/.claude/hud/omc-hud.mjs"
# Graft: skip baris pertama (nama model, sudah ditampilkan OMC HUD)
[ -n "$GRAFT_CJS" ] && printf '%s' "$input" | node "$GRAFT_CJS" | tail -n +2 | sed 's/^/  /'
```

Buat executable:

```bash
chmod +x ~/.claude/hud/omc-graft-hud.sh
```

## Windows (PowerShell)

Buat file `%USERPROFILE%\.claude\hud\omc-graft-hud.ps1`:

```powershell
# Combined statusline: OMC HUD (main) + graft info (appended)
$input = [Console]::In.ReadToEnd()
$graftDir = Get-ChildItem "$env:USERPROFILE\.openclaude\plugins\cache\local-plugins\graft" -Directory |
  Sort-Object Name -Descending | Select-Object -First 1
$graftCjs = if ($graftDir) { Join-Path $graftDir.FullName "hooks\graft-statusline.cjs" }

# OMC HUD
$input | node "$env:USERPROFILE\.claude\hud\omc-hud.mjs"

# Graft (skip baris pertama = nama model, sudah ditampilkan OMC HUD)
if ($graftCjs -and (Test-Path $graftCjs)) {
  $graftOut = $input | node $graftCjs
  $graftOut -split "`n" | Select-Object -Skip 1 | ForEach-Object { "  $_" }
}
```

Catatan PowerShell:

- `Select-String -Pattern ...` tidak dipakai karena output graft mengandung ANSI escape codes; pemisahan per baris via `-split "`n"` cukup.
- Jika execution policy memblokir script, jalankan via wrapper cmd (opsi di bawah) yang memanggil `powershell -ExecutionPolicy Bypass -File`.

### Windows wrapper cmd (opsional)

Jika `settings.json` mengeksekusi via cmd, buat `%USERPROFILE%\.claude\hud\omc-graft-hud.cmd`:

```bat
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.claude\hud\omc-graft-hud.ps1"
```

## Daftarkan di settings.json

Di `~/.openclaude/settings.json` (Windows: `%USERPROFILE%\.openclaude\settings.json`), set `statusLine` ke wrapper:

Linux/macOS:

```json
"statusLine": {
  "type": "command",
  "command": "/home/<user>/.claude/hud/omc-graft-hud.sh"
}
```

Windows:

```json
"statusLine": {
  "type": "command",
  "command": "powershell -NoProfile -ExecutionPolicy Bypass -File %USERPROFILE%\\.claude\\hud\\omc-graft-hud.ps1"
}
```

## Test manual

Pipe JSON statusline palsu ke wrapper dan cek output-nya:

Linux/macOS:

```bash
echo '{"model":{"display_name":"test"},"workspace":{"current_dir":"'"$HOME"'"}}' \
  | ~/.claude/hud/omc-graft-hud.sh
```

Windows (PowerShell):

```powershell
'{"model":{"display_name":"test"},"workspace":{"current_dir":"' + $env:USERPROFILE + '"}}' |
  node "$env:USERPROFILE\.claude\hud\omc-hud.mjs"
```

Output yang benar (contoh):

```
branch:master | !24 ?18
[OMC#5.3.0] | Model: test | session:0m | ctx:[----------]0%
  ◤ graft · 133 nodes / 282 edges · ⚠ stale
  ▸ last: settings.json
```

Baris pertama output graft sengaja dibuang (`tail -n +2` / `Select-Object -Skip 1`) karena isinya hanya nama model yang sudah ditampilkan oleh OMC HUD — mencegah duplikasi.

## Troubleshooting

| Gejala | Penyebab | Fix |
|---|---|---|
| Hanya OMC HUD muncul, tanpa graft | `GRAFT_CJS` kosong — path graft plugin beda | Cek `ls ~/.openclaude/plugins/cache/local-plugins/graft/*/hooks/graft-statusline.cjs` |
| Statusline tidak berubah | Settings hanya dibaca saat refresh/statusline re-render | Restart sesi OpenClaude |
| Windows: script tidak jalan | Execution policy | Gunakan wrapper cmd dengan `-ExecutionPolicy Bypass` |
| Karakter aneh di Windows (Unicode) | Console encoding | Jalankan `chcp 65001` atau set `[Console]::OutputEncoding = [Text.Encoding]::UTF8` di awal script ps1 |
