const { writeFile, mkdtemp } = require("node:fs/promises");
const { execFile } = require("node:child_process");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

const PANDOC = process.env.PANDOC_PATH || "pandoc";
const PDF_ENGINE = process.env.PDF_ENGINE || "xelatex";

// Font set per-OS: Windows has Times New Roman/Arial/Courier New;
// Linux/macOS commonly have Liberation/DejaVu families instead.
const FONTS =
  process.platform === "win32"
    ? {
        main: "Times New Roman",
        sans: "Arial",
        mono: "Courier New",
      }
    : {
        main: "Liberation Serif",
        sans: "Liberation Sans",
        mono: "DejaVu Sans Mono",
      };

const LATEX_PREAMBLE = String.raw`
\usepackage{fontspec}
\usepackage{xunicode}
\usepackage{xltxtra}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{fancyvrb}
\usepackage{upquote}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{framed}
\providecolor{shadecolor}{RGB}{248,248,248}
\defaultfontfeatures{Ligatures=TeX}
\setmainfont{${FONTS.main}}
\setsansfont{${FONTS.sans}}
\setmonofont{${FONTS.mono}}
\ifdefined\Shaded\renewenvironment{Shaded}{\begin{snugshade}\small}{\end{snugshade}}\fi
\setcounter{secnumdepth}{0}
`;

async function renderPdf(markdown, outputPath) {
  const tmpDir = await mkdtemp(join(tmpdir(), "md-preview-pdf-"));
  const mdPath = join(tmpDir, "input.md");
  const preamblePath = join(tmpDir, "preamble.tex");

  await writeFile(mdPath, markdown, "utf-8");
  await writeFile(preamblePath, LATEX_PREAMBLE, "utf-8");

  const pdfPath = outputPath || join(tmpDir, "output.pdf");

  const args = [
    mdPath,
    "-o", pdfPath,
    "--from", "markdown+autolink_bare_uris+tex_math_dollars",
    "--standalone",
    `--pdf-engine=${PDF_ENGINE}`,
    "-V", "geometry:margin=1in",
    "-V", "papersize:a4",
    "--include-in-header", preamblePath,
    "--highlight-style", "pygments",
    "--variable", "graphics",
  ];

  await new Promise((resolve, reject) => {
    execFile(PANDOC, args, { timeout: 120000 }, (err, stdout, stderr) => {
      if (err) {
        const msg = stderr || err.message;
        reject(new Error(`pandoc PDF failed: ${msg}`));
        return;
      }
      resolve();
    });
  });

  return pdfPath;
}

module.exports = { renderPdf };
