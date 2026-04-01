---
title: Animation Examples
author: Colloquium
---

# Animations in Colloquium

Incremental reveal for slides

---

## Bullet-by-Bullet Reveal
<!-- animate: bullets -->

- First, we define the problem
- Then, we propose a solution
- Next, we evaluate the results
- Finally, we draw conclusions

---

## Block-by-Block Reveal
<!-- animate: blocks -->

This paragraph appears first.

This paragraph appears second.

This paragraph appears third.

---

## Step Markers
<!-- size: large -->

This content is visible immediately.

<!-- step -->

This paragraph appears on the first click.

<!-- step -->

And this appears on the second click.

---

## Composing Animate + Steps
<!-- animate: bullets -->

- Point A
- Point B
- Point C

<!-- step -->

After revealing all bullets, this conclusion appears.

---

## Ordered Lists Too
<!-- animate: items -->

1. Gather requirements
2. Design the system
3. Implement the solution
4. Write tests
5. Ship it

---

## Blocks with Mixed Content
<!-- animate: blocks -->

Here is an introductory paragraph.

- A list of items
- That appears as one block

```python
# Code appears as another block
def hello():
    print("world")
```

A final paragraph to wrap up.

---

## Steps in Columns
<!-- columns: 2 -->

### Left Column

Content always visible on the left.

|||

### Right Column

Right column content.

<!-- step -->

More right column content revealed on click.

---

## No Animation

This slide has no animation directives.

All content appears at once, just like before.

- Bullet one
- Bullet two
- Bullet three
