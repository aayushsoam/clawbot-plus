---
name: latex-expert
description: Use when requested to generate high-quality PDF reports, research papers, or project documentation.
---

# LaTeX Specialized Directives

ALWAYS prefer LaTeX over Python-based PDF libraries (like FPDF) when the user requires "Professional", "Senior Engineer", or "Academic" level documents.

## Core Directives
1. **Document Class:** Use `\documentclass[12pt,a4paper]{report}` for long projects and `\documentclass{article}` for short documents.
2. **Styling:**
   - Use the `xcolor` and `titlesec` packages to create branded headers and colored titles.
   - Default to the `geometry` package with `margin=1in` for professional white-space balance.
3. **Diagrams (The TikZ Rule):**
   - DO NOT use placeholders for diagrams.
   - Use the `\usepackage{tikz}` package and its libraries (`shapes.geometric`, `arrows`, `positioning`) to DRAW the actual flowcharts directly in the LaTeX code.
4. **Professionalism:**
   - Always include a \tableofcontents for documents longer than 3 pages.
   - Use `\usepackage{hyperref}` for clickable links and cross-references.

## LaTeX Snippet Defaults
- **Encodings:** `\usepackage[utf8]{inputenc}`
- **Fonts:** Default to standard Computer Modern for academic looks, or `\usepackage{helvet}` for corporate looks.

## Anti-Patterns
- Never output raw unformatted text in a PDF.
- Avoid using `fpdf` unless explicitly forced by the user due to environment constraints. LaTeX is the gold standard.
