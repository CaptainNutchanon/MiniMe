const fs = require("fs");
const sharp = require("sharp");

const outPng = "D:/GitHub/MiniMe/diagrams/minime_research_pipeline_human_evaluation.png";
const outSvg = "D:/GitHub/MiniMe/diagrams/minime_research_pipeline_human_evaluation.svg";

const font =
  "&quot;Anthropic Sans&quot;, -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, sans-serif";

const textStyle = (fill, size, weight = 400) =>
  `fill:${fill};stroke:none;font-family:${font};font-size:${size}px;font-weight:${weight};text-anchor:middle;dominant-baseline:central`;

const rectStyle = (fill, stroke) =>
  `fill:${fill};stroke:${stroke};stroke-width:0.5px;stroke-linecap:butt;stroke-linejoin:miter`;

const lineStyle =
  "fill:none;stroke:rgb(115, 114, 108);stroke-width:1.5px;stroke-linecap:butt;stroke-linejoin:miter";

function box({ y, fill, stroke, title, subtitle, titleFill, subtitleFill, h = 56 }) {
  const titleY = y + (h === 30 ? 15 : 22);
  const subtitleY = y + 40;
  const subtitleText =
    h === 30
      ? ""
      : `<text x="340" y="${subtitleY}" text-anchor="middle" dominant-baseline="central" style="${textStyle(
          subtitleFill,
          12,
          400
        )}">${subtitle}</text>`;

  return `
<g>
<rect x="215" y="${y}" width="250" height="${h}" rx="8" stroke-width="0.5" style="${rectStyle(
    fill,
    stroke
  )}"/>
<text x="340" y="${titleY}" text-anchor="middle" dominant-baseline="central" style="${textStyle(
    titleFill,
    14,
    500
  )}">${title}</text>
${subtitleText}
</g>`;
}

function arrow(y1, y2) {
  return `<line x1="340" y1="${y1}" x2="340" y2="${y2}" marker-end="url(#arrow)" style="${lineStyle}"/>`;
}

const svg = `<svg width="100%" viewBox="0 0 680 830" role="img" xmlns="http://www.w3.org/2000/svg">
<title>Research pipeline diagram</title>
<desc>Flowchart showing the research pipeline from Instagram direct messages to a web application with a trained LoRA adapter.</desc>
<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</marker>
</defs>

${box({
  y: 30,
  fill: "rgb(230, 241, 251)",
  stroke: "rgb(24, 95, 165)",
  title: "Data collection",
  subtitle: "Messenger / Instagram chat corpus",
  titleFill: "rgb(12, 68, 124)",
  subtitleFill: "rgb(24, 95, 165)",
})}
${arrow(86, 120)}

${box({
  y: 120,
  fill: "rgb(225, 245, 238)",
  stroke: "rgb(15, 110, 86)",
  title: "Data preprocessing",
  subtitle: "Clean, filter, fix encoding",
  titleFill: "rgb(8, 80, 65)",
  subtitleFill: "rgb(15, 110, 86)",
})}
${arrow(176, 210)}

${box({
  y: 210,
  fill: "rgb(225, 245, 238)",
  stroke: "rgb(15, 110, 86)",
  title: "Emotion tagging",
  subtitle: "Emoji → emotion label",
  titleFill: "rgb(8, 80, 65)",
  subtitleFill: "rgb(15, 110, 86)",
})}
${arrow(266, 300)}

${box({
  y: 300,
  fill: "rgb(225, 245, 238)",
  stroke: "rgb(15, 110, 86)",
  title: "Dataset split",
  subtitle: "Train 95% / Validation 5%",
  titleFill: "rgb(8, 80, 65)",
  subtitleFill: "rgb(15, 110, 86)",
})}
${arrow(356, 390)}

${box({
  y: 390,
  fill: "rgb(238, 237, 254)",
  stroke: "rgb(83, 74, 183)",
  title: "Fine-tuning",
  subtitle: "Typhoon2 + LoRA + Unsloth",
  titleFill: "rgb(60, 52, 137)",
  subtitleFill: "rgb(83, 74, 183)",
})}
${arrow(446, 480)}

${box({
  y: 480,
  fill: "rgb(225, 245, 238)",
  stroke: "rgb(15, 110, 86)",
  title: "LoRA adapter output",
  subtitle: "Trained adapter weights",
  titleFill: "rgb(8, 80, 65)",
  subtitleFill: "rgb(15, 110, 86)",
})}
${arrow(536, 570)}

${box({
  y: 570,
  fill: "rgb(230, 241, 251)",
  stroke: "rgb(24, 95, 165)",
  title: "Inference backend",
  subtitle: "Base model + LoRA adapter",
  titleFill: "rgb(12, 68, 124)",
  subtitleFill: "rgb(24, 95, 165)",
})}
${arrow(626, 660)}

${box({
  y: 660,
  fill: "rgb(250, 236, 231)",
  stroke: "rgb(153, 60, 29)",
  title: "Web application",
  subtitle: "Captain AI chatbot interface",
  titleFill: "rgb(113, 43, 19)",
  subtitleFill: "rgb(153, 60, 29)",
})}
${arrow(716, 750)}

${box({
  y: 750,
  fill: "rgb(250, 238, 218)",
  stroke: "rgb(133, 79, 11)",
  title: "Evaluation",
  subtitle: "human evaluation",
  titleFill: "rgb(99, 56, 6)",
  subtitleFill: "rgb(133, 79, 11)",
})}

<text x="90" y="210" text-anchor="middle" dominant-baseline="central" style="${textStyle(
  "rgb(61, 61, 58)",
  12,
  400
)}">Pre-</text>
<text x="90" y="224" text-anchor="middle" dominant-baseline="central" style="${textStyle(
  "rgb(61, 61, 58)",
  12,
  400
)}">processing</text>
<text x="90" y="238" text-anchor="middle" dominant-baseline="central" style="${textStyle(
  "rgb(61, 61, 58)",
  12,
  400
)}">pipeline</text>
<line x1="128" y1="228" x2="213" y2="228" style="fill:none;stroke:rgb(115, 114, 108);stroke-width:0.5px;stroke-dasharray:4px, 3px;stroke-linecap:butt;stroke-linejoin:miter"/>

<text x="568" y="412" text-anchor="middle" dominant-baseline="central" style="${textStyle(
  "rgb(61, 61, 58)",
  12,
  400
)}">LoRA adapter</text>
<text x="568" y="426" text-anchor="middle" dominant-baseline="central" style="${textStyle(
  "rgb(61, 61, 58)",
  12,
  400
)}">~134 MB</text>
<line x1="550" y1="418" x2="467" y2="418" style="fill:none;stroke:rgb(115, 114, 108);stroke-width:0.5px;stroke-dasharray:4px, 3px;stroke-linecap:butt;stroke-linejoin:miter"/>
</svg>`;

fs.writeFileSync(outSvg, svg, "utf8");

sharp(Buffer.from(svg)).flatten({ background: "#ffffff" }).png().toFile(outPng).then(() => {
  console.log(outPng);
});
