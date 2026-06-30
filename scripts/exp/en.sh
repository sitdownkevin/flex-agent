#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROMPTS_DIR=baseline_en
LANGUAGE=en
CLEAR_ALL=true
PROMPT="Use grounded theory methods to develop experience value constructs for all metaverse game comments in the corpus."

source "${SCRIPT_DIR}/_run.sh"
