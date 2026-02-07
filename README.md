# ADHD-Anim Library v1.0

A reusable CSS + JS animation system designed for ADHD-friendly micro-interactions. Drop into any project.

## Quick Start

```html
<link rel="stylesheet" href="adhd-anim-lib/adhd-anim.css">
<script src="adhd-anim-lib/adhd-anim.js"></script>
```

## HTML Attributes

| Attribute | Values | Description |
|---|---|---|
| `class="anim"` | — | Marks element for animation |
| `data-anim` | `pop`, `fade`, `slide-left`, `slide-right`, `slide-up`, `bounce`, `draw`, `glow`, `typewriter` | Animation type |
| `data-delay` | ms (e.g. `200`) | Delay before animation starts |
| `data-duration` | ms (e.g. `600`) | Custom animation duration |
| `data-stagger-group` | string | Group name for auto-staggered timing |
| `data-stagger-step` | ms (e.g. `120`) | Gap between each element in group |

## SVG Line Drawing

Add `class="anim-line"` to any SVG `<path>` or `<line>`. The library auto-calculates length and animates the draw.

## JS API

| Method | Description |
|---|---|
| `AdhdAnim.init()` | Re-scan DOM (call after adding dynamic content) |
| `AdhdAnim.trigger(el)` | Manually trigger one element |
| `AdhdAnim.triggerAll()` | Fire all animations immediately |
| `AdhdAnim.reset()` | Reset everything to pre-animation state |
| `AdhdAnim.staggerGroup(name)` | Trigger a specific stagger group |

## Design Principle

ADHD brains respond to micro-transactions — small, rewarding visual events. This library makes every element earn its place on screen by arriving with intention. No element just "appears." Everything pops, slides, draws, or glows into existence.
