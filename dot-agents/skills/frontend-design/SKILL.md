---
name: frontend-design
description: Injects anti-slop UI design constraints into the session. Activate at the start of any frontend work to prevent distributional convergence to AI-generated visual noise.
effort: low
---

## Purpose

Activate before writing any frontend code. Injects the house UI design standard into the session so you don't need to re-prompt it every time.

## What This Enforces

You are now operating under the house UI standard. All UI output must comply with `~/.Codex/rules/anti-slop-ui.md`. Summary:

**Palette — use one of these, no exceptions:**
- Catppuccin Mocha (dark): base #1e1e2e, text #cdd6f4, blue #89b4fa, green #a6e3a1, red #f38ba8
- Nord (light/neutral): nord0 #2e3440, nord4 #d8dee9, nord8 #88c0d0, nord14 #a3be8c

**Never:**
- White (#fff / bg-white) as primary background without dark mode
- Purple gradients (from-purple-500, #7c3aed, #6366f1)
- Inter or sans-serif as the only font declaration
- More than 3 distinct border-radius values per component
- z-index above 9999
- !important outside reset CSS
- Color values not in the approved palette without a comment explaining why

**Colors must be semantic:**
- Blue = primary action / interactive
- Green = success / pass / health
- Yellow = warning / degraded
- Red = error / fail / danger
- Surface tones = hierarchy only

**Contrast check mandatory before any text/background pair:**
- Body text: >=4.5:1 (WCAG AA)
- Large text (>=24px): >=3:1

**Typography:**
- Body: clamp(1rem, 2.5vw, 1.25rem), line-height 1.5-1.7
- Headings: line-height 1.1-1.2, letter-spacing 0.01em body / 0.05em caps

**Layout:**
- Grid for 2D, flexbox for 1D
- gap not margin between siblings
- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64px

## When Done

After any frontend implementation, run /review with Layer 5 (accessibility/UX) and verify:
- [ ] Palette is Catppuccin or Nord (or documented exception)
- [ ] All text contrast ratios verified
- [ ] Dark mode is first-class
- [ ] No purple gradients
- [ ] No white primary backgrounds
