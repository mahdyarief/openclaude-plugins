# oh-my-claudecode (OMC) — Install Manual untuk OpenClaude

OMC ([Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)) v5.3.0 adalah plugin multi-agent orchestration format Claude Code standar (`.claude-plugin/plugin.json`), sehingga kompatibel dengan OpenClaude. Namun `omc setup` dari npm CLI hanya menulis ke jalur Claude Code (`~/.claude/`), **bukan** ke jalur OpenClaude (`~/.openclaude/plugins/`). Karena itu installasinya perlu dilakukan manual di tiga tempat.

## Prasyarat

- Node.js 18+
- OpenClaude terinstall

## Langkah 1 — Install CLI (opsional tapi disarankan)

```bash
sudo npm i -g oh-my-claude-sisyphus@latest
omc setup        # men-sync skills/hooks/HUD ke ~/.claude/ (jalur Claude Code)
omc doctor conflicts   # cek konflik dengan plugin lain
```

Warning `prebuild-install@7.1.3 deprecated` saat install itu normal (issue #2913), bukan tanda gagal.

## Langkah 2 — Kloning repo ke plugin cache OpenClaude

Path harus mengikuti konvensi `cache/local-plugins/<nama>/<versi>`:

```bash
mkdir -p ~/.openclaude/plugins/cache/local-plugins/oh-my-claudecode
git clone --depth 1 https://github.com/Yeachan-Heo/oh-my-claudecode \
  ~/.openclaude/plugins/cache/local-plugins/oh-my-claudecode/5.3.0
```

Verifikasi manifest ada di `5.3.0/.claude-plugin/plugin.json`.

## Langkah 3 — Daftarkan di `installed_plugins.json`

Tambahkan entry baru di `~/.openclaude/plugins/installed_plugins.json` (array `plugins`):

```json
"oh-my-claudecode@local-plugins": [
  {
    "scope": "user",
    "installPath": "/home/<user>/.openclaude/plugins/cache/local-plugins/oh-my-claudecode/5.3.0",
    "version": "5.3.0",
    "installedAt": "<ISO timestamp>",
    "lastUpdated": "<ISO timestamp>",
    "gitCommitSha": "<git rev-parse HEAD dari langkah 2>"
  }
]
```

## Langkah 4 — Daftarkan di `enabledPlugins` (WAJIB — paling sering terlewat)

OpenClaude hanya memuat plugin yang tercantum di field `enabledPlugins` pada `~/.openclaude/settings.json`. Tambahkan:

```json
"enabledPlugins": {
  "oh-my-claudecode@local-plugins": true
}
```

Tanpa entry ini, plugin akan terdaftar tapi **tidak pernah dimuat** (reload tetap menampilkan jumlah plugin lama).

## Langkah 5 — Daftarkan di marketplace `local-plugins`

```bash
# Buat folder plugin di marketplace dengan struktur benar
mkdir -p ~/.openclaude/plugins/marketplaces/local-plugins/oh-my-claudecode/.claude-plugin
cd ~/.openclaude/plugins/cache/local-plugins/oh-my-claudecode/5.3.0
cp .claude-plugin/plugin.json ~/.openclaude/plugins/marketplaces/local-plugins/oh-my-claudecode/.claude-plugin/
cp -r skills commands agents hooks .mcp.json ~/.openclaude/plugins/marketplaces/local-plugins/oh-my-claudecode/
```

**Gotcha:** jangan `cp -r .claude-plugin <dest>` saat dest belum ada — isi `.claude-plugin` akan menempel di root folder, sehingga loader tidak menemukan `.claude-plugin/plugin.json`. Pastikan path-nya `.claude-plugin/plugin.json`.

Lalu tambahkan entry di `~/.openclaude/plugins/marketplaces/local-plugins/.claude-plugin/marketplace.json`:

```json
{
  "name": "oh-my-claudecode",
  "source": "./oh-my-claudecode",
  "description": "oh-my-claudecode (OMC) v5.3.0 — Teams-first multi-agent orchestration. 36 skills (autopilot, team, ralplan, ultragoal, wiki, verify, dll), 19 agents, hooks, dan MCP server.",
  "category": "development"
}
```

## Langkah 6 — Reload

```
/reload-plugins
```

Output yang benar: `Reloaded: 10 plugins · 25 agents · 30 hooks · 10 plugin MCP servers` (angka sesuai total plugin + OMC).

Cek keberhasilan di sesi: agent types baru muncul dengan prefix `oh-my-claudecode:` (planner, executor, critic, dll.) dan skills `/oh-my-claudecode:autopilot`, `/oh-my-claudecode:team`, dll.

## Bonus — Statusline gabungan OMC HUD + graft

Untuk menampilkan OMC HUD sekaligus graft statusline dalam satu tampilan (support Windows & Linux), ikuti panduan terpisah: [HUD.md](./HUD.md).

## Troubleshooting

| Gejala | Penyebab | Fix |
|---|---|---|
| Reload tetap jumlah plugin lama | Tidak ada di `enabledPlugins` (settings.json) | Langkah 4 |
| Reload tetap setelah fix | Konfigurasi hanya dibaca saat startup | Restart sesi OpenClaude penuh |
| Skill lama men-shadow skill OMC | Duplikat nama di `~/.openclaude/skills` | Hapus/rename salah satu (`omc doctor conflicts`) |
| `plugin.json` tidak ditemukan saat load | Struktur folder marketplace salah (`.claude-plugin` nempel di root) | Langkah 5, perhatikan gotcha |
