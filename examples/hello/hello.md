---
title: "Hello Colloquium"
author: "Nathan Lambert"
date: "2026-02-22"
fonts:
  heading: "Rubik"
  body: "Poppins"
footer:
  left: "logo.png"
  center: ""
  right: "auto"
custom_css: |
  :root {
    --colloquium-bg: #E3EEEA;
    --colloquium-text: #0B1A14;
    --colloquium-heading: #0B1A14;
    --colloquium-accent: #4AA691;
    --colloquium-link: #4AA691;
    --colloquium-progress-fill: #4AA691;
    --colloquium-code-bg: #d4e4dd;
    --colloquium-muted: #3a5a4a;
    --colloquium-border: #b8d4c8;
    --colloquium-progress-bg: #b8d4c8;
  }
  .slide--section-break { background: #4AA691; }
---

# Hello Colloquium

A demo presentation with math, code, and figures

Nathan Lambert

2026-02-22

---

## What is Colloquium?

- Agent-native slide creation tool for research talks
- Markdown-based and git-friendly
- AI agents can drive it programmatically
- Single self-contained HTML output

---

## LaTeX Math Support

The loss function for RLHF with a KL penalty:

$$\mathcal{L}(\theta) = -\mathbb{E}_{x \sim D}\left[\log \sigma\left(r_\theta(x_w) - r_\theta(x_l)\right)\right]$$

Inline math works too: $\nabla_\theta J(\theta) = \mathbb{E}_{\pi_\theta}[R \cdot \nabla_\theta \log \pi_\theta(a|s)]$

---

## Code Highlighting

```python
from colloquium import Deck

deck = Deck(title="My Talk", author="Researcher")
deck.add_title_slide(subtitle="A research presentation")
deck.add_slide(
    title="Key Results",
    content="Our method achieves **state-of-the-art** performance.",
)
deck.build("output/")
```

---

<!-- columns: 2 -->

## Two Equal Columns

- Point one
- Point two
- Point three

|||

- Result A: **95.2%**
- Result B: **87.4%**
- Result C: **91.8%**

---

<!-- columns: 60/40 -->

## Asymmetric Columns (60/40)

This wider column has the main explanation text. The 60/40 split gives more room to the primary content while keeping a sidebar for supplementary info.

- Key finding one
- Key finding two

|||

> "Supplementary details go in the narrower column."

Supporting points:
1. Evidence A
2. Evidence B

---

<!-- align: center -->
<!-- valign: center -->

## Centered Image

![Colloquium wordmark](mark.webp)

---

<!-- columns: 40/60 -->

## Image with Text

![Colloquium wordmark](mark.webp)

|||

Colloquium supports images in any layout. Here the wordmark sits in the wider column alongside explanatory text.

Images auto-scale to fit their container while maintaining aspect ratio.

---

<!-- layout: section-break -->

## Key Results

---

## Experimental Results

| Model | Accuracy | F1 Score | Training Time |
|-------|----------|----------|---------------|
| Baseline | 82.1% | 79.3% | 2h |
| Ours (small) | 91.4% | 89.7% | 4h |
| Ours (large) | **95.2%** | **93.8%** | 12h |

> "The results demonstrate significant improvements across all metrics."

---

<!-- align: center -->
<!-- size: large -->

## Centered & Large Text

This slide uses the `align` and `size` directives to center all text and increase the font size.

Great for emphasis slides.

---

<!-- title: center -->

## Vertically Centered Title

All content on this slide is vertically centered, like a title slide but with `##` heading style.

---

## Training Performance

```chart
type: line
data:
  labels: [10K, 50K, 100K, 250K, 500K, 1M]
  datasets:
    - label: Accuracy
      data: [62.1, 74.5, 82.3, 89.1, 93.4, 95.2]
      color: "#4AA691"
    - label: F1 Score
      data: [58.3, 71.2, 79.8, 87.4, 91.9, 93.8]
      color: "#0B1A14"
options:
  scales:
    x:
      grid: {display: false}
    y:
      grid: {display: false}
```

---

## Resource Usage

```chart
type: bar
data:
  labels: [Small, Medium, Large, XL]
  datasets:
    - label: Training
      data: [4, 12, 48, 120]
      color: "#4AA691"
    - label: Evaluation
      data: [1, 3, 8, 20]
      color: "#0B1A14"
options:
  scales:
    x:
      grid: {display: false}
    y:
      grid: {display: false}
```

---

## Conclusions

1. Colloquium makes slide creation **fast** and **reproducible**
2. Full LaTeX math support for academic presentations
3. Git-friendly markdown source files
4. AI agents can create and modify presentations programmatically

<!-- notes: Mention future plans: citation support, MCP server, multiple themes -->

---

<!-- layout: title -->

# Thank You

Questions?

github.com/interconnects-ai/colloquium
