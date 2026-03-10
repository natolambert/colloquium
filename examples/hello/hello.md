---
title: "Hello Colloquium"
author: "Nathan Lambert"
date: "2026-02-22"
bibliography: refs.bib
figure_captions: true
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

![](mark.webp)

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

## Text Sizes

<span class="text-4xl">**text-4xl**</span> <span class="text-3xl">**text-3xl**</span> <span class="text-2xl">**text-2xl**</span>

<span class="text-xl">**text-xl** — Key takeaways</span>

<span class="text-lg">**text-lg** — Callouts and introductions</span>

<span class="text-base">**text-base** — Default body text</span>

<span class="text-sm">**text-sm** — Dense lists, supporting details</span>

<span class="text-xs">**text-xs** — Footnotes, references, fine print</span>

---

## LLM Conversation

```conversation
messages:
  - role: user
    content: "What is RLHF?"
  - role: assistant
    content: "**RLHF** (Reinforcement Learning from Human Feedback) is a technique for aligning language models with human preferences using reward models trained on human comparisons."
```

---

<!-- columns: 40/60 -->
<!-- size: small -->

## Conversation in Columns

- RLHF uses human preferences to train reward models
- The reward model scores LLM outputs
- PPO optimizes the policy against the reward

|||

```conversation
messages:
  - role: system
    content: "You are a helpful AI research assistant."
  - role: user
    content: "What is RLHF?"
  - role: assistant
    content: "**RLHF** is a technique for aligning language models with human preferences."
```

---

<!-- size: small -->

## Multi-Turn Conversation

```conversation
messages:
  - role: user
    content: "Can you explain the RLHF training pipeline?"
  - role: assistant
    content: "The RLHF pipeline has three main steps:\n1. **SFT** — supervised fine-tuning on demonstrations\n2. **Reward modeling** — train a reward model on human preferences\n3. **PPO** — optimize the policy against the reward model"
  - role: user
    content: "What's the role of KL divergence?"
  - role: assistant
    content: "The KL penalty prevents the policy from diverging too far from the SFT model. Without it, the model can exploit the reward model with degenerate outputs — this is called *reward hacking*."
```

---

<!-- columns: 1/1/1 -->
<!-- size: small -->

## Callout Boxes

```box
title: Accent
tone: accent
content: |
  High-contrast callout for key takeaways.

  - Great for punchy emphasis
  - Uses the deck accent color
```

|||

```box
title: Muted
tone: muted
content: |
  Softer card for supporting notes.

  - Good for side explanations
  - Uses the code/surface background
```

|||

```box
title: Surface
tone: surface
compact: true
content: |
  Neutral bordered panel for references or caveats.

  - Works when you want less visual weight
  - Keeps strong contrast with body text
```

---

## Title-only Box

```box
title: Core idea
tone: accent
```

---

## Key RLHF Papers

<!-- cite: christiano2017, ouyang2022 -->

The foundational work on RLHF [@christiano2017] introduced learning reward models from human comparisons.

InstructGPT [@ouyang2022] scaled this approach to large language models, demonstrating significant alignment improvements.

For a comprehensive overview, see [@lambert2024].

---

## The RLHF Loss

<!-- cite-right: christiano2017 -->

$$\mathcal{L}_{\text{RM}}(\theta) = -\mathbb{E}_{(x, y_w, y_l) \sim D}\left[\log \sigma\left(r_\theta(x, y_w) - r_\theta(x, y_l)\right)\right]$$

The reward model is trained with the Bradley-Terry preference model, where $y_w$ is the preferred response and $y_l$ is the rejected response.

---

<!-- size: small -->

## RLHF Timeline

- **2017**: Deep RL from human preferences [@christiano2017] and PPO [@schulman2017]
- **2019**: Fine-tuning LMs from human preferences [@ziegler2019]
- **2020**: Learning to summarize with human feedback [@stiennon2020]
- **2022**: InstructGPT [@ouyang2022] and Anthropic's HHH assistant [@bai2022]
- **2023**: DPO [@rafailov2023], IPO [@azar2023], Llama 2 [@touvron2023], Zephyr [@tunstall2023], Tülu 2 [@ivison2023], RLAIF [@lee2023]
- **2024**: KTO [@ethayarajh2024], AlpacaFarm [@dubois2024], and the RLHF Book [@lambert2024]

---

## Conclusions

1. Colloquium makes slide creation **fast** and **reproducible**
2. Full LaTeX math support for academic presentations
3. Git-friendly markdown source files
4. AI agents can create and modify presentations programmatically

<!-- notes: Mention future plans: citation support, MCP server, multiple themes -->

---

<!-- rows: 80/20 -->
## Thank You

Questions?

===

<!-- row-columns: 60/40 -->

|||

```builtwith
repo: natolambert/colloquium
```
