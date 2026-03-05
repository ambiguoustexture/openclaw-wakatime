# Community Submission Kit

Published package:

- npm: `@ambiguoustr/openclaw-wakatime@0.9.9`
- repo: `https://github.com/ambiguoustexture/openclaw-wakatime`
- install: `openclaw plugins install @ambiguoustr/openclaw-wakatime`

## OpenClaw Community Listing

Reference:

- `https://docs.openclaw.ai/plugins/community`
- Target file: `https://github.com/openclaw/openclaw/blob/main/docs/plugins/community.md`

### Listing entry (copy/paste)

```md
- **WakaTime** — Track OpenClaw messages, commands, sessions, and tool usage in WakaTime.
  npm: `@ambiguoustr/openclaw-wakatime`
  repo: `https://github.com/ambiguoustexture/openclaw-wakatime`
  install: `openclaw plugins install @ambiguoustr/openclaw-wakatime`
```

### PR title

```text
docs(plugins): add @ambiguoustr/openclaw-wakatime to community plugins
```

### PR body

```md
## Summary

Add `@ambiguoustr/openclaw-wakatime` to the OpenClaw community plugins list.

## Plugin

- Name: WakaTime
- npm: `@ambiguoustr/openclaw-wakatime`
- repo: `https://github.com/ambiguoustexture/openclaw-wakatime`
- install: `openclaw plugins install @ambiguoustr/openclaw-wakatime`

## Why

This plugin tracks OpenClaw activity (messages, commands, sessions, tools) and sends heartbeats via the official `wakatime` CLI.
```

### Optional gh CLI flow

```bash
# fork and clone
gh repo fork openclaw/openclaw --clone --remote
cd openclaw

# create branch
git checkout -b docs/add-openclaw-wakatime-community-plugin

# edit docs/plugins/community.md and add the entry block under "Listed plugins"

git add docs/plugins/community.md
git commit -m "docs(plugins): add @ambiguoustr/openclaw-wakatime to community plugins"
git push -u origin docs/add-openclaw-wakatime-community-plugin

gh pr create \
  --repo openclaw/openclaw \
  --base main \
  --head ambiguoustexture:docs/add-openclaw-wakatime-community-plugin \
  --title "docs(plugins): add @ambiguoustr/openclaw-wakatime to community plugins" \
  --body-file /path/to/your/pr-body.md
```

## WakaTime Community Submission

Reference:

- `https://wakatime.com/help/creating-plugin` (Releasing -> Distribution)
- `https://wakatime.com/help/contact-support`

### Submission message (copy/paste)

```text
Hi WakaTime team,

I built a community plugin integration for OpenClaw:
- Name: openclaw-wakatime
- npm: @ambiguoustr/openclaw-wakatime
- Repo: https://github.com/ambiguoustexture/openclaw-wakatime
- Install: openclaw plugins install @ambiguoustr/openclaw-wakatime

The plugin sends heartbeats through the official wakatime-cli and includes plugin identity via --plugin.
Please consider adding it to the WakaTime community plugins list.

Thanks!
```
