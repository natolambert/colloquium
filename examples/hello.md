---
title: "Hello Colloquium"
author: "Nathan Lambert"
date: "2026-02-22"
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

---

- Result A: **95.2%**
- Result B: **87.4%**
- Result C: **91.8%**

---

<!-- columns: 60/40 -->

## Asymmetric Columns (60/40)

This wider column has the main explanation text. The 60/40 split gives more room to the primary content while keeping a sidebar for supplementary info.

- Key finding one
- Key finding two

---

> "Supplementary details go in the narrower column."

Supporting points:
1. Evidence A
2. Evidence B

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

## Conclusions

1. Colloquium makes slide creation **fast** and **reproducible**
2. Full LaTeX math support for academic presentations
3. Git-friendly markdown source files
4. AI agents can create and modify presentations programmatically

<!-- notes: Mention future plans: citation support, MCP server, multiple themes -->

---

<!-- layout: title -->
<!-- class: highlight -->

# Thank You

Questions?

github.com/interconnects-ai/colloquium
