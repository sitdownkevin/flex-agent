#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROMPTS_DIR=baseline_oneshot
LANGUAGE=zh
CLEAR_ALL=true
PROMPT="使用扎根理论方法，对所有语料做元宇宙游戏的体验价值构念开发"

source "${SCRIPT_DIR}/_run.sh"
