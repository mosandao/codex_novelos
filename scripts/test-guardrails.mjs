// 护栏测试：题材词表单源自洽 + 配方矩阵⊆manifest 一致性。
// 背景（对抗审查 A 路发现）：config/genre-packs.json 曾沦为运行期死配置
// （gate 读 wizard-data.js、组装器读 metadata_json 快照，两源无同步校验即漂移无声）；
// plugin/client/project-wizard-data.js 已随 plugin/ 移除退役，genre-packs.json 现为唯一词表源。
// 运行：node scripts/test-guardrails.mjs —— 全部 PASS 退出码 0，任一 FAIL 非零退出。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passCount = 0;
let failCount = 0;

function check(name, ok, detail = '') {
  if (ok) {
    passCount++;
    console.log(`PASS ${name}`);
  } else {
    failCount++;
    console.log(`FAIL ${name}${detail ? ' —— ' + detail : ''}`);
  }
}

function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ── 守卫一：题材词表结构自洽（单一来源） ────────────────────────────────
// 唯一来源约定：config/genre-packs.json 是题材词表的唯一权威（原 plugin/client/
// project-wizard-data.js 双源镜像已随 plugin/ 移除退役）。每包必须含四个非空数组字段。
const packs = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'config/genre-packs.json'), 'utf8')
);
const PACK_FIELDS = ['power_currency_candidates', 'typical_dilemmas', 'reader_expectations', 'taboos'];

check('G1 词表源存在且非空（config/genre-packs.json）', Object.keys(packs).length > 0);

for (const [key, pack] of Object.entries(packs)) {
  const missing = PACK_FIELDS.filter((f) => !Array.isArray(pack?.[f]));
  const empty = PACK_FIELDS.filter((f) => Array.isArray(pack?.[f]) && pack[f].length === 0);
  check(
    `G1 包结构自洽 ${key}`,
    missing.length === 0 && empty.length === 0,
    `缺失字段:[${missing}] 空字段:[${empty}]`
  );
}

// ── 守卫二：配方矩阵 ⊆ manifest 一致性 ────────────────────────────────
// 权威矩阵 config/agent-recipes.json 的每个资产：
//   a) 具名槽 ∈ slot_vocabulary 且 ∈ SLOT_REGISTRY（动态前缀除外）；
//   b) catalog/skills/<skill>/modules/manifest.json 的 data_slots 与矩阵槽集合完全一致
//      （组装器按 manifest.data_slots 注入——recipe-only 槽=声明了却永不注入）；
//   c) skill 目录真实存在。
const { SLOT_REGISTRY } = await import('./novelos-compose-prompt.mjs');
const recipes = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'config/agent-recipes.json'), 'utf8')
);
const DYNAMIC_PREFIXES = ['upstream:', 'upstream-reviews:', 'canon_minimal', 'review_feedback'];

for (const entry of recipes.assets) {
  const label = entry.asset;

  // a) 槽位合法性
  for (const slot of entry.slots) {
    const isDynamic = DYNAMIC_PREFIXES.some((p) => slot.startsWith(p));
    check(
      `G2a 槽注册 ${label}::${slot}`,
      isDynamic || (slot in SLOT_REGISTRY && recipes.slot_vocabulary.includes(slot)),
      isDynamic ? '' : '不在 SLOT_REGISTRY 或 slot_vocabulary'
    );
  }

  // b) manifest ⊆≡ matrix
  const manifestPath = path.join(ROOT, 'catalog/skills', entry.skill, 'modules/manifest.json');
  check(
    `G2c skill 目录存在 ${label} (${entry.skill})`,
    fs.existsSync(manifestPath)
  );
  if (!fs.existsSync(manifestPath)) continue;
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const rs = [...entry.slots].sort();
  const ms = [...(manifest.data_slots ?? [])].sort();
  check(
    `G2b 槽集合一致 ${label}`,
    deepEqual(rs, ms),
    `仅recipe:[${rs.filter((s) => !ms.includes(s))}] 仅manifest:[${ms.filter((s) => !rs.includes(s))}]`
  );
}

console.log(`\n${passCount} passed, ${failCount} failed`);
process.exit(failCount > 0 ? 1 : 0);
