#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${project_dir}/.venv/bin/python"
if [[ ! -x "${python_bin}" ]]; then
  python_bin="python3"
fi

seed_database="${project_dir}/mcp/novelos/resources/seed.db"
seed_inventory="${project_dir}/mcp/novelos/resources/seed-inventory.json"

if [[ -n "${NOVELOS_SEED_DB_PATH:-}" || -n "${NOVELOS_SEED_INVENTORY_PATH:-}" ]]; then
  echo "生产 runner 固定使用已授权 seed 及其清单，拒绝环境变量覆盖。" >&2
  exit 64
fi
if [[ ! -r "${seed_database}" || ! -r "${seed_inventory}" ]]; then
  echo "已授权 seed 或冻结清单不存在，拒绝启动。" >&2
  exit 66
fi

export PYTHONPATH="${project_dir}/mcp/novelos/src"

exec "${python_bin}" -m novelos_mcp.server \
  --database "${NOVELOS_DB_PATH:-${project_dir}/data/novelos-v2.db}" \
  --seed-database "${seed_database}" \
  --seed-inventory "${seed_inventory}" \
  --catalog "${NOVELOS_CATALOG_PATH:-${project_dir}/catalog/skills}" \
  --agent-contracts "${NOVELOS_AGENT_CONTRACT_PATH:-${project_dir}/config/agents.yaml}"
