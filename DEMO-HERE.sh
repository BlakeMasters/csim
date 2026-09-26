#!/usr/bin/env bash
# Start the local demo on macOS from any working directory.
# First run: bash DEMO-HERE.sh --install
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="$repo_root/.venv/bin/python"
oss_cli="$repo_root/.venv/bin/ocura-oss"
install=false
check_only=false
board_port=8765
playground_port=8766
engine_cli=""

while (($#)); do
  case "$1" in
    --install) install=true; shift ;;
    --check-only) check_only=true; shift ;;
    --board-port|--playground-port|--engine-cli)
      if (($# < 2)); then echo "Missing value for $1" >&2; exit 2; fi
      case "$1" in
        --board-port) board_port="$2" ;;
        --playground-port) playground_port="$2" ;;
        --engine-cli) engine_cli="$2" ;;
      esac
      shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -x "$python" ]]; then
  if [[ "$install" != true || "$check_only" == true ]]; then
    echo 'Demo environment missing. Run: bash DEMO-HERE.sh --install' >&2
    exit 1
  fi
  echo 'Creating the local Python 3.12 environment...'
  python3.12 -m venv "$repo_root/.venv"
fi
if [[ "$install" == true ]]; then
  echo 'Installing pinned demo dependencies, including Ocura OSS...'
  "$python" -m pip install -r "$repo_root/requirements-hackathon.txt"
fi

args=("$repo_root/tools/start_live_demo.py" --board-port "$board_port"
      --playground-port "$playground_port" --oss-cli "$oss_cli")
if [[ "$check_only" == true ]]; then args+=(--check-only); fi
if [[ -n "$engine_cli" ]]; then args+=(--engine-cli "$engine_cli"); fi

cd "$repo_root"
if [[ "$check_only" != true ]]; then
  printf 'Board:      http://127.0.0.1:%s/\n' "$board_port"
  printf 'Playground: http://127.0.0.1:%s/\n' "$playground_port"
  printf 'Campaign:   http://127.0.0.1:%s/campaign\n' "$playground_port"
  echo 'Keep this terminal open during the demo; press Ctrl+C to stop owned services.'
fi
exec "$python" "${args[@]}"
