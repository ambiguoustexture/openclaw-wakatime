#!/usr/bin/env zsh
# WakaTime hook for shell command tracking in OpenClaw sessions.

if [[ -n "${OPENCLAW_WAKATIME_DISABLE_HOOK}" || -n "${WAKATIME_OPENCLAW_DISABLE_HOOK}" ]]; then
  return
fi

typeset -g OPENCLAW_WAKATIME_PLUGIN_VERSION="1.2.0"

_openclaw_wakatime_detect_version() {
  local version="${OPENCLAW_VERSION:-${OPENCLAW_WAKATIME_OPENCLAW_VERSION:-}}"
  local raw=""

  if [[ -z "${version}" ]] && command -v openclaw >/dev/null 2>&1; then
    raw="$(openclaw --version 2>/dev/null | head -n 1)"
    version="$(printf '%s' "${raw}" | grep -Eo '[0-9]+([.][0-9]+)+([-.][A-Za-z0-9._-]+)?' | head -n 1)"
  fi

  if [[ -z "${version}" ]] && [[ -f "${HOME}/.openclaw/openclaw.json" ]]; then
    raw="$(grep -m1 '"lastTouchedVersion"' "${HOME}/.openclaw/openclaw.json" 2>/dev/null)"
    version="$(printf '%s' "${raw}" | sed -E 's/.*"lastTouchedVersion"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
  fi

  if [[ -z "${version}" ]]; then
    version="unknown"
  fi

  printf '%s' "${version}"
}

typeset -g OPENCLAW_WAKATIME_OPENCLAW_VERSION="$(_openclaw_wakatime_detect_version)"
typeset -g OPENCLAW_WAKATIME_PLUGIN_ID="OpenClaw/${OPENCLAW_WAKATIME_OPENCLAW_VERSION} openclaw-wakatime/${OPENCLAW_WAKATIME_PLUGIN_VERSION}"

_openclaw_wakatime_preexec() {
  local cmd="$1"
  local trimmed="${cmd:0:140}"
  local waka_bin="${HOME}/.local/bin/wakatime"

  if [[ ! -x "${waka_bin}" ]]; then
    return
  fi

  "${waka_bin}" \
    --entity "openclaw://shell/${trimmed}" \
    --entity-type app \
    --language Shell \
    --project openclaw-shell \
    --plugin "${OPENCLAW_WAKATIME_PLUGIN_ID}" \
    --write >/dev/null 2>&1 &
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _openclaw_wakatime_preexec
