---
trigger: always_on
---

# Always use the matching workspace skill

Before answering any chat message or running any command in this workspace:

1. Check the skills in `.agents/skills/`. Read each skill's `name` and `description`.
2. If the request fits a skill's description, load that skill and follow it before doing the work.
3. Say in one line which skill you used.

Current skills:
- `mind-margin-brand`: colors, fonts, frame layout, voice and editorial rules for the Mind & Margin channel. Use it for storyboards in `content/`, thumbnails, visuals, site styling and any channel-facing copy.

- `vao-rtx`: work on the user's Windows RTX workstation from a cloud session via remote-control bridge.

Claude Code uses the same skills from `.claude/skills/`. Keep both copies identical.
