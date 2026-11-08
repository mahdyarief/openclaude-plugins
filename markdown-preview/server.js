const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");

const { readFile } = require("node:fs/promises");
const { resolve } = require("path");
const { renderPdf } = require("./lib/render-pdf.js");
const { renderHtml } = require("./lib/render-html.js");
const { renderPng } = require("./lib/render-png.js");

const TOOLS = [
  {
    name: "markdown_to_pdf",
    description:
      "Convert markdown content to a PDF file using md2pdf (Playwright/Chromium engine). Supports Mermaid diagrams, KaTeX math, syntax highlighting, tables, callouts, TOC, page numbers, and multiple built-in themes (default, github, obsidian-light, obsidian-dark, dracula, nord, academic) plus custom CSS themes. Returns the path to the generated PDF file.",
    inputSchema: {
      type: "object",
      properties: {
        source: {
          type: "string",
          description: "Raw markdown string to convert. Takes priority over path if both are provided.",
        },
        path: {
          type: "string",
          description: "Absolute path to a .md file on disk. Used when source is not provided.",
        },
        outputPath: {
          type: "string",
          description: "Optional output path for the PDF file. Defaults to a temp file.",
        },
        theme: {
          type: "string",
          description:
            "Theme. Plugin themes: academic (thesis/report, Palatino), jurnal (two-column journal/conference paper, auto I/II/III sections), tugas-kuliah (Indonesian campus report: Times 12pt, spasi 1.5, auto BAB I / 1.1 numbering — write headings without manual numbers), artikel (magazine long-form), tufte (lecture notes; blockquotes become margin sidenotes), proposal (research/grant proposal; first blockquote is a boxed summary), naskah (plain Courier double-spaced submission manuscript), surat-dinas (Indonesian official letter: H1 = kop surat, next line = address), memo (executive briefing; first blockquote = executive summary), teknis (technical docs/SOP; blockquotes become NOTE callouts), notulen (compact meeting minutes; bullets render as checkboxes), zine (brutalist essay/opinion), catatan-buku, default. md2pdf built-ins: github, obsidian-light, obsidian-dark, dracula, nord. Or an absolute path to a .css file. Defaults to 'default'.",
          default: "default",
        },
        mermaidTheme: {
          type: "string",
          description:
            "Optional Mermaid diagram theme override (default, base, dark, neutral). Auto-matched to the selected theme when omitted.",
        },
        open: {
          type: "boolean",
          description: "If true, opens the PDF in the default viewer after generation.",
          default: false,
        },
      },
    },
  },
  {
    name: "markdown_to_html",
    description:
      "Convert markdown content to a standalone HTML file using pandoc. Includes syntax highlighting, MathML for equations, and clean default styling. Returns the path to the generated HTML file.",
    inputSchema: {
      type: "object",
      properties: {
        source: {
          type: "string",
          description: "Raw markdown string to convert. Takes priority over path if both are provided.",
        },
        path: {
          type: "string",
          description: "Absolute path to a .md file on disk. Used when source is not provided.",
        },
        outputPath: {
          type: "string",
          description: "Optional output path for the HTML file. Defaults to a temp file.",
        },
        open: {
          type: "boolean",
          description: "If true, opens the HTML in the default browser after generation.",
          default: false,
        },
      },
    },
  },
  {
    name: "markdown_to_png",
    description:
      "Convert markdown content to PNG image files using pandoc + DrissionPage (headless Chrome via CDP). Returns paths to the generated PNG files. Requires Python 3.6+, DrissionPage, and an installed Chrome or Edge browser.",
    inputSchema: {
      type: "object",
      properties: {
        source: {
          type: "string",
          description: "Raw markdown string to convert. Takes priority over path if both are provided.",
        },
        path: {
          type: "string",
          description: "Absolute path to a .md file on disk. Used when source is not provided.",
        },
        outputPath: {
          type: "string",
          description: "Optional output path prefix for the PNG file(s). Defaults to a temp file.",
        },
        open: {
          type: "boolean",
          description: "If true, opens the first PNG in the default viewer after generation.",
          default: false,
        },
      },
    },
  },
];

async function resolveSource(args) {
  if (args.source && args.source.trim()) {
    return { markdown: args.source, sourceDescription: "provided markdown" };
  }
  if (args.path) {
    const absPath = resolve(args.path);
    const content = await readFile(absPath, "utf-8");
    return { markdown: content, sourceDescription: `file: ${absPath}` };
  }
  throw new Error(
    "Either 'source' (markdown string) or 'path' (file path) must be provided."
  );
}

// Open a file with the OS default handler (cross-platform).
function openPath(target) {
  const { execFile } = require("node:child_process");
  if (process.platform === "win32") {
    execFile("start", [target], { shell: true });
  } else if (process.platform === "darwin") {
    execFile("open", [target]);
  } else {
    execFile("xdg-open", [target]);
  }
}

async function dispatchTool(name, args) {
  const { markdown, sourceDescription } = await resolveSource(args);

  switch (name) {
    case "markdown_to_pdf": {
      const pdfPath = await renderPdf(markdown, args.outputPath, {
        theme: args.theme,
        mermaidTheme: args.mermaidTheme,
      });
      if (args.open) openPath(pdfPath);
      return `PDF generated from ${sourceDescription}:\n- ${pdfPath}`;
    }
    case "markdown_to_html": {
      const htmlPath = await renderHtml(markdown, args.outputPath);
      if (args.open) openPath(htmlPath);
      return `HTML generated from ${sourceDescription}:\n- ${htmlPath}`;
    }
    case "markdown_to_png": {
      const result = await renderPng(markdown, args.outputPath);
      if (args.open && result.paths.length > 0) openPath(result.paths[0]);
      const title =
        result.paths.length > 1
          ? `PNG pages (${result.paths.length}) generated from ${sourceDescription}:`
          : `PNG generated from ${sourceDescription}:`;
      return [title, ...result.paths.map((p) => `- ${p}`)].join("\n");
    }
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

const server = new Server(
  { name: "markdown-preview", version: "2.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    const result = await dispatchTool(
      request.params.name,
      request.params.arguments
    );
    return {
      content: [{ type: "text", text: result }],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

const transport = new StdioServerTransport();
server.connect(transport).catch(console.error);
