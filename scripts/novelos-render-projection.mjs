#!/usr/bin/env node
/**
 * 项目投影渲染（node:sqlite 直连，零依赖）——py 版 scripts/novelos_render_projection.py
 * 的 JS 移植（零 Python 纪律：全仓不新建 .py，本脚本是投影功能的唯一权威实现）。
 *
 * 把权威数据库 ``data/novelos-v2.db`` 的内容单向渲染为 Markdown 文件目录
 * ``novels/<项目目录>/``。只渲染当前权威视图（locked 规划 + accepted 正文），
 * 不渲染候选诊断、全部产出与溯源档案。
 *
 * 用法:
 *   node scripts/novelos-render-projection.mjs --project project:xxx
 *   node scripts/novelos-render-projection.mjs --project project:xxx --output novels/
 *   node scripts/novelos-render-projection.mjs --project project:xxx --verify   # 渲染后校验 manifest
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

export const PROJECTION_FORMAT_VERSION = 1;
export const GENERATOR_VERSION = '3.0.0';

const _ILLEGAL_CHAR = /[\x00-\x1f\x7f\\/:*?"<>|]/g;
const _CN_DIGITS = '零一二三四五六七八九';

export function contentHash(data) {
  const buf = typeof data === 'string' ? Buffer.from(data, 'utf8') : data;
  return `sha256:${crypto.createHash('sha256').update(buf).digest('hex')}`;
}

export function cnNum(n) {
  /** 正整数转中文数字（1->一, 10->十, 21->二十一）。 */
  if (n < 0) return String(n);
  if (n === 0) return '零';
  if (n < 10) return _CN_DIGITS[n];
  if (n < 20) return n === 10 ? '十' : `十${_CN_DIGITS[n - 10]}`;
  if (n < 100) {
    const tens = Math.floor(n / 10);
    const ones = n % 10;
    return `${_CN_DIGITS[tens]}十${ones ? _CN_DIGITS[ones] : ''}`;
  }
  if (n < 1000) {
    const hundreds = Math.floor(n / 100);
    const rest = n % 100;
    const result = `${_CN_DIGITS[hundreds]}百`;
    if (rest === 0) return result;
    if (rest < 10) return `${result}零${_CN_DIGITS[rest]}`;
    return result + cnNum(rest);
  }
  return String(n);
}

export function sanitizeFilename(name, fallback = 'untitled') {
  if (!name) return fallback;
  let cleaned = String(name)
    .replace(_ILLEGAL_CHAR, '_')
    .trim()
    .replace(/^[ .]+|[ .]+$/g, '');
  if (!cleaned || cleaned === '..' || cleaned === '.' || cleaned.includes('..')) {
    return fallback;
  }
  return cleaned;
}

// --------------------------------------------------------------------------- //
// 读取层：node:sqlite 直连，组装权威快照
// --------------------------------------------------------------------------- //

function _readResource(db, resourceId) {
  /** 读 resources.content（BLOB/TEXT）为 UTF-8 文本。 */
  const row = db.prepare('SELECT content FROM resources WHERE id=?').get(resourceId);
  if (!row) return '';
  const blob = row.content;
  if (blob == null) return '';
  if (typeof blob === 'string') return blob;
  return Buffer.from(blob).toString('utf8');
}

function _row(db, sql, ...params) {
  return db.prepare(sql).get(...params) ?? null;
}

function _rows(db, sql, ...params) {
  return db.prepare(sql).all(...params);
}

function _json(value, fallback = {}) {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function loadSnapshot(db, projectId) {
  const project = _row(db, 'SELECT * FROM projects WHERE id=?', projectId);
  if (!project) {
    fail(`找不到项目 ${projectId}`);
  }

  // locked 规划资产
  const planning = {};
  const volumeOutlines = [];
  const chapterPlans = [];
  for (const r of _rows(
    db,
    "SELECT * FROM planning_assets WHERE project_id=? AND status='locked' ORDER BY asset_type",
    projectId,
  )) {
    r.content = _readResource(db, r.content_resource_id);
    r.metadata = _json(r.metadata_json);
    planning[r.asset_type] = r;
    if (r.asset_type === 'volume_outline') volumeOutlines.push(r);
    else if (r.asset_type === 'chapter_plan') chapterPlans.push(r);
  }

  // creator 签名（binding → profile_version → resource）+ 派生溯源（derivation resource）
  const binding = _row(db, 'SELECT * FROM project_creator_bindings WHERE project_id=?', projectId);
  let creatorSignature = null;
  let creatorDerivation = null;
  if (binding) {
    const pv = _row(db, 'SELECT * FROM creator_profile_versions WHERE id=?', binding.profile_version_id);
    const profile = _row(db, 'SELECT * FROM creator_profiles WHERE id=?', binding.profile_id);
    if (pv && profile) {
      const signature = _json(_readResource(db, pv.content_resource_id), null);
      creatorSignature = {
        profile_id: binding.profile_id,
        profile_display_name: profile.display_name,
        profile_version_id: binding.profile_version_id,
        profile_revision: binding.profile_revision,
        subject_hash: binding.subject_hash,
        binding_mode: binding.binding_mode,
        signature,
      };
      if (pv.derivation_resource_id) {
        creatorDerivation = _json(_readResource(db, pv.derivation_resource_id), null);
      }
    }
  }

  // 向导 setup 快照（projects.metadata_json.$.setup——项目定位的权威存储）
  const metadataObj = _json(project.metadata_json);
  const projectSetup = metadataObj && typeof metadataObj === 'object' ? metadataObj.setup ?? null : null;

  // book_soul 从 locked direction 的 metadata 提取
  let bookSoul = null;
  const direction = planning.direction;
  if (direction && direction.metadata && 'book_soul' in direction.metadata) {
    bookSoul = {
      direction_id: direction.id,
      direction_version: direction.version,
      direction_subject_hash: direction.subject_hash ?? '',
      book_soul: direction.metadata.book_soul,
    };
  }

  // accepted 正文（JOIN volumes/books）
  const chapters = _rows(
    db,
    `SELECT c.*, v.number AS volume_number, v.title AS volume_title
     FROM chapters c
     JOIN volumes v ON c.volume_id = v.id
     JOIN books b ON v.book_id = b.id
     WHERE b.project_id=? AND c.status='accepted'
     ORDER BY v.number, c.number`,
    projectId,
  );
  for (const c of chapters) {
    c.content = _readResource(db, c.content_resource_id);
  }

  // 卷号/标题映射（volume_outline / chapter_plan 的 scope_ref 是 volume:{id}）
  const volumesById = {};
  for (const v of _rows(
    db,
    'SELECT v.* FROM volumes v JOIN books b ON v.book_id=b.id WHERE b.project_id=?',
    projectId,
  )) {
    volumesById[v.id] = v;
  }

  // 实体
  const characters = _rows(db, 'SELECT * FROM characters WHERE project_id=? ORDER BY name', projectId);
  for (const ch of characters) {
    if (ch.description_resource_id) {
      ch.description = _readResource(db, ch.description_resource_id);
    }
  }
  const worlds = _rows(db, 'SELECT * FROM worlds WHERE project_id=? ORDER BY name', projectId);
  for (const w of worlds) {
    if (w.description_resource_id) {
      w.description = _readResource(db, w.description_resource_id);
    }
  }

  // 连续性账本
  const continuity = {
    narrative_promises: _rows(db, 'SELECT * FROM narrative_promises WHERE project_id=? ORDER BY id', projectId),
    expectation_ledgers: _rows(db, 'SELECT * FROM expectation_ledgers WHERE project_id=? ORDER BY id', projectId),
    relationship_states: _rows(db, 'SELECT * FROM relationship_states WHERE project_id=? ORDER BY id', projectId),
    arc_states: _rows(db, 'SELECT * FROM arc_states WHERE project_id=? ORDER BY id', projectId),
    timelines: _rows(db, 'SELECT * FROM timelines WHERE project_id=? ORDER BY sequence, label', projectId),
    chapter_facts: _rows(
      db,
      "SELECT * FROM chapter_facts WHERE project_id=? AND status='accepted' ORDER BY id",
      projectId,
    ),
  };

  // 权威快照 hash（只覆盖权威内容，确定性可重现）
  const snapshotPayload = {
    project,
    creator_signature: creatorSignature,
    book_soul: bookSoul,
    planning_assets: Object.fromEntries(Object.entries(planning).map(([k, v]) => [k, v.content])),
    chapters: chapters.map((c) => ({ id: c.id, content: c.content })),
  };
  const authoritySnapshotHash = contentHash(canonicalJson(snapshotPayload));

  return {
    project,
    creator_signature: creatorSignature,
    creator_derivation: creatorDerivation,
    project_setup: projectSetup,
    book_soul: bookSoul,
    planning,
    volume_outlines: volumeOutlines,
    chapter_plans: chapterPlans,
    chapters,
    volumes_by_id: volumesById,
    characters,
    worlds,
    continuity,
    authority_snapshot_hash: authoritySnapshotHash,
  };
}

// --------------------------------------------------------------------------- //
// 渲染层
// --------------------------------------------------------------------------- //

const _SIGNATURE_LABELS = {
  sympathies: '天然同情',
  distrusts: '持续警惕',
  recurring_attention: '反复关注',
  narrative_principles: '叙事原则',
  forbidden_conveniences: '禁止的便利解法',
  expression_preferences: '表达偏好',
  negative_constraints: '负面约束',
};
const _PERSONA_DIMENSION_LABELS = {
  generation_age: '世代与年龄',
  education_horizon: '教育与视野',
  class_circle_inventory: '阶层与圈子库存',
  career_track: '职业履历',
  life_trajectory: '人生轨迹',
};
const _THEME_LABELS = {
  agency: 'agency（自主·成就·掌控）',
  communion: 'communion（联结·归属·关系）',
  dual: '双主题并重',
};
const _SOUL_LABELS = {
  organizing_principle: '组织原则',
  unresolved_claims: '未决追问',
  central_contradiction: '核心矛盾',
  promise_cadence: '承诺兑现节奏',
  power_currency: '力量货币',
  costly_commitments: '有代价的承诺',
  protected_dignity: '受保护的尊严',
  forbidden_resolutions: '禁止的解决方式',
  recurring_tests: '重复检验',
  narrative_mercy: '叙事仁慈',
  narrative_cruelty: '叙事残酷',
  deliberate_silences: '刻意留白',
};
const _PLANNING_MAP = {
  direction: '01-故事方向.md',
  architecture: '02-故事架构.md',
  strategy: '03-全书战略.md',
  world_contract: '05-世界契约.md',
  story_arc: '06-故事弧.md',
};
// character_contract 不走 _PLANNING_MAP 单文件，改由 splitCharacterContract
// 拆成「人物契约/」目录（00-总览 + 每人物一份），见 render() E2 段。

// 人物档案二级标题：## 人物档案：{角色}｜{名字}（兼容中英冒号与中英竖线）。
const _CHARACTER_HEADING = /^##\s+人物档案[:：]\s*(.+?)\s*[|｜]\s*(.+?)\s*$/;
const _H2_HEADING = /^##\s/;

export function splitCharacterContract(content) {
  /** 按「## 人物档案：角色｜名字」把人物契约拆成总览 + 各人物。
   *
   * 返回 ``{"overview": str, "characters": [{"role","name","body"}]}``，
   * ``body`` 含该人物的标题行及其下全部内容（到下一个二级标题前）。
   * 非人物档案的二级标题段与文档顶部内容归入 ``overview``。
   * 主角（角色含「主角」）排第一，其余按出现顺序。
   *
   * 识别不到任何人物档案标题时返回 ``null``，调用方据此走单文件兜底。
   */
  const segments = [{ titleLines: [], bodyLines: [] }];
  for (const line of content.split(/\r?\n/)) {
    if (_H2_HEADING.test(line)) {
      segments.push({ titleLines: [line], bodyLines: [] });
    } else {
      segments[segments.length - 1].bodyLines.push(line);
    }
  }

  const overviewParts = [];
  const characters = [];
  for (const { titleLines, bodyLines } of segments) {
    const titleLine = titleLines.length > 0 ? titleLines[0] : null;
    const body = [...titleLines, ...bodyLines].join('\n').trim();
    const match = titleLine ? _CHARACTER_HEADING.exec(titleLine) : null;
    if (match) {
      characters.push({ role: match[1].trim(), name: match[2].trim(), body });
    } else if (body) {
      overviewParts.push(body);
    }
  }

  if (characters.length === 0) return null;

  const protagonists = characters.filter((c) => c.role.includes('主角'));
  const others = characters.filter((c) => !c.role.includes('主角'));
  return { overview: overviewParts.join('\n\n').trim(), characters: protagonists.concat(others) };
}

export class ProjectionError extends Error {}

function fail(message) {
  throw new ProjectionError(message);
}

function _withinRoot(root, target) {
  const rel = path.relative(root, target);
  return rel === '' || (!rel.startsWith(`..${path.sep}`) && rel !== '..' && !path.isAbsolute(rel));
}

/**
 * 确定性 JSON 序列化（键递归排序 + 紧凑格式），用于权威快照 hash 的稳定重现。
 * 语义对齐 py 版 json.dumps(..., sort_keys=True, ensure_ascii=False)。
 */
function canonicalJson(value) {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'string') return pyJsonString(value);
  if (typeof value === 'number') {
    if (Number.isNaN(value) || value === Infinity || value === -Infinity) return 'null';
    return String(value);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(', ')}]`;
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    return `{${keys.map((k) => `${pyJsonString(k)}: ${canonicalJson(value[k])}`).join(', ')}}`;
  }
  return 'null';
}

/** 与 python json.dumps(ensure_ascii=False) 对齐的字符串转义（不转义非 ASCII、U+2028/2029）。 */
function pyJsonString(s) {
  let out = '"';
  for (const ch of String(s)) {
    const code = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === '\\') out += '\\\\';
    else if (code === 0x08) out += '\\b';
    else if (code === 0x0c) out += '\\f';
    else if (code === 0x0a) out += '\\n';
    else if (code === 0x0d) out += '\\r';
    else if (code === 0x09) out += '\\t';
    else if (code < 0x20) out += `\\u${code.toString(16).padStart(4, '0')}`;
    else out += ch;
  }
  return `${out}"`;
}

export function render(snapshot, projectId, outputRoot) {
  const project = snapshot.project;
  const projectTitle = project.name || project.title || 'Untitled';
  const projectVersion = project.version;
  const authorityHash = snapshot.authority_snapshot_hash;

  const rootDir = path.resolve(outputRoot);
  const dirName = sanitizeFilename(projectTitle, `project_${projectId}`);
  const targetDir = path.resolve(rootDir, dirName);
  if (!_withinRoot(rootDir, targetDir)) {
    fail(`目标渲染路径超出许可根目录范围: ${targetDir}`);
  }

  // 目标目录归属校验（防覆盖其他项目）
  if (fs.existsSync(targetDir)) {
    const manifestFile = path.join(targetDir, 'manifest.json');
    if (fs.existsSync(manifestFile)) {
      try {
        const old = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
        if (old.project_id && old.project_id !== projectId) {
          fail(`目标目录已存在且属于其他项目 ${old.project_id}，拒绝覆盖`);
        }
      } catch (err) {
        if (err instanceof SyntaxError) {
          // 无效 manifest 视为无归属，允许重建
        } else {
          throw err;
        }
      }
    }
  }

  fs.mkdirSync(rootDir, { recursive: true });
  const tmpDir = path.join(rootDir, `.tmp_${dirName}_${crypto.randomUUID().replace(/-/g, '')}`);
  fs.mkdirSync(tmpDir, { recursive: true });

  const filesManifest = [];

  const writeMarkdown = (relPath, title, body, source) => {
    const safeParts = relPath.split('/').map((p) => sanitizeFilename(p));
    const absPath = path.resolve(tmpDir, ...safeParts);
    if (!_withinRoot(tmpDir, absPath)) {
      fail(`渲染路径非法逃逸: ${relPath}`);
    }
    fs.mkdirSync(path.dirname(absPath), { recursive: true });
    const text = title ? `# ${title}\n\n${body}\n` : `${body}\n`;
    const data = Buffer.from(text, 'utf8');
    fs.writeFileSync(absPath, data);
    const digest = contentHash(data);
    filesManifest.push({
      relative_path: safeParts.join('/'),
      sha256: digest,
      source_type: source.source_type ?? 'derived',
      source_id: source.source_id ?? '',
      source_version: source.source_version ?? 1,
      source_hash: source.source_hash || digest,
    });
  };

  // A. README（含向导 setup 定位摘要——频道/平台/规模/题材/表里基调/美学）
  let readmeBody =
    `此文件夹为 NovelOS 项目《${projectTitle}》派生的用户只读投影。\n\n` +
    '> [!IMPORTANT]\n' +
    '> **只读提示**：本目录由权威数据库单向渲染，可随时安全删除并重新生成。' +
    '直接修改其中 Markdown 文件**不会回写**数据库。\n\n' +
    `- **项目 ID**：\`${projectId}\`\n` +
    `- **项目版本**：\`v${projectVersion}\`\n` +
    `- **权威快照 Hash**：\`${authorityHash}\`\n`;
  const setup = snapshot.project_setup;
  if (setup && typeof setup === 'object') {
    const traits = setup.platform_traits || {};
    const setupLines = ['', '## 项目定位（向导 setup 快照）', ''];
    setupLines.push(
      `- **频道×平台**：${setup.channel ?? '?'} · ${setup.platform ?? '?'}` +
        (traits.model ? `（${traits.model}）` : ''),
    );
    if (traits.patience) setupLines.push(`- **平台耐心**：${traits.patience}`);
    setupLines.push(`- **规模**：${setup.scale ?? '?'}`);
    setupLines.push(`- **题材**：${setup.primary_genre ?? '?'}`);
    if (setup.secondary_directions) {
      setupLines.push(`- **二级方向**：${setup.secondary_directions.join('、')}`);
    }
    const surface = setup.emotional_surface || [];
    const core = setup.emotional_core;
    if (surface.length > 0 || core) {
      setupLines.push(`- **表里基调**：表层 ${surface.join('、') || '—'} / 内核 ${core || '—'}`);
    }
    if (setup.tonal_contrast) {
      setupLines.push(`- **表里声明**：${setup.tonal_contrast}`);
    }
    if (setup.aesthetic_styles) {
      setupLines.push(`- **美学风格**：${setup.aesthetic_styles.join('、')}`);
    }
    readmeBody += setupLines.join('\n') + '\n';
  }
  writeMarkdown('README.md', `《${projectTitle}》项目展示视图`, readmeBody, {
    source_type: 'project_readme',
    source_id: projectId,
  });

  // B. 创作约束/作者签名（先见人，再见规：persona 在前）
  const creator = snapshot.creator_signature;
  let body;
  let src;
  if (creator) {
    const sig = creator.signature || {};
    const lines = [
      `- **Profile**：${creator.profile_display_name} (\`${creator.profile_id}\`)`,
      `- **版本**：revision ${creator.profile_revision} (\`${creator.profile_version_id}\`)`,
      `- **Hash**：\`${creator.subject_hash}\``,
      `- **绑定模式**：\`${creator.binding_mode}\``,
    ];
    const persona = sig.persona;
    if (persona && typeof persona === 'object') {
      lines.push('', '## 创作者人格', '', persona.narrative ?? '');
      const anchors = persona.anchors || {};
      const sketch = anchors.profile_sketch;
      if (sketch) lines.push('', `> ${sketch}`);
      const dims = anchors.five_dimensions || {};
      const dimLines = Object.entries(_PERSONA_DIMENSION_LABELS).map(([key, label]) => [
        label,
        dims[key],
      ]);
      if (dimLines.some(([, value]) => value)) {
        lines.push('', '### 人生五维');
        for (const [label, value] of dimLines) {
          if (value) lines.push(`- **${label}**：${value}`);
        }
      }
      const traits = anchors.trait_profile || [];
      if (traits.length > 0) {
        lines.push('', '### 特质简档（行为化）');
        for (const item of traits) lines.push(`- ${item}`);
      }
      const theme = anchors.theme_orientation || {};
      if (theme.dominant) {
        const themeLabel = _THEME_LABELS[theme.dominant] ?? theme.dominant;
        const evidence = theme.evidence ?? '';
        lines.push('', '### 主题倾向');
        lines.push(`- **主导**：${themeLabel}` + (evidence ? `——${evidence}` : ''));
      }
      const tension = anchors.inner_tension;
      if (tension) lines.push('', '### 自觉的内在矛盾', '', tension);
      const voices = anchors.voice_samples || [];
      if (voices.length > 0) {
        lines.push('', '### 声音样本');
        for (const v of voices) lines.push(`> ${v}`);
      }
      const blindspots = anchors.blindspots || {};
      const refuses = blindspots.refuses || [];
      const cannot = blindspots.cannot_write || [];
      if (refuses.length > 0 || cannot.length > 0) {
        lines.push('', '### 盲区（对全知全能的限制）');
        for (const item of refuses) lines.push(`- **拒绝写**：${item}`);
        for (const item of cannot) lines.push(`- **写不了**：${item}`);
      }
    }
    for (const [field, label] of Object.entries(_SIGNATURE_LABELS)) {
      lines.push('', `## ${label}`);
      for (const item of sig[field] ?? []) lines.push(`- ${item}`);
    }
    // 风格 DNA（schema v3，R5；全部防御式——v1/v2 签名无此字段时整段跳过）
    const dna = sig.style_dna;
    if (dna && typeof dna === 'object' && !Array.isArray(dna)) {
      lines.push('', '## 风格 DNA（style_dna）');
      const tier = dna.corpus_basis?.tier;
      if (tier) lines.push(`- **语料分级**：${tier}${dna.corpus_basis?.notes ? `——${dna.corpus_basis.notes}` : ''}`);
      for (const [key, label] of [
        ['lexicon_summary', '语言习惯摘要'],
        ['syntax_patterns', '句式模式'],
        ['punctuation_habits', '标点习惯'],
        ['structure_preferences', '结构偏好'],
        ['dialogue_style', '对白风格'],
      ]) {
        const v = dna[key];
        if (typeof v === 'string' && v.trim()) lines.push(`- **${label}**：${v}`);
        else if (Array.isArray(v) && v.length) for (const item of v) lines.push(`- **${label}**：${item}`);
      }
    }
    const feats = sig.measured_features;
    if (Array.isArray(feats) && feats.length) {
      lines.push('', '## 逐特征豁免依据（measured_features）');
      for (const f of feats) {
        if (f && f.feature) lines.push(`- \`${f.feature}\`${f.metric ? `（${f.metric}=${f.value ?? '?'}` : ''}${f.metric ? '）' : ''}${f.source ? ` —— ${f.source}` : ''}`);
      }
    }
    const derivation = snapshot.creator_derivation;
    if (derivation && typeof derivation === 'object') {
      lines.push('', '## 派生溯源', '');
      lines.push(
        `- **Parent**：${derivation.parent_display_name ?? '?'}` +
          `（\`${derivation.parent_version_id ?? '?'}\`）`,
      );
      const aux = derivation.auxiliary_archetypes || [];
      if (aux.length > 0) lines.push(`- **辅助原型**：${aux.length} 个`);
      const snapshotIn = derivation.user_input_snapshot || {};
      const hints = snapshotIn.user_persona_hints || {};
      const hintDesc =
        Object.entries(hints)
          .map(([k, v]) => `${k}×${v.length}`)
          .join('、') || '未填写';
      lines.push(`- **用户人格素材**：${hintDesc}`);
      const rationale = derivation.rationale;
      if (rationale) lines.push('', '### parent 判定理由与取舍', '', rationale);
    }
    body = lines.join('\n');
    src = {
      source_type: 'creator_signature',
      source_id: creator.profile_version_id,
      source_version: creator.profile_revision,
      source_hash: creator.subject_hash,
    };
  } else {
    body = '*当前项目尚未绑定 Creator Profile。*';
    src = { source_type: 'creator_signature_absent', source_id: projectId };
  }
  writeMarkdown('创作约束/作者签名.md', '作者签名', body, src);

  // C. 创作约束/本书创作灵魂
  const soul = snapshot.book_soul;
  if (soul) {
    const sv = soul.book_soul;
    const lines = [
      `- **Direction**：\`${soul.direction_id}\`，version ${soul.direction_version}`,
      `- **Hash**：\`${soul.direction_subject_hash}\``,
    ];
    for (const [field, label] of Object.entries(_SOUL_LABELS)) {
      const value = sv[field];
      if (!value) continue;
      lines.push('', `## ${label}`);
      if (Array.isArray(value)) {
        for (const item of value) lines.push(`- ${item}`);
      } else {
        lines.push(String(value));
      }
    }
    body = lines.join('\n');
    src = {
      source_type: 'book_soul',
      source_id: soul.direction_id,
      source_version: soul.direction_version,
      source_hash: soul.direction_subject_hash,
    };
  } else {
    body = '*当前没有包含有效 `book_soul` 的 locked Story Direction。*';
    src = { source_type: 'book_soul_absent', source_id: projectId };
  }
  writeMarkdown('创作约束/本书创作灵魂.md', '本书创作灵魂', body, src);

  // E. 规划/（locked 资产，character_contract 除外——见 E2）
  const planning = snapshot.planning;
  for (const [assetType, filename] of Object.entries(_PLANNING_MAP)) {
    const asset = planning[assetType];
    if (asset) {
      writeMarkdown(`规划/${filename}`, `规划：${assetType}`, asset.content, {
        source_type: 'planning_asset',
        source_id: asset.id,
        source_version: asset.version,
        source_hash: asset.subject_hash ?? '',
      });
    }
  }

  // E2. 人物契约特殊渲染：按「## 人物档案：角色｜名字」拆成 规划/人物契约/ 目录。
  // 识别不到该结构（如尚未按新约定整理的残缺契约）时退化为单文件并警告。
  const cc = planning.character_contract;
  if (cc) {
    const ccSource = {
      source_type: 'planning_asset',
      source_id: cc.id,
      source_version: cc.version,
      source_hash: cc.subject_hash ?? '',
    };
    const split = splitCharacterContract(cc.content);
    if (split === null) {
      console.error(
        '警告: character_contract 未按「## 人物档案：角色｜名字」结构组织，' +
          '退化为单文件 规划/04-人物契约.md',
      );
      writeMarkdown('规划/04-人物契约.md', '规划：character_contract', cc.content, ccSource);
    } else {
      writeMarkdown('规划/人物契约/00-总览.md', '人物契约·总览', split.overview, ccSource);
      for (const [idx, ch] of split.characters.entries()) {
        const nn = String(idx + 1).padStart(2, '0');
        const fname = `规划/人物契约/${nn}-${sanitizeFilename(ch.role)}-${sanitizeFilename(ch.name)}.md`;
        writeMarkdown(fname, `${ch.role}｜${ch.name}`, ch.body, ccSource);
      }
    }
  }

  // F. 大纲/（卷纲 + 章纲）
  const volumesById = snapshot.volumes_by_id;
  for (const vol of snapshot.volume_outlines) {
    const scope = vol.scope_ref ?? '';
    const vid = scope.startsWith('volume:') ? scope.slice('volume:'.length) : scope;
    const volRow = volumesById[vid] ?? {};
    const vNum = Number(volRow.number ?? 1) || 1;
    const vCn = cnNum(vNum);
    const vTitle = volRow.title || vol.title || `第${vCn}卷`;
    writeMarkdown(`大纲/第${vCn}卷/卷纲.md`, `第 ${vCn} 卷卷纲：${vTitle}`, vol.content ?? '', {
      source_type: 'volume_outline',
      source_id: vol.id,
      source_version: vol.version,
      source_hash: vol.subject_hash ?? '',
    });
  }
  for (const plan of snapshot.chapter_plans) {
    const scope = plan.scope_ref ?? '';
    const chapMatch = /:chapter_(\d+)$/.exec(scope);
    if (!chapMatch) continue;
    const cNum = Number(chapMatch[1]);
    const volMatch = /^(volume:[^:]+):/.exec(scope);
    let vNum = 1;
    if (volMatch) {
      // 归一化：py 版此处带 "volume:" 前缀查裸 id 永远落第一卷（≥2 卷时章纲错卷），
      // JS 移植版剥掉前缀按真实卷号渲染。
      const vid = volMatch[1].replace(/^volume:/, '');
      vNum = Number(volumesById[vid]?.number ?? 1) || 1;
    }
    const vCn = cnNum(vNum);
    const cTitle = plan.title || `第${String(cNum).padStart(3, '0')}章`;
    writeMarkdown(
      `大纲/第${vCn}卷/第${String(cNum).padStart(3, '0')}章-章纲.md`,
      `第 ${vCn} 卷第 ${cNum} 章执行卡：${cTitle}`,
      plan.content ?? '',
      {
        source_type: 'chapter_plan',
        source_id: plan.id,
        source_version: plan.version,
        source_hash: plan.subject_hash ?? '',
      },
    );
  }

  // G. 正文/（accepted 章节）
  for (const ch of snapshot.chapters) {
    const vNum = Number(ch.volume_number ?? 1) || 1;
    const vCn = cnNum(vNum);
    const cNum = Number(ch.number ?? 1) || 1;
    const cTitle = sanitizeFilename(ch.title ?? '未命名章节');
    writeMarkdown(
      `正文/第${vCn}卷/第${String(cNum).padStart(3, '0')}章-${cTitle}.md`,
      ch.title ?? `第 ${cNum} 章`,
      ch.content ?? '',
      {
        source_type: 'chapter',
        source_id: ch.id,
        source_version: ch.version ?? 1,
        source_hash: ch.subject_hash ?? '',
      },
    );
  }

  // H. 人物/ & 世界/
  for (const char of snapshot.characters) {
    const name = sanitizeFilename(char.name);
    const body =
      `**分类**：${char.role_class ?? ''}　**状态**：${char.status ?? ''}` +
      (char.exit_type ? `　**退场**：${char.exit_type}` : '') +
      `\n\n**描述**：${char.description ?? ''}` +
      `\n\n**补充**：${char.state_json ?? ''}`;
    writeMarkdown(`人物/${name}.md`, char.name, body, {
      source_type: 'character',
      source_id: char.id,
      source_version: char.version,
    });
  }
  for (const world of snapshot.worlds) {
    const name = sanitizeFilename(world.name);
    const body = `**设定**：${world.description ?? ''}\n\n**状态**：${world.state_json ?? ''}`;
    writeMarkdown(`世界/${name}.md`, world.name, body, {
      source_type: 'world',
      source_id: world.id,
      source_version: world.version,
    });
  }

  // I. 连续性/账本
  const contFiles = [
    ['伏笔与叙事承诺.md', '叙事承诺账本', 'narrative_promises'],
    ['读者期待.md', '读者期待账本', 'expectation_ledgers'],
    ['人物关系.md', '人物关系状态', 'relationship_states'],
    ['故事弧状态.md', '故事弧状态账本', 'arc_states'],
    ['时间线.md', '时间线账本', 'timelines'],
    ['正文事实.md', '正文事实与逻辑账本', 'chapter_facts'],
  ];
  for (const [fname, title, key] of contFiles) {
    const data = snapshot.continuity[key] ?? [];
    const body = data.length > 0 ? JSON.stringify(data, null, 2) : '*尚无相关记录*';
    writeMarkdown(`连续性/${fname}`, title, body, {
      source_type: 'continuity_ledger',
      source_id: fname,
    });
  }

  // I+. 人物状态注册表（migration 018 重建后的人物状态唯一锚点）
  if (snapshot.characters.length > 0) {
    const lines = ['| 姓名 | 分类 | 状态 | 退场 | 职责/补充 |', '|---|---|---|---|---|'];
    for (const char of snapshot.characters) {
      lines.push(
        `| ${char.name} | ${char.role_class ?? ''} | ${char.status ?? ''} ` +
          `| ${char.exit_type ?? ''} | ${char.state_json ?? ''} |`,
      );
    }
    writeMarkdown('连续性/人物状态注册表.md', '人物状态注册表', lines.join('\n'), {
      source_type: 'character_registry',
      source_id: 'characters',
    });
  }

  // J. manifest.json
  const manifestPayload = {
    projection_format_version: PROJECTION_FORMAT_VERSION,
    project_id: projectId,
    project_title: projectTitle,
    project_version: projectVersion,
    authority_snapshot_hash: authorityHash,
    generator_version: GENERATOR_VERSION,
    file_count: filesManifest.length,
    files: filesManifest.slice().sort((a, b) =>
      a.relative_path < b.relative_path ? -1 : a.relative_path > b.relative_path ? 1 : 0,
    ),
  };
  fs.writeFileSync(path.join(tmpDir, 'manifest.json'), JSON.stringify(manifestPayload, null, 2));

  // 原子替换
  if (fs.existsSync(targetDir)) {
    fs.rmSync(targetDir, { recursive: true, force: true });
  }
  fs.renameSync(tmpDir, targetDir);

  return {
    project_id: projectId,
    project_title: projectTitle,
    output_directory: targetDir,
    authority_snapshot_hash: authorityHash,
    rendered_file_count: filesManifest.length + 1,
  };
}

export function verifyManifest(projectDirectory) {
  /** 逐文件校验 manifest：重算 SHA-256 比对。 */
  const projectPath = path.resolve(projectDirectory);
  const manifestPath = path.join(projectPath, 'manifest.json');
  if (!fs.existsSync(manifestPath)) {
    fail(`目标目录缺少 manifest.json: ${manifestPath}`);
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const errors = [];
  let verified = 0;
  for (const entry of manifest.files ?? []) {
    const rel = entry.relative_path ?? '';
    const fp = path.resolve(projectPath, rel);
    if (!_withinRoot(projectPath, fp)) {
      errors.push(`路径逃逸: ${rel}`);
      continue;
    }
    if (!fs.existsSync(fp)) {
      errors.push(`缺失文件: ${rel}`);
      continue;
    }
    if (contentHash(fs.readFileSync(fp)) !== (entry.sha256 ?? '')) {
      errors.push(`SHA-256 不匹配: ${rel}`);
    }
    verified += 1;
  }
  return { verified_file_count: verified, errors };
}

export function main(argv = process.argv.slice(2)) {
  const { values } = parseArgs({
    args: argv,
    options: {
      project: { type: 'string' },
      output: { type: 'string', default: 'novels' },
      db: { type: 'string', default: 'data/novelos-v2.db' },
      verify: { type: 'boolean', default: false },
    },
    allowPositionals: false,
  });

  if (!values.project) {
    console.error(
      '用法: node scripts/novelos-render-projection.mjs --project project:xxx ' +
        '[--output novels] [--db data/novelos-v2.db] [--verify]',
    );
    process.exit(1);
  }

  let db;
  try {
    try {
      db = new DatabaseSync(values.db, { readOnly: true });
    } catch (err) {
      fail(`无法打开数据库 ${values.db}: ${err.message}`);
    }
    const snapshot = loadSnapshot(db, values.project);
    const result = render(snapshot, values.project, values.output);
    console.log(`渲染完成: ${result.output_directory}`);
    console.log(`文件数: ${result.rendered_file_count}`);
    console.log(`权威快照 Hash: ${result.authority_snapshot_hash}`);
    if (values.verify) {
      const vr = verifyManifest(result.output_directory);
      if (vr.errors.length > 0) {
        console.log(`校验失败 (${vr.errors.length} 项):`);
        for (const e of vr.errors) console.log(`  - ${e}`);
        process.exitCode = 1;
      } else {
        console.log(`manifest 校验通过: ${vr.verified_file_count} 个文件`);
      }
    }
  } catch (err) {
    if (err instanceof ProjectionError) {
      console.error(err.message);
      process.exitCode = 1;
    } else {
      throw err;
    }
  } finally {
    if (db) db.close();
  }
}

// 直接以 CLI 方式运行时执行 main
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
