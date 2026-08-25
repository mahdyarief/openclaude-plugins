# SciSpace Plugin — Cookie / Login Session Guide

The SciSpace plugin uses headless Playwright to access scispace.com. It reads a
persisted browser session from `storage-state.json` (Playwright's storage-state
format) located in this plugin directory. Every `search_papers` / `scispace_status`
call loads that session automatically, so you only need to authenticate once.

There are two ways to populate `storage-state.json`:

1. **`scispace_login` tool** — opens a visible Playwright browser, you sign in once,
   cookies are saved automatically. Simplest option; no external browser needed.
2. **Import cookies from an already-logged-in browser** (this guide) — if you are
   already signed in to scispace.com with your premium account in Chrome/Firefox,
   you can extract those cookies and write them to `storage-state.json`.

> Note: the imported session is shared with your browser. If the SciSpace session
> in your browser expires or logs out, the plugin loses access too. Session cookies
> typically last a few weeks.

---

## Target format

The plugin reads `storage-state.json` (Playwright storage-state format):

```json
{
  "cookies": [
    {
      "name": "COOKIE_NAME",
      "value": "COOKIE_VALUE",
      "domain": ".scispace.com",
      "path": "/",
      "expires": 1893456000,
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ],
  "origins": []
}
```

Location: `~/.openclaude/plugins/cache/local-plugins/scispace/1.0.0/storage-state.json`

Important cookies for the login session (look for these names):

- `__Secure-next-auth.session-token` or `authjs.session-token` (main session, HttpOnly)
- `csrf-token` or `next-auth.csrf-token`
- Other cookies under `.scispace.com` and `.scispace.io` domains

---

## Method 1 — Chrome DevTools (all cookies, including HttpOnly)

1. Open Chrome, sign in to **scispace.com** with your premium account.
2. Press `F12` → **Application** tab.
3. In the left sidebar: **Storage → Cookies → https://scispace.com**.
4. All cookies are listed (the **HttpOnly** column marks cookies that JavaScript
   cannot read — these are the most important for the session).
5. For each cookie, copy `Name`, `Value`, `Domain`, `Path`, `Expires` into a JSON
   file matching the format above.
6. Save as `storage-state.json` in the plugin directory.

> If there are many cookies (10–20+), Methods 2 or 3 are faster.

---

## Method 2 — "Get cookies.txt LOCALLY" extension (Netscape format)

1. Install the **"Get cookies.txt LOCALLY"** extension from the Chrome Web Store.
2. Open a **scispace.com** tab (signed in), click the extension icon.
3. Click **Export** — you get a `cookies.txt` file in Netscape format:

```
# Netscape HTTP Cookie File
.scispace.com	TRUE	/	FALSE	1893456000	__Secure-next-auth.session-token	<value>
```

4. Convert to Playwright format with this Node script (`convert-cookies.js`,
   run `node convert-cookies.js` in the same folder as your `cookies.txt`):

```js
const fs = require('fs');

const lines = fs.readFileSync('cookies.txt', 'utf8').split('\n');
const cookies = [];

for (const line of lines) {
  if (line.startsWith('#') || !line.trim()) continue;
  const [domain, , path, secure, expires, name, value] = line.split('\t');
  cookies.push({
    name,
    value,
    domain: domain.startsWith('.') ? domain : '.' + domain,
    path,
    expires: parseInt(expires, 10) || -1,
    httpOnly: true, // cookies.txt does not mark this; auth sessions are usually HttpOnly
    secure: secure === 'TRUE',
    sameSite: 'Lax',
  });
}

fs.writeFileSync('storage-state.json', JSON.stringify({ cookies, origins: [] }, null, 2));
console.log('Converted', cookies.length, 'cookies → storage-state.json');
```

---

## Method 3 — CDP one-liner (most accurate, automated)

Fastest and most accurate — grabs cookies exactly as the browser sends them.
Requires Node and the `playwright` package (already installed in this plugin's
`node_modules`).

1. Close Chrome, then reopen it with remote debugging:

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp
```

2. Sign in to scispace.com in that Chrome window.
3. Run this script from the plugin directory:

```js
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const ctx = browser.contexts()[0];
  const cookies = await ctx.cookies('https://scispace.com');
  const state = { cookies, origins: [] };
  fs.writeFileSync('storage-state.json', JSON.stringify(state, null, 2));
  console.log('Saved', cookies.length, 'cookies');
  await browser.close();
})();
```

4. `storage-state.json` is written directly — just restart/keep the plugin as is.

---

## Verification

After placing the file, run from the plugin directory:

```bash
cd ~/.openclaude/plugins/cache/local-plugins/scispace/1.0.0
node -e "
const c = require('./scispace-client.js');
c.status().then(r => console.log(JSON.stringify(r, null, 2)));
"
```

`loggedIn: true` and `hasStoredSession: true` mean the cookies work. If
`loggedIn: false`, re-check the session cookie names (Method 1, step 5) — an
important cookie is probably missing.

---

## Troubleshooting

- **Session expired** — SciSpace session cookies last a few weeks. Re-run one of
  the methods above when access stops working.
- **403 / blocked page** — the headless session lost authentication or the WAF
  flagged the request pattern. Refresh the cookies, and make sure only scispace.com
  cookies are imported.
- **Premium features missing** — confirm you exported cookies from a browser where
  the premium account is actively signed in (check the account menu on scispace.com).
