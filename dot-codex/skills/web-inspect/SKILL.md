---
name: web-inspect
description: "/web-inspect"
---

# /web-inspect

Headed browser automation via `playwright-cli` with isolated profile. No MCP overhead.

## When to Use

- Explore/test your own dev/stage apps (a dashboard app, a Figma plugin preview, a rendering pipeline preview)
- Debug UI issues, fill forms, validate flows, take screenshots
- Generate or fix E2E tests from observed browser behavior

## When NOT to Use

- Browsing arbitrary external sites (use Perplexity MCP or WebSearch instead)
- Running full Playwright test suites (use `bunx playwright test` directly)
- Simple URL fetching for content extraction (use WebFetch tool)

## Quick Start

```bash
# Always use headed mode + isolated profile (never your personal browser)
playwright-cli open https://localhost:3000 --browser=chrome --persistent --profile=.pw-userdata/dev

# Interact via accessibility refs from snapshots
playwright-cli snapshot                    # Get page structure with element refs
playwright-cli click e15                   # Click by ref
playwright-cli fill e5 "user@example.com"  # Fill input
playwright-cli screenshot --filename=debug.png

# Named sessions for longer workflows
playwright-cli -s=<project> open https://localhost:3002/intelligence --persistent --profile=.pw-userdata/<project>
playwright-cli -s=<project> snapshot
playwright-cli -s=<project> close

# Cleanup
playwright-cli close          # Close default session
playwright-cli close-all      # Close all sessions
playwright-cli kill-all       # Force-kill all browser processes
```

## Project URLs (Allow-List)

Only automate these domains:

| Project | Dev URL | Stage URL |
|---------|---------|-----------|
| `<project-a>` | `localhost:3002` | `<project-a>-stage.vercel.app` |
| `<figma-plugin-project>` | Figma plugin (localhost:1234) | N/A |
| `<render-preview-project>` | `localhost:3000` | N/A |

For external sites, use Perplexity MCP or WebSearch.

## Profiles

Each project gets an isolated browser profile. Cookies, localStorage, and auth persist between sessions without touching your personal browser.

```
.pw-userdata/
  <project-a>/  # project-a dashboard auth, cookies
  figma/        # Figma plugin preview
  <project-b>/  # project-b local preview
  dev/          # General dev/test profile
```

Add `.pw-userdata/` to `.gitignore` (and `.claudeignore` if you still use Claude Code).

## Agent Mode Workflow (E2E Loop)

When asked to explore and fix UI issues, follow this loop:

1. **Open** the target page in headed mode with project profile
2. **Snapshot** to get accessibility tree with element refs
3. **Interact** using refs (click, fill, select, press)
4. **Observe** results via snapshot or screenshot
5. **Diagnose** failures from console/network output
6. **Fix** the code based on observations
7. **Verify** by re-running the interaction
8. **Stop** after 3 iterations or when green

```bash
# Example: debug a project's intelligence dashboard
playwright-cli -s=<project> open http://localhost:3002/intelligence --browser=chrome --persistent --profile=.pw-userdata/<project>
playwright-cli -s=<project> snapshot
# ... interact, observe, diagnose ...
playwright-cli -s=<project> console     # Check for JS errors
playwright-cli -s=<project> network     # Check API calls
playwright-cli -s=<project> screenshot --filename=debug-<project>.png
playwright-cli -s=<project> close
```

## Safety Rules

- **Isolated profile only** — never use `--profile` pointing to `~/.config/google-chrome/` or similar
- **Domain allow-list** — only automate project URLs above; external sites go through Perplexity/WebSearch
- **Max 3 iterations** — if the fix isn't working after 3 explore-fix cycles, stop and report
- **Close sessions** — always close browser sessions when done; stale processes waste memory
- **No credentials in commands** — use `state-load auth.json` for pre-saved auth, not inline passwords

## Full Command Reference

For the complete command reference (core, keyboard, mouse, tabs, storage, network, devtools, tracing, video), see:
`~/.codex/skills/playwright-cli/SKILL.md`

Only load that file when you need a specific command not listed above.
