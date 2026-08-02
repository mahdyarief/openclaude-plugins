const { writeFile, mkdtemp } = require("node:fs/promises");
const { execFile } = require("node:child_process");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

const PANDOC = process.env.PANDOC_PATH || "pandoc";

const HTML_CSS = String.raw`
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1rem;
    line-height: 1.7;
    color: #1a1a1a;
    background: #fff;
  }
  h1, h2, h3, h4, h5, h6 { margin-top: 1.5em; margin-bottom: 0.5em; }
  h1 { font-size: 1.75rem; border-bottom: 2px solid #eee; padding-bottom: 0.25rem; }
  h2 { font-size: 1.5rem; border-bottom: 1px solid #eee; padding-bottom: 0.25rem; }
  h3 { font-size: 1.25rem; }
  pre {
    background: #f5f5f5;
    padding: 1rem;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 0.875rem;
    line-height: 1.5;
  }
  code {
    font-family: "Fira Code", "Cascadia Code", Consolas, monospace;
    font-size: 0.875em;
    background: #f0f0f0;
    padding: 0.125em 0.25em;
    border-radius: 3px;
  }
  pre code { background: none; padding: 0; font-size: inherit; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
  th, td { border: 1px solid #ddd; padding: 0.5rem; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; }
  tr:nth-child(even) { background: #fafafa; }
  img { max-width: 100%; }
  blockquote {
    border-left: 4px solid #ddd;
    margin-left: 0;
    padding-left: 1rem;
    color: #666;
  }
  a { color: #0366d6; }
  hr { border: none; border-top: 1px solid #eee; margin: 2rem 0; }
</style>
${""}
`;

async function renderHtml(markdown, outputPath) {
  const tmpDir = await mkdtemp(join(tmpdir(), "md-preview-html-"));
  const mdPath = join(tmpDir, "input.md");
  const cssPath = join(tmpDir, "header.css");

  await writeFile(mdPath, markdown, "utf-8");
  await writeFile(cssPath, HTML_CSS, "utf-8");

  const htmlPath = outputPath || join(tmpDir, "output.html");

  const args = [
    mdPath,
    "-o", htmlPath,
    "--from", "markdown+autolink_bare_uris+tex_math_dollars",
    "--to", "html5",
    "--standalone",
    "--mathml",
    "--highlight-style", "tango",
    "--include-in-header", cssPath,
    "--metadata", "title=Markdown Preview",
  ];

  await new Promise((resolve, reject) => {
    execFile(PANDOC, args, { timeout: 60000 }, (err, stdout, stderr) => {
      if (err) { reject(new Error(`pandoc HTML failed: ${stderr || err.message}`)); return; }
      resolve();
    });
  });

  return htmlPath;
}

module.exports = { renderHtml };
