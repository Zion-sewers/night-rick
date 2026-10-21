---
name: project-intake
description: Project intake gate — structure, git hygiene, code quality, testing, deployment checklist. Use when onboarding a new project to ~/projects/.
---

# /project-intake

Mandatory checklist for any project entering ~/projects/. The lesson from a past project: 21K-line monolith, 4 backend copies, 42 MB of images. Never again.
See archived full protocol: `~/.Codex/rules/.archive-project-intake.md`

## Checklist (all must pass)
- [ ] No file >500 LOC, no function >50 LOC
- [ ] .gitignore covers: images, node_modules, __pycache__, .env, build artifacts
- [ ] No secrets in repo
- [ ] Linter + type checker configured
- [ ] Zero TODOs in production code
- [ ] Tests exist and pass
- [ ] No mocks (except platform stubs)
- [ ] Single deploy mechanism, documented
- [ ] README with: what, how to run, how to test

## Run: `~/.Codex/bin/codex-ci-review.sh --intake /path/to/project`
