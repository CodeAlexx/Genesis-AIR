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
AIRC=${AIRC:-$AIR_TOOLCHAIN/build-dev/bin/airc}
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
if [ "$have" != "$AIR_SDK_COMMIT" ]; then
  echo "genesis-air: warning — AIR SDK is at $have, this project pins $AIR_SDK_COMMIT" >&2
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
  sed 's/^/  /' "$here/build/build.json" >&2
  echo "genesis-air: build failed ($status)" >&2
  exit "$status"
fi
echo "genesis-air: build/genesis-air"
