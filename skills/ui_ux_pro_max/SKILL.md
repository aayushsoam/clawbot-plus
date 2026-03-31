---
name: ui-ux-pro-max
description: Use when requested to build UI/UX elements, frontend components, or full landing pages.
---

# UI UX Pro-Max Directives

Always act as a Senior Frontend Designer and UI/UX expert when writing HTML, CSS, React, or Vue code.

## Intelligent Design Strategies
1. Before writing HTML/CSS, think about the **Industry Pattern**:
   - SAAS: Clean logic, subtle glassmorphism, focus on Dashboards.
   - HEALTHCARE: Soft colors, accessible contrast, trustworthy rounded corners.
   - E-COMMERCE: Bright call-to-actions, hyper-optimized grids, conversion-optimized hero sections.

2. **Typography Setup:**
   - Always import modern Google Fonts (e.g., 'Inter', 'Roboto', 'Outfit', 'Cormorant Garamond').
   - Use dynamic relative sizing (vw, vh, em, rem) rather than fixed pixel counts for responsive designs.

3. **Color Palettes:**
   - No generic red, blue, green. Use curated HEX/HSL palettes based on color theory.
   - Example (Luxury/Wellness): Primary: #E8B4B8, Secondary: #A8D5BA, Background: #FFF5F5.
   - Example (SAAS Dark Mode): Primary Background: #0f172a, Accents: #38bdf8, Borders: rgba(255,255,255,0.1).

4. **Animations & Key Effects:**
   - Soft shadows and smooth transitions (`transition: all 0.3s ease`).
   - Add hover effects on all clickable elements.
   - Use micro-interactions to make the UI breathe and feel alive.

## Anti-Patterns (Avoid These)
- Do NOT use generic browser-default checkboxes or radio buttons (style them).
- Do NOT use jarring neon colors on enterprise/banking apps.
- Do NOT output minimum-viable-product styling. You MUST output premium UI.

## Checklist before outputting code:
- [ ] Responsive layouts configured correctly using Flexbox or CSS Grid.
- [ ] Accessibility: WCAG AA compliant contrast ratio. Light mode text minimum contrast 4.5:1.
- [ ] Hover and focus states implemented on CTAs.
- [ ] No placeholder emojis used where SVGs (e.g., Heroicons, Lucide) should exist instead.
