#!/usr/bin/env node
/**
 * catalog/skills 逐文件 sha256 manifest lint（R7-T2，对抗审查 P2-5 处置）。
 *
 * 背景：方法层资产（catalog/skills/** 的 prompt.md / modules / metadata.yaml 等 351 文件）
 * 此前零机器守护——被删的 test_recipe_matrix.py 只管配方矩阵，文件漂移（改名/改文/删卡）
 * 无任何报警（行为证据：chapter-draft prompt 按需 Read 指向已腐坏路径数月无人发现）。
 * 形态参照 oh-story-dsh manifest v2（逐文件 sha256+bytes），本仓自研零依赖实现。
 *
 * 用法：
 *   node scripts/novelos-catalog-manifest.mjs            # 生成/刷新 config/catalog-manifest.json
 *   node scripts/novelos-catalog-manifest.mjs --check    # 复核工作树 vs manifest，漂移 exit 1
 *   node scripts/novelos-catalog-manifest.mjs --help
 * 流程约定：任何改动 catalog/skills/** 的提交须同步刷新 manifest（跑一次无参模式）；
 * guardrails G3 常驻复核（一致性单检查），本脚本 --check 出漂移明细。
 * exit：0 = 一致（或刷新成功）；1 = 漂移；2 = 用法/IO 错误。
 */

import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CATALOG = path.join(ROOT, 'catalog/skills');
const MANIFEST_PATH = path.join(ROOT, 'config/catalog-manifest.json');
const SCHEMA = 'novelos.catalog-manifest.v1';

export class ManifestUsageError extends Error {}

/** 递归收集 catalog/skills 下全部文件的相对路径（posix 分隔符，排序稳定）。 */
export function collectCatalogFiles() {
  const out = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.isFile()) out.push(path.relative(ROOT, p).split(path.sep).join('/'));
    }
  };
  if (!fs.existsSync(CATALOG)) throw new ManifestUsageError(`catalog/skills 不存在：${CATALOG}`);
  walk(CATALOG);
  return out;
}

function fileDigest(rel) {
  const buf = fs.readFileSync(path.join(ROOT, rel));
  return { sha256: createHash('sha256').update(buf).digest('hex'), bytes: buf.length };
}

/** 生成 manifest 对象（不落盘）。 */
export function buildManifest() {
  const files = collectCatalogFiles();
  const entries = {};
  for (const rel of files) entries[rel] = fileDigest(rel);
  return {
    schema: SCHEMA,
    generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    file_count: files.length,
    files: entries,
  };
}

/** 复核工作树 vs 已存 manifest。返回漂移明细数组（空数组=一致）。 */
export function checkManifest() {
  if (!fs.existsSync(MANIFEST_PATH)) {
    return [{ kind: 'no_manifest', detail: 'config/catalog-manifest.json 不存在——先跑无参模式生成' }];
  }
  let saved;
  try {
    saved = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
  } catch (e) {
    return [{ kind: 'manifest_unparsable', detail: String(e.message || e) }];
  }
  if (saved.schema !== SCHEMA) {
    return [{ kind: 'schema_mismatch', detail: `manifest schema=${saved.schema} ≠ ${SCHEMA}` }];
  }
  const drifts = [];
  const current = collectCatalogFiles();
  const savedPaths = Object.keys(saved.files ?? {});
  for (const rel of savedPaths) {
    if (!current.includes(rel)) {
      drifts.push({ kind: 'removed', path: rel, detail: 'manifest 有而工作树无' });
      continue;
    }
    const d = fileDigest(rel);
    if (d.sha256 !== saved.files[rel].sha256) {
      drifts.push({ kind: 'changed', path: rel, detail: `sha256 ${saved.files[rel].sha256.slice(0, 12)}… → ${d.sha256.slice(0, 12)}…` });
    }
  }
  for (const rel of current) {
    if (!savedPaths.includes(rel)) drifts.push({ kind: 'added', path: rel, detail: '工作树有而 manifest 无（新增文件须刷新 manifest）' });
  }
  drifts.sort((a, b) => a.path.localeCompare(b.path) || a.kind.localeCompare(b.kind));
  return drifts;
}

function usage() {
  return [
    '用法：node scripts/novelos-catalog-manifest.mjs [--check]',
    '  无参    生成/刷新 config/catalog-manifest.json（catalog/skills/** 逐文件 sha256+bytes）',
    '  --check 复核工作树 vs manifest；漂移（增/删/改）exit 1 并逐条列明',
    '流程约定：改动 catalog/skills/** 的提交须同步刷新 manifest；guardrails G3 常驻复核。',
  ].join('\n');
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--help') || argv.includes('-h')) {
    console.log(usage());
    return;
  }
  if (argv.includes('--check')) {
    const drifts = checkManifest();
    if (drifts.length === 0) {
      const m = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
      console.log(`catalog manifest 一致：${m.file_count} 文件全部 sha256 匹配（${MANIFEST_PATH.replace(ROOT + '/', '')}）`);
      return;
    }
    console.error(`catalog manifest 漂移 ${drifts.length} 处：`);
    for (const d of drifts) console.error(`  [${d.kind}] ${d.path} —— ${d.detail}`);
    console.error('如改动合法：跑无参模式刷新 manifest 后随本次提交入库。');
    process.exitCode = 1;
    return;
  }
  if (argv.length > 0) throw new ManifestUsageError(`未知参数：${argv.join(' ')}`);
  const m = buildManifest();
  fs.writeFileSync(MANIFEST_PATH, JSON.stringify(m, null, 2) + '\n', 'utf8');
  console.log(`已生成 ${MANIFEST_PATH.replace(ROOT + '/', '')}：${m.file_count} 文件，sha256 全量登记（generated_at=${m.generated_at}）`);
}

const invokedDirectly = (() => {
  try {
    return Boolean(process.argv[1])
      && path.resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase();
  } catch {
    return false;
  }
})();

if (invokedDirectly) {
  try {
    await main();
  } catch (e) {
    console.error(e && e.stack ? e.stack : String(e));
    process.exitCode = e instanceof ManifestUsageError ? 2 : 2;
  }
}
