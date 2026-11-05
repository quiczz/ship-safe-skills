---
name: awesome-design-md
description: Pick and apply a brand-style DESIGN.md (colors, type, spacing, components) from a local library of about 84 real-world design systems such as Apple, Stripe, Linear, Airbnb. Use when asked to make a UI "in the style of" a known product, set up a DESIGN.md for a project, or choose a visual direction from references.
---

# Awesome DESIGN.md

A `DESIGN.md` is a plain Markdown file that describes a visual system (atmosphere, color tokens, typography, spacing, component styling, do and don't) so a coding agent can build UI that matches it. This skill gives you a library of them, collected by the open-source project VoltAgent/awesome-design-md (MIT), installed next to this file in `design-md/<brand>/DESIGN.md`.

## Procedure

1. **Find a match.** List the library once with `ls design-md/` (the folder names are brand slugs). If the user named a brand, check for it and for close neighbours. If they described a mood ("calm, dense, developer-focused"), shortlist 2 or 3 brands and say why.
2. **Load only the chosen file(s).** Read `design-md/<slug>/DESIGN.md`. Never load the whole library; each file is large.
3. **Apply it, don't copy it.** Use its tokens and patterns as the style guide for the user's own product. If the user wants it to persist, copy it to the project root as `DESIGN.md` and add one line to the project's `CLAUDE.md` or `AGENTS.md`: "Follow DESIGN.md for all UI decisions."
4. **Combine thoughtfully.** One primary reference per product. You may borrow a single idea (for example Stripe's gradients) from a second, but say so.
5. **Check your work.** After building, compare against the file's color, type, and spacing tokens and list any deliberate deviations.

## Rules

- These files describe public visual style for reference. Do not copy logos, proprietary images, brand names, or trademarks, and do not imply the user's product is affiliated with the brand.
- If the library folder is missing, the install did not complete: tell the user to run `python3 install.py install awesome-design-md` from the skills pack, or get the files from https://github.com/VoltAgent/awesome-design-md.
- Pair with a general UI skill for layout, accessibility, and interaction details; a DESIGN.md covers look and feel, not behaviour.
