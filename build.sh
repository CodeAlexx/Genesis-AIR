#!/bin/sh
# Build Genesis AIR against a pinned AIR toolchain.
#
# The AIR compiler and standard library are DISCOVERED, never copied into this project.
# air-sdk.conf records exactly which AIR commit this application is built against; override
# either path with AIR_HOME / AIRC in the environment.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck disable=SC1091
. "$here/air-sdk.conf"

case "$AIR_SDK" in /*) ;; *) AIR_SDK="$here/$AIR_SDK" ;; esac
case "$AIR_TOOLCHAIN" in /*) ;; *) AIR_TOOLCHAIN="$here/$AIR_TOOLCHAIN" ;; esac
AIR_HOME=${AIR_HOME:-$AIR_SDK}
case "$AIR_HOME" in /*) ;; *) AIR_HOME="$here/$AIR_HOME" ;; esac
AIRC=${AIRC:-$AIR_TOOLCHAIN/build-gcc15/bin/airc}
case "$AIRC" in /*) ;; *) AIRC="$here/$AIRC" ;; esac
export AIR_STDLIB="$AIR_HOME/stdlib"

if [ ! -x "$AIRC" ]; then
  echo "genesis-air: no AIR compiler at $AIRC" >&2
  echo "  set AIRC=/path/to/airc, or build one in $AIR_TOOLCHAIN" >&2
  exit 1
fi
if [ ! -f "$AIR_STDLIB/editor.ai" ]; then
  echo "genesis-air: $AIR_STDLIB has no std.editor" >&2
  echo "  Genesis AIR needs the AIR portable NLE toolkit ($AIR_SDK_COMMIT)" >&2
  exit 1
fi

have=$(cd "$AIR_HOME" && git rev-parse HEAD 2>/dev/null || echo unknown)
if [ "$have" != "$AIR_SDK_COMMIT" ] &&
   ! (cd "$AIR_HOME" && git merge-base --is-ancestor "$AIR_SDK_COMMIT" "$have" 2>/dev/null); then
  echo "genesis-air: warning — AIR SDK is at $have, this project pins $AIR_SDK_COMMIT" >&2
fi

# One shared editor implementation supplies exact Split semantics on both OS.
editor_patch="$here/patches/air-editor.patch"
if [ ! -f "$editor_patch" ]; then
  echo 'genesis-air: [GA_SDK_PATCH_MISSING] shared editor overlay is missing' >&2
  exit 1
fi
if git -C "$AIR_HOME" apply --reverse --check "$editor_patch" >/dev/null 2>&1; then
  :
elif git -C "$AIR_HOME" apply --check "$editor_patch" >/dev/null 2>&1; then
  git -C "$AIR_HOME" apply "$editor_patch"
else
  echo 'genesis-air: [GA_SDK_PATCH_BASE] editor overlay does not match SDK; existing changes preserved' >&2
  exit 1
fi

editor_io_patch="$here/patches/air-editor-io.patch"
if [ ! -f "$editor_io_patch" ]; then
  echo 'genesis-air: [GA_SDK_IO_PATCH_MISSING] shared project codec overlay is missing' >&2
  exit 1
fi
if git -C "$AIR_HOME" apply --reverse --check "$editor_io_patch" >/dev/null 2>&1; then
  :
elif git -C "$AIR_HOME" apply --check "$editor_io_patch" >/dev/null 2>&1; then
  git -C "$AIR_HOME" apply "$editor_io_patch"
else
  echo 'genesis-air: [GA_SDK_IO_PATCH_BASE] project codec overlay does not match SDK; existing changes preserved' >&2
  exit 1
fi

# Retryable credit polling and started-frame writes have distinct time budgets.
channel_patch="$here/patches/air-channel-deadlines.patch"
if [ ! -f "$channel_patch" ]; then
  echo 'genesis-air: [GA_SDK_CHANNEL_PATCH_MISSING] shared channel deadline overlay is missing' >&2
  exit 1
fi
if git -C "$AIR_HOME" apply --reverse --check "$channel_patch" >/dev/null 2>&1; then
  :
elif git -C "$AIR_HOME" apply --check "$channel_patch" >/dev/null 2>&1; then
  git -C "$AIR_HOME" apply "$channel_patch"
else
  echo 'genesis-air: [GA_SDK_CHANNEL_PATCH_BASE] channel deadline overlay does not match SDK; existing changes preserved' >&2
  exit 1
fi

mkdir -p "$here/build"
mode=${MODE:-release}
echo "genesis-air: building against AIR $AIR_SDK_COMMIT ($mode)"
# Capture the report even when the compile fails: the diagnostics live inside it, and
# dying before the reporter runs is how a build error turns into silence.
set +e
"$AIRC" build "$here/src/main.ai" -o "$here/build/genesis-air" --mode "$mode" --json > "$here/build/build.json"
status=$?
set -e
if [ "$status" -ne 0 ]; then
  # Keep the compiler's structured report available and surface it without requiring
  # a second language runtime.
  if command -v python3 >/dev/null 2>&1; then
    python3 "$here/report_build.py" "$here/build/build.json" || true
  else
    sed 's/^/  /' "$here/build/build.json" >&2
  fi
  echo "genesis-air: build failed ($status)" >&2
  exit "$status"
fi
echo "genesis-air: build/genesis-air"
