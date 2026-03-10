#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/Users/apple/Documents/Claude Code/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

echo "[eval-analysis-p0p1] root=${ROOT_DIR}"
echo "[eval-analysis-p0p1] python=${PYTHON_BIN}"

pushd "${ROOT_DIR}/backend" >/dev/null
"${PYTHON_BIN}" -m unittest \
  test_task_queue_idempotency.py \
  test_review_data_schema.py \
  test_processing_param_specs.py \
  test_analysis_flow.py
"${PYTHON_BIN}" -m compileall app
popd >/dev/null

pushd "${ROOT_DIR}/frontend" >/dev/null
npm run lint
npm run build
popd >/dev/null

"${ROOT_DIR}/tools/devstack.sh" verify-new-code
"${ROOT_DIR}/tools/devstack.sh" restart frontend
node "${ROOT_DIR}/frontend/qa-analysis-flow-headed.mjs"

echo "[eval-analysis-p0p1] PASSED"
