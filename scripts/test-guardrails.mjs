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
const DYNAMIC_PREFIXES = ['upstream:', 'upstream-reviews:', 'canon_minimal', 'review_feedback', 'knowledge:'];

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

  // d/e/f) divergence/decision_scope 全等 + 词表合法（R7-T2 复活被删的 test_recipe_matrix
  // 守护——config/agent-recipes.json description 声称此校验存在而原 .py 已随零 Python 退役；
  // 对抗审查 P2-5 行为证据之一）。absent/空串/null 归一为 null 再比。
  const norm = (v) => (v === undefined || v === null || v === '' ? null : v);
  check(
    `G2d divergence 全等 ${label}`,
    deepEqual(norm(entry.divergence), norm(manifest.divergence)),
    `matrix=${JSON.stringify(norm(entry.divergence))} manifest=${JSON.stringify(norm(manifest.divergence))}`
  );
  check(
    `G2e decision_scope 全等 ${label}`,
    deepEqual(norm(entry.decision_scope), norm(manifest.decision_scope)),
    `matrix=${JSON.stringify(norm(entry.decision_scope))} manifest=${JSON.stringify(norm(manifest.decision_scope))}`
  );
  check(
    `G2f 档位词表合法 ${label}`,
    (entry.divergence == null || entry.divergence === '' || entry.divergence in recipes.divergence_tiers)
      && entry.decision_scope in recipes.decision_scopes,
    `divergence=${JSON.stringify(entry.divergence)} decision_scope=${JSON.stringify(entry.decision_scope)}`
  );
}

// ── 守卫 2.5：catalog 方法层资产漂移复核（G3，R7-T2） ──────────────────────
// catalog/skills/** 351 文件的 sha256 全量登记在 config/catalog-manifest.json，
// 改动方法层须跑 `node scripts/novelos-catalog-manifest.mjs` 刷新并随提交入库；
// 此处常驻复核一致性，漂移明细用 `novelos-catalog-manifest.mjs --check` 看。
const { checkManifest } = await import('./novelos-catalog-manifest.mjs');
const manifestDrifts = checkManifest();
check(
  'G3 catalog manifest 与工作树一致（catalog/skills/** 逐文件 sha256）',
  manifestDrifts.length === 0,
  manifestDrifts.slice(0, 3).map((d) => `[${d.kind}] ${d.path}`).join(' | ') + '（明细：--check）'
);

// ── 守卫三：knowledge 蒸馏域文件 schema（KG1，R3） ────────────────────────
// 校验 config/knowledge/distilled.<domain>.json（蒸馏产物，入 git）的结构契约：
// 必需字段齐 / id 格式 kg-<domain>-NNN / placement 枚举 / formula 为非空数组 /
// card_module_md ≤2560B。校验器只读 config/knowledge/，不得依赖 gitignored 的 data/ 源。
const KG_DIR = path.join(ROOT, 'config/knowledge');
const KG_REQUIRED = ['id', 'name', 'trigger_scene', 'formula', 'anti_patterns', 'placement', 'scene_tags', 'source'];
const KG_PLACEMENTS = ['slot', 'card', 'both'];
const KG_CARD_MAX_BYTES = 2560;

const kgFiles = fs.existsSync(KG_DIR)
  ? fs.readdirSync(KG_DIR).filter((f) => /^distilled\.[a-z0-9-]+\.json$/.test(f)).sort()
  : [];
check('KG1 蒸馏域文件存在（config/knowledge/distilled.*.json ≥1）', kgFiles.length > 0);

for (const f of kgFiles) {
  const domain = f.replace(/^distilled\./, '').replace(/\.json$/, '');
  let doc = null;
  try {
    doc = JSON.parse(fs.readFileSync(path.join(KG_DIR, f), 'utf8'));
  } catch { /* 保持 null，下方判定 FAIL */ }
  check(`KG1 ${f} 可解析且 domain 字段一致`, doc !== null && doc.domain === domain,
    'JSON 不可解析或 domain 与文件名不符');
  if (doc === null) continue;

  const entries = Array.isArray(doc.entries) ? doc.entries : [];
  check(`KG1 ${f} entries 非空数组`, entries.length > 0);
  if (entries.length === 0) continue;

  const badFields = [];
  const badIds = [];
  const badPlacement = [];
  const badFormula = [];
  const idRe = new RegExp(`^kg-${domain}-\\d{3}$`);
  for (const [i, e] of entries.entries()) {
    const missing = KG_REQUIRED.filter((k) => e?.[k] === undefined || e?.[k] === null);
    if (missing.length > 0) badFields.push(`#${i}缺[${missing.join(',')}]`);
    if (typeof e?.id !== 'string' || !idRe.test(e.id)) badIds.push(`#${i}:${JSON.stringify(e?.id)}`);
    if (!KG_PLACEMENTS.includes(e?.placement)) badPlacement.push(`#${i}:${JSON.stringify(e?.placement)}`);
    if (!Array.isArray(e?.formula) || e.formula.length === 0) badFormula.push(`#${i}`);
  }
  check(`KG1 ${f} 条目必需字段齐（${KG_REQUIRED.join('/')}）`, badFields.length === 0,
    badFields.slice(0, 3).join(' '));
  check(`KG1 ${f} id 格式 kg-${domain}-NNN`, badIds.length === 0, badIds.slice(0, 3).join(' '));
  check(`KG1 ${f} placement 枚举 [${KG_PLACEMENTS.join('|')}]`, badPlacement.length === 0,
    badPlacement.slice(0, 3).join(' '));
  check(`KG1 ${f} formula 为非空数组`, badFormula.length === 0, badFormula.slice(0, 3).join(' '));
  check(`KG1 ${f} card_module_md ≤${KG_CARD_MAX_BYTES}B`,
    typeof doc.card_module_md === 'string'
    && Buffer.byteLength(doc.card_module_md, 'utf8') <= KG_CARD_MAX_BYTES,
    `实际 ${Buffer.byteLength(String(doc.card_module_md ?? ''), 'utf8')}B`);
}

// ── 守卫四：规划层参照模块红线（KG2，R4） ────────────────────────────────
// catalog/skills/planning/*/modules/reference-*.md 是「形态参照」模块（R5 裁-7
// modules 预组合通道投递）。三重隔离：
//   ① 信封头「非 Canon、无对账义务」必须在场（00-chain-coverage 发现二：参照不得
//      被当对账对象/对账源）；
//   ② 字节数 ≤2560（D3 计划 planning 参照预算）；
//   ③ 正文不含词表型键名（lexicon/positive_terms/banned_categories/measure_system
//      的键位形态：token 后接 := 或引号包裹键）——防参照变第二词表源；信封声明句
//      中对词表源名的提及（如 world_lexicon」）不带键位形态，不误伤。
const PLANNING_SKILLS = path.join(ROOT, 'catalog/skills/planning');
const KG2_ENVELOPE = '非 Canon、无对账义务';
const KG2_MAX_BYTES = 2560;
const KG2_TOKENS = 'lexicon|positive_terms|banned_categories|measure_system';
const KG2_KEY_RES = [
  new RegExp(`(?:^|[^A-Za-z0-9_])(?:${KG2_TOKENS})\\s*[:=]`, 'i'),
  new RegExp(`["'](?:${KG2_TOKENS})["']\\s*:`, 'i'),
];

const kg2Files = [];
if (fs.existsSync(PLANNING_SKILLS)) {
  for (const skill of fs.readdirSync(PLANNING_SKILLS).sort()) {
    const modDir = path.join(PLANNING_SKILLS, skill, 'modules');
    if (!fs.statSync(modDir, { throwIfNoEntry: false })?.isDirectory()) continue;
    for (const f of fs.readdirSync(modDir).sort()) {
      if (f.startsWith('reference-') && f.endsWith('.md')) {
        kg2Files.push({ label: `planning/${skill}/modules/${f}`, p: path.join(modDir, f) });
      }
    }
  }
}
check('KG2 参照模块存在（planning/*/modules/reference-*.md ≥1）', kg2Files.length > 0);

for (const { label, p } of kg2Files) {
  const text = fs.readFileSync(p, 'utf8');
  check(`KG2 信封头「${KG2_ENVELOPE}」在场 ${label}`, text.includes(KG2_ENVELOPE));
  const bytes = Buffer.byteLength(text, 'utf8');
  check(`KG2 字节数 ≤${KG2_MAX_BYTES}B ${label}`, bytes <= KG2_MAX_BYTES, `实际 ${bytes}B`);
  const hit = KG2_KEY_RES.map((re) => (text.match(re) ?? [])[0]).filter(Boolean);
  check(`KG2 无词表型键名 ${label}`, hit.length === 0, `命中:[${hit.join(', ')}]`);
}

console.log(`\n${passCount} passed, ${failCount} failed`);
process.exit(failCount > 0 ? 1 : 0);
