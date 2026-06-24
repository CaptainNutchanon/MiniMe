const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const WIDTH = 1400;
const HEIGHT = 900;
const outputDirectory = __dirname;
const outSvg = path.join(outputDirectory, "minime_research_pipeline_human_evaluation.svg");
const outPng = path.join(outputDirectory, "minime_research_pipeline_human_evaluation.png");

const palette = {
  deepPond: "#123232",
  orange: "#f46a21",
  warmSand: "#f4efe4",
  paper: "#fffdf8",
  ink: "#193636",
  muted: "#60706d",
  line: "#6f7f7b",
  phaseA: "#2f7569",
  phaseAFill: "#e7f2ed",
  phaseB: "#326d8a",
  phaseBFill: "#e7f1f7",
  phaseC: "#54777c",
  phaseCFill: "#edf4f3",
  phaseD: "#b95b28",
  phaseDFill: "#faecdf",
};

const font =
  "'Noto Sans Thai', 'Leelawadee UI', 'Segoe UI', Arial, sans-serif";

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function textLines({
  x,
  y,
  lines,
  size = 12,
  lineHeight = 16,
  fill = palette.ink,
  weight = 400,
  anchor = "middle",
  className = "",
}) {
  const tspans = lines
    .map(
      (line, index) =>
        `<tspan x="${x}" dy="${index === 0 ? 0 : lineHeight}">${escapeXml(line)}</tspan>`
    )
    .join("");
  return `<text class="${className}" x="${x}" y="${y}" text-anchor="${anchor}" fill="${fill}" font-family="${font}" font-size="${size}" font-weight="${weight}">${tspans}</text>`;
}

function panel({ id, x, title, subtitle, color }) {
  return `
    <g id="phase-${id.toLowerCase()}">
      <rect x="${x}" y="104" width="326" height="752" rx="8" fill="${palette.paper}" stroke="#d8d2c5" stroke-width="1" filter="url(#shadow)"/>
      <rect x="${x}" y="104" width="326" height="66" rx="8" fill="${color}"/>
      <rect x="${x}" y="154" width="326" height="16" fill="${color}"/>
      <circle cx="${x + 29}" cy="137" r="16" fill="${palette.paper}" fill-opacity="0.96"/>
      <text x="${x + 29}" y="143" text-anchor="middle" fill="${color}" font-family="${font}" font-size="17" font-weight="800">${id}</text>
      ${textLines({ x: x + 58, y: 131, lines: [title], size: 15, fill: "#ffffff", weight: 700, anchor: "start" })}
      ${textLines({ x: x + 58, y: 151, lines: [subtitle], size: 10.5, fill: "#ffffff", weight: 400, anchor: "start" })}
    </g>`;
}

function nodeBox({
  id,
  x,
  y,
  width = 294,
  height,
  title,
  body,
  fill,
  stroke,
  compact = false,
}) {
  const titleSize = compact ? 11 : 13.2;
  const titleLineHeight = compact ? 13 : 16;
  const bodySize = compact ? 9.7 : 10.7;
  const bodyLineHeight = compact ? 14 : 15;
  const titleY = y + (compact ? 42 : 27);
  const bodyY = y + (title.length > 1 ? (compact ? 82 : 68) : compact ? 65 : 52);
  const tagWidth = compact ? 28 : 34;

  return `
    <g id="node-${id.toLowerCase()}">
      <rect x="${x}" y="${y}" width="${width}" height="${height}" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="1.2"/>
      <rect x="${x + 10}" y="${y + 10}" width="${tagWidth}" height="20" rx="4" fill="${stroke}"/>
      <text x="${x + 10 + tagWidth / 2}" y="${y + 24}" text-anchor="middle" fill="#ffffff" font-family="${font}" font-size="10.5" font-weight="800">${id}</text>
      ${textLines({
        x: x + width / 2,
        y: titleY,
        lines: title,
        size: titleSize,
        lineHeight: titleLineHeight,
        fill: palette.ink,
        weight: 750,
      })}
      <line x1="${x + 16}" y1="${bodyY - 14}" x2="${x + width - 16}" y2="${bodyY - 14}" stroke="${stroke}" stroke-opacity="0.24"/>
      ${textLines({
        x: x + width / 2,
        y: bodyY,
        lines: body,
        size: bodySize,
        lineHeight: bodyLineHeight,
        fill: palette.muted,
        weight: 450,
      })}
    </g>`;
}

function verticalArrow(x, y1, y2, color = palette.line) {
  return `<path d="M ${x} ${y1} L ${x} ${y2}" fill="none" stroke="${color}" stroke-width="1.7" marker-end="url(#arrow-solid)"/>`;
}

function dottedConnector({ d, label, labelX, labelY, rotate = 0 }) {
  return `
    <g class="cross-phase-connector">
      <path d="${d}" fill="none" stroke="${palette.orange}" stroke-width="2" stroke-dasharray="5 5" marker-end="url(#arrow-dotted)"/>
      <text x="${labelX}" y="${labelY}" text-anchor="middle" fill="${palette.orange}" font-family="${font}" font-size="9.5" font-weight="700" transform="rotate(${rotate} ${labelX} ${labelY})">${escapeXml(label)}</text>
    </g>`;
}

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-labelledby="diagram-title diagram-desc">
  <title id="diagram-title">MiniMe research pipeline and human evaluation architecture</title>
  <desc id="diagram-desc">Four-phase research architecture from Instagram chat export preparation through Qwen 3.5 LoRA fine-tuning, local inference safety, and automatic plus human evaluation.</desc>
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#123232" flood-opacity="0.10"/>
    </filter>
    <marker id="arrow-solid" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 1 1 L 8 5 L 1 9 Z" fill="${palette.line}"/>
    </marker>
    <marker id="arrow-dotted" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 1 1 L 8 5 L 1 9 Z" fill="${palette.orange}"/>
    </marker>
  </defs>

  <rect width="${WIDTH}" height="${HEIGHT}" fill="${palette.warmSand}"/>
  <rect width="${WIDTH}" height="80" fill="${palette.deepPond}"/>
  <rect y="76" width="${WIDTH}" height="4" fill="${palette.orange}"/>
  ${textLines({ x: 34, y: 34, lines: ["MiniMe Research Pipeline"], size: 25, fill: "#ffffff", weight: 800, anchor: "start" })}
  ${textLines({ x: 34, y: 60, lines: ["Dataset preparation, LoRA fine-tuning, guarded local inference, and research evaluation"], size: 12.5, fill: "#dce8e4", weight: 400, anchor: "start" })}
  <text x="1365" y="48" text-anchor="end" fill="${palette.orange}" font-family="${font}" font-size="14" font-weight="800">Qwen3.5-9B + LoRA</text>

  ${panel({ id: "A", x: 24, title: "Dataset Preparation", subtitle: "Raw chat to chronological splits", color: palette.phaseA })}
  ${panel({ id: "B", x: 366, title: "LoRA Fine-Tuning", subtitle: "Parameter-efficient persona learning", color: palette.phaseB })}
  ${panel({ id: "C", x: 708, title: "Runtime & Safety", subtitle: "Local inference with a light guard", color: palette.phaseC })}
  ${panel({ id: "D", x: 1050, title: "Research Evaluation", subtitle: "Automatic, blind A/B, and live chat", color: palette.phaseD })}

  <g id="dataset-preparation-nodes">
    ${nodeBox({
      id: "A1", x: 40, y: 190, height: 126,
      title: ["Raw Data Ingestion"],
      body: ["Instagram chat JSON export", "Thai mojibake recovery:", "latin1 -> UTF-8 re-decoding"],
      fill: palette.phaseAFill, stroke: palette.phaseA,
    })}
    ${verticalArrow(187, 316, 340, palette.phaseA)}
    ${nodeBox({
      id: "A2", x: 40, y: 344, height: 126,
      title: ["Text Preprocessing", "& Cleaning"],
      body: ["scripts/04_clean_and_filter.py", "Remove calls, links, reactions,", "shared posts, and system notices"],
      fill: palette.phaseAFill, stroke: palette.phaseA,
    })}
    ${verticalArrow(187, 470, 494, palette.phaseA)}
    ${nodeBox({
      id: "A3", x: 40, y: 498, height: 126,
      title: ["Session Construction", "& Message Merging"],
      body: ["scripts/05_build_jsonl.py", "Merge consecutive same-sender turns", "1-hour idle gap; start with User"],
      fill: palette.phaseAFill, stroke: palette.phaseA,
    })}
    ${verticalArrow(187, 624, 648, palette.phaseA)}
    ${nodeBox({
      id: "A4", x: 40, y: 652, height: 170,
      title: ["Chronological Data Split"],
      body: ["scripts/06_split_train_val.py", "Source-preserved chronological split", "90% Train / 10% Validation", "Sources with <10 sessions: train only", "Future-like validation; reduced leakage"],
      fill: palette.phaseAFill, stroke: palette.phaseA,
    })}
  </g>

  <g id="lora-fine-tuning-nodes">
    ${nodeBox({
      id: "B1", x: 382, y: 190, height: 126,
      title: ["Base Model Loading"],
      body: ["Qwen/Qwen3.5-9B via Unsloth", "4-bit quantization", "Reduced VRAM footprint"],
      fill: palette.phaseBFill, stroke: palette.phaseB,
    })}
    ${verticalArrow(529, 316, 340, palette.phaseB)}
    ${nodeBox({
      id: "B2", x: 382, y: 344, height: 126,
      title: ["Parameter-Efficient", "Fine-Tuning"],
      body: ["LoRA: rank 16, alpha 32, dropout 0.05", "Q/K/V/O + gate/up/down projections", "Gradient checkpointing"],
      fill: palette.phaseBFill, stroke: palette.phaseB,
    })}
    ${verticalArrow(529, 470, 494, palette.phaseB)}
    ${nodeBox({
      id: "B3", x: 382, y: 498, height: 126,
      title: ["Hybrid Training Data"],
      body: ["Real Instagram chat train split", "+ curated general-chat examples", "CURATED_REPEAT = 2"],
      fill: palette.phaseBFill, stroke: palette.phaseB,
    })}
    ${verticalArrow(529, 624, 648, palette.phaseB)}
    ${nodeBox({
      id: "B4", x: 382, y: 652, height: 170,
      title: ["Optimization Strategy"],
      body: ["Last assistant-only token loss", "Context remains visible; prior tokens masked", "2 epochs; evaluate/save every 100 steps", "Best checkpoint selected by eval_loss", "Export LoRA adapter weights"],
      fill: palette.phaseBFill, stroke: palette.phaseB,
    })}
  </g>

  <g id="runtime-and-safety-nodes">
    ${nodeBox({
      id: "C1", x: 724, y: 190, height: 126,
      title: ["Local FastAPI Backend"],
      body: ["Base model + LoRA adapter", "Local GPU inference", "Server-Sent Events (SSE) streaming"],
      fill: palette.phaseCFill, stroke: palette.phaseC,
    })}
    ${verticalArrow(871, 316, 340, palette.phaseC)}
    ${nodeBox({
      id: "C2", x: 724, y: 344, height: 126,
      title: ["Context Management"],
      body: ["Current user message + recent history", "MAX_HISTORY_MESSAGES = 6", "System prompt guides short Thai chat"],
      fill: palette.phaseCFill, stroke: palette.phaseC,
    })}
    ${verticalArrow(871, 470, 494, palette.phaseC)}
    ${nodeBox({
      id: "C3", x: 724, y: 498, height: 126,
      title: ["Post-Processing Light Guard"],
      body: ["Reject CJK, malformed tokens, long numbers", "Emoji-only or >=3 emoji; max 70 chars", "Block artifacts: ไอแพน / คุณายาว"],
      fill: palette.phaseCFill, stroke: palette.phaseC,
    })}
    ${verticalArrow(871, 624, 648, palette.phaseC)}
    ${nodeBox({
      id: "C4", x: 724, y: 652, height: 170,
      title: ["Identity Policy", "& Active Retry"],
      body: ["Garbage output: retry up to 2 times", "Identity drift: add a targeted system hint", "then perform one identity retry", "Normalize known identity variants", "Deterministic identity fallback if needed"],
      fill: palette.phaseCFill, stroke: palette.phaseC,
    })}
  </g>

  <g id="research-evaluation-nodes">
    ${nodeBox({
      id: "D1", x: 1066, y: 190, width: 294, height: 140,
      title: ["Multi-Category Prompt Set"],
      body: ["66 held-out prompts", "8 persona and conversation categories", "No audited verbatim overlap", "normalized text >=10 characters", "Baseline vs fine-tuned comparison"],
      fill: palette.phaseDFill, stroke: palette.phaseD,
    })}

    <path d="M 1213 330 L 1213 356 L 1136 356 L 1136 378" fill="none" stroke="${palette.phaseD}" stroke-width="1.7" marker-end="url(#arrow-solid)"/>
    <path d="M 1213 356 L 1284 356 L 1284 378" fill="none" stroke="${palette.phaseD}" stroke-width="1.7" marker-end="url(#arrow-solid)"/>
    <circle cx="1213" cy="356" r="4" fill="${palette.orange}"/>

    ${nodeBox({
      id: "D3", x: 1066, y: 382, width: 140, height: 438,
      title: ["Human-Centric", "Evaluation"],
      body: ["BLIND HUMAN A/B", "8 raters", "Persona similarity", "Style similarity", "Context relevance", "", "Exact Wilcoxon", "signed-rank test", "Krippendorff's alpha", "agreement", "", "LIVE CHAT", "22 sessions", "Acceptable response", "rate"],
      fill: "#fff3e9", stroke: palette.phaseD, compact: true,
    })}
    ${nodeBox({
      id: "D2", x: 1214, y: 382, width: 146, height: 438,
      title: ["Automatic", "Metrics"],
      body: ["Distinct-1 / 2", "character-level", "", "Guard rejection rate", "Average latency", "Output artifacts", "Identity accuracy", "Generic reply rate", "", "Reply length ratio", "vs real Kappitan", "validation replies", "", "Training / eval loss", "and overfitting gap"],
      fill: "#eef4f8", stroke: palette.phaseB, compact: true,
    })}
  </g>

  <g id="cross-phase-data-flow">
    ${dottedConnector({ d: "M 334 737 L 350 737 L 350 561 L 378 561", label: "TRAIN DATA", labelX: 351, labelY: 649, rotate: -90 })}
    ${dottedConnector({ d: "M 676 737 L 692 737 L 692 253 L 720 253", label: "BEST LoRA", labelX: 693, labelY: 490, rotate: -90 })}
    ${dottedConnector({ d: "M 1018 737 L 1034 737 L 1034 700 L 1062 700", label: "LIVE REPLIES", labelX: 1034, labelY: 714, rotate: -90 })}
  </g>

  <g id="research-summary-footer">
    <line x1="24" y1="876" x2="1376" y2="876" stroke="#d4ccbc"/>
    <text x="700" y="892" text-anchor="middle" fill="${palette.muted}" font-family="${font}" font-size="10.5" font-weight="600">66 held-out prompts  |  8 human raters  |  22 live-chat sessions  |  exact Wilcoxon testing  |  agreement analysis</text>
  </g>
</svg>`;

async function render() {
  const normalizedSvg = svg.replace(/[ \t]+$/gm, "");
  fs.writeFileSync(outSvg, normalizedSvg, "utf8");
  await sharp(Buffer.from(normalizedSvg))
    .flatten({ background: palette.warmSand })
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toFile(outPng);
  console.log(`SVG: ${outSvg}`);
  console.log(`PNG: ${outPng}`);
}

render().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
