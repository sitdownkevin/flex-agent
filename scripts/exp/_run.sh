#!/usr/bin/env bash
# Shared runner — set PROMPTS_DIR, LANGUAGE, CLEAR_ALL, PROMPT first.
# OPENAI_MODEL is read from project .env; workspace label is derived automatically.

set -euo pipefail

: "${PROMPTS_DIR:?PROMPTS_DIR is required}"
: "${LANGUAGE:?LANGUAGE is required}"
: "${CLEAR_ALL:?CLEAR_ALL is required}"
: "${PROMPT:?PROMPT is required}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT}"

ENV_FILE="${ROOT}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ -z "${OPENAI_MODEL:-}" ]]; then
  echo "OPENAI_MODEL is not set in ${ENV_FILE}" >&2
  exit 1
fi

LABEL="${OPENAI_MODEL}-${PROMPTS_DIR}"
export OPENAI_MODEL_PRO="${OPENAI_MODEL_PRO:-${OPENAI_MODEL}}"

inputs=()
if [[ "${CLEAR_ALL}" == "true" ]]; then
  inputs+=("/clear")
fi
inputs+=("${PROMPT}")
inputs+=("exit")

RUN_CMD="uv run agent -p ${PROMPTS_DIR} -w ${LABEL} -l ${LANGUAGE}"
echo ">>> ${RUN_CMD}" >&2
printf '%s\n' "${inputs[@]}" | ${RUN_CMD}
