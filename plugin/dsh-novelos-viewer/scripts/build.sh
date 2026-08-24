#!/bin/bash
# Build dsh-novelos-viewer: src/ → lib/（host tsc）+ client tsdown。
# 兼容两种 DSH 布局：
#   A. 源码 checkout（有 packages/）：peer 依赖 junction 到 vendor/packages
#   B. 安装版桌面目录（只有 node_modules）：junction 到其 node_modules 真包
#      —— 运行期插件必须与宿主共享同一 cordis/tools 实例，junction 保证这一点。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ---- 探测 DSH 根：环境变量 → 常见路径 ----
DSH_ROOT="${DSH_CHECKOUT:-}"
if [ -z "$DSH_ROOT" ]; then
  for candidate in "$HOME/dsh-harness" "$HOME/dsh" "$HOME/.dsh/dsh-harness" "/d/Program Files/DSH Desktop/dsh-desktop" "/mnt/d/Program Files/DSH Desktop/dsh-desktop"; do
    if [ -d "$candidate/node_modules/@deepseek-ai" ] || [ -d "$candidate/packages" ]; then
      DSH_ROOT="$candidate"; break
    fi
  done
fi

# ---- tsc：本地 devDep 优先，退回 checkout ----
TSC=""
for cand in "$ROOT/node_modules/.bin/tsc" "$ROOT/node_modules/.bin/tsc.cmd" "${DSH_ROOT:-}/node_modules/.bin/tsc"; do
  if [ -x "$cand" ] || [ -f "$cand" ]; then TSC="$cand"; break; fi
done
if [ -z "$TSC" ]; then
  echo "build: no tsc found (pnpm install in plugin dir, or set DSH_CHECKOUT)" >&2
  exit 1
fi

link_pkg() {
  local pkg="$1"; shift
  local target=""
  for rel in "$@"; do
    # 相对根的候选：源码布局或安装版 node_modules 布局
    if [ -e "$DSH_ROOT/$rel" ]; then target="$DSH_ROOT/$rel"; break; fi
  done
  if [ -z "$target" ]; then
    echo "build: dependency target missing for $pkg" >&2
    exit 1
  fi
  local link="node_modules/$pkg"
  mkdir -p "$(dirname "$link")"
  rm -rf "$link"
  node -e "
    const fs=require('fs'),path=require('path');
    fs.symlinkSync(path.resolve(process.argv[1]),path.resolve(process.argv[2]),process.platform==='win32'?'junction':'dir');
  " "$target" "$link"
}

echo "=== Linking peer deps (dsh root: ${DSH_ROOT:-<none>}) ==="
# 注意：不碰 pnpm 装的 dependencies/devDependencies（sql.js/typescript/@types/node）
if [ -n "$DSH_ROOT" ]; then
  link_pkg "@deepseek-ai/cordis" "vendor/cordis" "node_modules/@deepseek-ai/cordis"
  link_pkg "cosmokit" "vendor/cosmokit" "node_modules/cosmokit"
  link_pkg "@deepseek-ai/schemastery" "vendor/schemastery" "node_modules/@deepseek-ai/schemastery" "node_modules/schemastery"
  link_pkg "@deepseek-ai/dsh-tools" "packages/core/tools" "node_modules/@deepseek-ai/dsh-tools"
  link_pkg "@deepseek-ai/dsh-llm" "packages/llm/llm" "node_modules/@deepseek-ai/dsh-llm"
  link_pkg "@deepseek-ai/dsh-client-ui-slots" "packages/client/ui-slots" "node_modules/@deepseek-ai/dsh-client-ui-slots"
fi

echo "=== Compile host (src → lib) ==="
"$TSC" -p tsconfig.json

echo "=== Build complete（client 由 dev_build_plugin 流水线 npm run build:client 完成）==="
