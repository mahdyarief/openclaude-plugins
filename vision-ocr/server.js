const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");
const { execFile } = require("child_process");
const { access, unlink, writeFile } = require("fs/promises");
const { tmpdir } = require("os");
const { join } = require("path");
const { promisify } = require("util");

const execFileAsync = promisify(execFile);

// Detect Python binary: "python" on Windows (and many systems), "python3" on
// Linux/macOS where plain "python" is often absent. Override with PYTHON_PATH.
function detectPython() {
  if (process.env.PYTHON_PATH) return process.env.PYTHON_PATH;
  const candidates = process.platform === "win32" ? ["python", "py"] : ["python3", "python"];
  const { spawnSync } = require("child_process");
  for (const bin of candidates) {
    try {
      const r = spawnSync(bin, ["--version"], { timeout: 10000 });
      if (r.status === 0) return bin;
    } catch { /* try next */ }
  }
  return candidates[0];
}
const PYTHON = detectPython();

// ─── Constants ───────────────────────────────────────────────────────────────

const SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"];
const SUPPORTED_PDF_FORMATS = [".pdf"];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function isSupportedImage(path) {
  const lower = path.toLowerCase();
  return SUPPORTED_IMAGE_FORMATS.some((ext) => lower.endsWith(ext));
}

function isPdf(path) {
  return path.toLowerCase().endsWith(".pdf");
}

function isUrl(input) {
  return /^https?:\/\//i.test(input);
}

function isSupportedPath(path) {
  return isSupportedImage(path) || isPdf(path);
}

async function fileExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function normalizeImageUrl(url) {
  const imgurMatch = url.match(/imgur\.com\/([a-zA-Z0-9]+)(?:\.\w+)?$/);
  if (imgurMatch) {
    return `https://i.imgur.com/${imgurMatch[1]}.png`;
  }
  return url;
}

async function downloadToTemp(url) {
  const match = url.match(/\.\w+$/);
  const ext = isSupportedImage(url) && match ? match[0] : ".png";
  const tmpPath = join(tmpdir(), `vision-ocr-${Date.now()}${ext}`);

  const { stdout } = await execFileAsync(PYTHON, [
    "-c",
    `
import urllib.request
url = "${url.replace(/\\/g, "\\\\")}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    data = r.read()
with open("${tmpPath.replace(/\\/g, "\\\\")}", "wb") as f:
    f.write(data)
print("OK")
`,
  ], { timeout: 30000 });

  if (!stdout.trim().includes("OK")) {
    throw new Error(`Failed to download: ${url}`);
  }

  return tmpPath;
}

// ─── OCR Engine ──────────────────────────────────────────────────────────────

async function runOcrOnImage(imagePath, preprocess) {
  const escapedPath = imagePath.replace(/\\/g, "\\\\");
  const script = `
import json, sys
from rapidocr_onnxruntime import RapidOCR
from PIL import Image, ImageOps, ImageEnhance
import numpy as np

path = r"${escapedPath}"
preprocess_mode = "${preprocess}"

try:
    im = Image.open(path).convert("RGB")
except Exception as e:
    print(json.dumps({"error": f"Cannot open image: {e}"}))
    sys.exit(1)

if preprocess_mode == "grayscale":
    im = ImageOps.grayscale(im).convert("RGB")
elif preprocess_mode == "high_contrast":
    im = ImageOps.grayscale(im)
    im = ImageEnhance.Contrast(im).enhance(2.0)
    im = im.convert("RGB")
elif preprocess_mode == "upscale":
    w, h = im.size
    im = im.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
elif preprocess_mode == "sharpen":
    from PIL import ImageFilter
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
elif preprocess_mode == "auto":
    from PIL import ImageFilter, ImageStat
    gray = ImageOps.grayscale(im)
    stat = ImageStat.Stat(gray)
    contrast = stat.stddev[0]
    w, h = im.size
    is_small = max(w, h) < 400
    is_low_contrast = contrast < 40
    if is_small and is_low_contrast:
        im = im.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        im = ImageOps.grayscale(im)
        im = ImageEnhance.Contrast(im).enhance(2.0)
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        im = im.convert("RGB")
    elif is_small:
        im = im.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
    elif is_low_contrast:
        im = ImageOps.grayscale(im)
        im = ImageEnhance.Contrast(im).enhance(1.8)
        im = im.convert("RGB")
    else:
        im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=100, threshold=2))

w, h = im.size
max_dim = 1024
if max(w, h) > max_dim:
    scale = max_dim / max(w, h)
    im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

arr = np.array(im)
engine = RapidOCR()
result, elapse = engine(arr)

if result is None:
    print(json.dumps({"texts": [], "elapsed": elapse if isinstance(elapse, list) else [elapse]}))
    sys.exit(0)

texts = []
for item in result:
    bbox, text, conf = item[0], item[1], float(item[2])
    texts.append({"text": text, "confidence": round(conf, 4), "bbox": bbox})

print(json.dumps({"texts": texts, "elapsed": elapse if isinstance(elapse, list) else [elapse]}))
`;

  const { stdout } = await execFileAsync(PYTHON, ["-c", script], {
    timeout: 60000,
    maxBuffer: 10 * 1024 * 1024,
  });

  return JSON.parse(stdout.trim());
}

async function runOcrOnPdf(pdfPath, pages, preprocess) {
  const escapedPath = pdfPath.replace(/\\/g, "\\\\");
  const script = `
import json, sys, os, tempfile
import fitz
from rapidocr_onnxruntime import RapidOCR
from PIL import Image, ImageOps, ImageEnhance
import numpy as np

pdf_path = r"${escapedPath}"
pages_arg = "${pages}"
preprocess_mode = "${preprocess}"

try:
    doc = fitz.open(pdf_path)
except Exception as e:
    print(json.dumps({"error": f"Cannot open PDF: {e}"}))
    sys.exit(1)

total_pages = len(doc)

def parse_pages(spec, total):
    if not spec or spec == "all":
        return list(range(total))
    result = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = max(1, int(start))
            end = min(total, int(end))
            result.extend(range(start - 1, end))
        else:
            idx = int(part) - 1
            if 0 <= idx < total:
                result.append(idx)
    return sorted(set(result))

page_indices = parse_pages(pages_arg, total_pages)

engine = RapidOCR()
results = []
tmp_dir = tempfile.mkdtemp(prefix="ocr_pdf_")

try:
    for i in page_indices:
        page = doc[i]
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_path = os.path.join(tmp_dir, f"page_{i}.png")
        pix.save(img_path)

        im = Image.open(img_path).convert("RGB")
        if preprocess_mode == "grayscale":
            im = ImageOps.grayscale(im).convert("RGB")
        elif preprocess_mode == "high_contrast":
            im = ImageOps.grayscale(im)
            im = ImageEnhance.Contrast(im).enhance(2.0)
            im = im.convert("RGB")

        w, h = im.size
        max_dim = 1024
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        arr = np.array(im)
        result, elapse = engine(arr)

        texts = []
        if result:
            for item in result:
                bbox, text, conf = item[0], item[1], float(item[2])
                texts.append({"text": text, "confidence": round(conf, 4), "bbox": bbox})

        results.append({
            "pageNumber": i + 1,
            "texts": texts,
            "elapsed": elapse if isinstance(elapse, list) else [elapse],
        })

        os.remove(img_path)
finally:
    try:
        os.rmdir(tmp_dir)
    except:
        pass
    doc.close()

print(json.dumps({"pages": results, "totalPages": total_pages}))
`;

  const { stdout } = await execFileAsync(PYTHON, ["-c", script], {
    timeout: 120000,
    maxBuffer: 20 * 1024 * 1024,
  });

  return JSON.parse(stdout.trim());
}

// ─── Formatters ──────────────────────────────────────────────────────────────

function formatImageResult(result, filePath, detail) {
  const lines = [];
  lines.push(`## OCR Result: ${filePath}`);
  lines.push("");

  if (result.texts.length === 0) {
    lines.push("**No text detected in image.**");
    return lines.join("\n");
  }

  lines.push(`Detected **${result.texts.length}** text region(s).`);
  if (result.elapsed && result.elapsed.length > 0) {
    const totalTime = result.elapsed.reduce((a, b) => a + b, 0);
    lines.push(`Processing time: ${totalTime.toFixed(2)}s`);
  }
  lines.push("");

  if (detail) {
    lines.push("### Text Regions");
    lines.push("");
    for (const item of result.texts) {
      const ys = item.bbox.map((p) => p[1]);
      const xs = item.bbox.map((p) => p[0]);
      lines.push(
        `- \`${item.text}\` (conf: ${(item.confidence * 100).toFixed(1)}%, pos: x=${Math.min(...xs).toFixed(0)}-${Math.max(...xs).toFixed(0)} y=${Math.min(...ys).toFixed(0)}-${Math.max(...ys).toFixed(0)})`,
      );
    }
  } else {
    lines.push("### Extracted Text");
    lines.push("");
    const sorted = [...result.texts].sort((a, b) => {
      const ayMin = Math.min(...a.bbox.map((p) => p[1]));
      const byMin = Math.min(...b.bbox.map((p) => p[1]));
      return ayMin - byMin;
    });
    lines.push("```");
    for (const item of sorted) {
      lines.push(item.text);
    }
    lines.push("```");
  }

  return lines.join("\n");
}

function formatPdfResult(result, filePath, detail) {
  const lines = [];
  lines.push(`## PDF OCR Result: ${filePath}`);
  lines.push("");
  lines.push(`PDF has **${result.totalPages}** page(s). OCR'd **${result.pages.length}** page(s).`);
  lines.push("");

  const allEmpty = result.pages.every((p) => p.texts.length === 0);
  if (allEmpty) {
    lines.push("**No text detected in any page.**");
    return lines.join("\n");
  }

  for (const page of result.pages) {
    lines.push(`### Page ${page.pageNumber}`);
    lines.push("");

    if (page.texts.length === 0) {
      lines.push("*(no text detected)*");
      lines.push("");
      continue;
    }

    lines.push(`${page.texts.length} text region(s).`);
    if (page.elapsed && page.elapsed.length > 0) {
      const totalTime = page.elapsed.reduce((a, b) => a + b, 0);
      lines.push(`Processing time: ${totalTime.toFixed(2)}s`);
    }
    lines.push("");

    if (detail) {
      for (const item of page.texts) {
        const ys = item.bbox.map((p) => p[1]);
        const xs = item.bbox.map((p) => p[0]);
        lines.push(
          `- \`${item.text}\` (conf: ${(item.confidence * 100).toFixed(1)}%, pos: x=${Math.min(...xs).toFixed(0)}-${Math.max(...xs).toFixed(0)} y=${Math.min(...ys).toFixed(0)}-${Math.max(...ys).toFixed(0)})`,
        );
      }
    } else {
      const sorted = [...page.texts].sort((a, b) => {
        const ayMin = Math.min(...a.bbox.map((p) => p[1]));
        const byMin = Math.min(...b.bbox.map((p) => p[1]));
        return ayMin - byMin;
      });
      lines.push("```");
      for (const item of sorted) {
        lines.push(item.text);
      }
      lines.push("```");
    }
    lines.push("");
  }

  return lines.join("\n");
}

// ─── Tool Definition ─────────────────────────────────────────────────────────

const TOOLS = [
  {
    name: "vision-ocr",
    description: "Extract text from images, PDFs, and URLs using RapidOCR (ONNX, CPU). Supports PNG, JPG, GIF, BMP, WebP, TIFF, PDF, and image URLs (including Imgur). For PDFs, supports page selection. Use when the AI model cannot see images directly.",
    inputSchema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Path to image/PDF file, or a URL (e.g. https://imgur.com/XXXXX or direct image URL)",
        },
        detail: {
          type: "boolean",
          description: "If true, return per-region details (text, confidence, bounding box). Default: false.",
        },
        preprocess: {
          type: "string",
          enum: ["none", "grayscale", "high_contrast", "upscale", "sharpen", "auto"],
          description: "Image preprocessing to improve OCR accuracy. 'auto' analyzes the image and picks the best preprocessing.",
        },
        pages: {
          type: "string",
          description: "PDF page selection. Examples: 'all' (default), '1', '1-3', '1,3,5'. Ignored for images/URLs.",
        },
      },
      required: ["path"],
    },
  },
];

// ─── MCP Server ──────────────────────────────────────────────────────────────

const server = new Server(
  { name: "vision-ocr", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name !== "vision-ocr") {
    return {
      content: [{ type: "text", text: JSON.stringify({ error: `Unknown tool: ${name}` }) }],
    };
  }

  const input = args.path;
  const detail = args.detail === true;
  const preprocess = args.preprocess || "none";
  const pages = args.pages || "all";

  if (!input) {
    return {
      content: [{ type: "text", text: "Error: 'path' parameter is required." }],
    };
  }

  let tmpFile = null;

  try {
    if (isUrl(input)) {
      const url = normalizeImageUrl(input);
      tmpFile = await downloadToTemp(url);
      const result = await runOcrOnImage(tmpFile, preprocess);

      if (result.error) {
        return { content: [{ type: "text", text: `OCR failed: ${result.error}` }] };
      }

      const formatted = formatImageResult(result, `${input} \u2192 ${url}`, detail);
      return {
        content: [{ type: "text", text: formatted }],
      };
    }

    if (!isSupportedPath(input)) {
      return {
        content: [{
          type: "text",
          text: `Error: Unsupported format. Supported: ${[...SUPPORTED_IMAGE_FORMATS, ...SUPPORTED_PDF_FORMATS].join(", ")}, or a URL`,
        }],
      };
    }

    // Resolve relative to cwd from environment
    const cwd = process.cwd();
    const resolved = input.startsWith("/") || /^[A-Z]:[\\/]/i.test(input)
      ? input
      : join(cwd, input);

    if (!(await fileExists(resolved))) {
      return {
        content: [{ type: "text", text: `Error: File not found: ${resolved}` }],
      };
    }

    if (isPdf(resolved)) {
      const result = await runOcrOnPdf(resolved, pages, preprocess);
      if (result.error) {
        return { content: [{ type: "text", text: `OCR failed: ${result.error}` }] };
      }
      const formatted = formatPdfResult(result, resolved, detail);
      return { content: [{ type: "text", text: formatted }] };
    }

    const result = await runOcrOnImage(resolved, preprocess);
    if (result.error) {
      return { content: [{ type: "text", text: `OCR failed: ${result.error}` }] };
    }
    const formatted = formatImageResult(result, resolved, detail);
    return { content: [{ type: "text", text: formatted }] };
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    return {
      content: [{
        type: "text",
        text: `OCR failed: ${msg}\n\nMake sure Python dependencies are installed:\n- pip install rapidocr-onnxruntime\n- pip install pymupdf  (for PDF)\n- pip install Pillow numpy`,
      }],
    };
  } finally {
    if (tmpFile) {
      try { await unlink(tmpFile); } catch { /* ignore */ }
    }
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Fatal server error:", err);
  process.exit(1);
});
