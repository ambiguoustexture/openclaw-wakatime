# Release Guide

This document is the single runbook for publishing `@re/openclaw-wakatime` and submitting community listings.

Current package:

- npm: `@re/openclaw-wakatime`
- repo: `https://github.com/ambiguoustexture/openclaw-wakatime`
- install: `openclaw plugins install @re/openclaw-wakatime`

## 1) Preflight Checks

Run from repo root:

```bash
git status --short
node --check setup_wakatime.mjs
openclaw plugins info openclaw-wakatime
npm pack --dry-run
npm publish --dry-run --access public
```

Recommended functional check before release:

```bash
openclaw gateway restart
# trigger one real message/tool event
# then verify:
tail -n 30 ~/.openclaw/wakatime/plugin.log
```

## 2) Commit and Push

Ensure git identity is correct:

```bash
git config --get user.name
git config --get user.email
```

Commit:

```bash
git add -A
git commit -m "feat: release @re/openclaw-wakatime 0.9.9"
```

Push:

```bash
git push origin main
```

## 3) Publish to npm

Login and verify identity:

```bash
npm login
npm whoami
```

Publish:

```bash
npm publish --access public
```

Verify published version:

```bash
npm view @re/openclaw-wakatime version
```

## 4) Submit to OpenClaw Community Plugins

Official requirements and format:

- Docs: `https://docs.openclaw.ai/plugins/community`

Checklist:

- Package is published on npmjs.
- GitHub repo is public.
- Repo has setup/use docs.
- Repo has issue tracker (GitHub Issues enabled).
- Maintainer activity signal is present.

Submission action:

1. Open PR against:
`https://github.com/openclaw/openclaw/blob/main/docs/plugins/community.md`
2. Add one line under listed plugins using required format.

Candidate line for this plugin:

```text
WakaTime — Track OpenClaw messages, commands, sessions, and tool usage in WakaTime. npm: `@re/openclaw-wakatime` repo: `https://github.com/ambiguoustexture/openclaw-wakatime` install: `openclaw plugins install @re/openclaw-wakatime`
```

Suggested PR title:

```text
docs(community-plugins): add @re/openclaw-wakatime
```

## 5) Submit to WakaTime Community Plugins

Official plugin release guidance:

- Docs: `https://wakatime.com/help/creating-plugin` (Releasing -> Distribution)

The guide states to publish on GitHub and send your repo to WakaTime for Community listing.
Use WakaTime help/contact channels to share the repo and package:

- Contact entry: `https://wakatime.com/help/contact-support`

Suggested submission message:

```text
Hi WakaTime team,

I built a new community plugin integration:
- Name: openclaw-wakatime
- npm: @re/openclaw-wakatime
- Repo: https://github.com/ambiguoustexture/openclaw-wakatime
- Install: openclaw plugins install @re/openclaw-wakatime

It sends heartbeats through wakatime-cli and includes plugin/version signature via --plugin.
Please consider adding it to the WakaTime Community plugins list.

Thanks!
```

## 6) Post-Release Verification

Check that production users can install and load:

```bash
openclaw plugins install @re/openclaw-wakatime --pin
openclaw gateway restart
openclaw plugins info openclaw-wakatime
```

Cloud-side WakaTime verification:

- Confirm plugin appears in user agents/status.
- Confirm heartbeats arrive with expected entity/project/language.
