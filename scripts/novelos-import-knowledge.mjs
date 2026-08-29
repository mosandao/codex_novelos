#!/usr/bin/env node
/**
 * novelos-import-knowledge.mjs — R5-D3 知识导入层（MySQL nwriter → data/knowledge/）
 *
 * R0 轮一次性 + 可重复工具。零 Python、Node 22+ 纯标准库、零 npm 依赖。
 * 通道：`mysql -B` CLI 导出 TSV（显式列清单，禁 SELECT *）→ Node 解析/清洗 → 落 JSON。
 *
 * ── 权威依据 ─────────────────────────────────────────────────────────────
 * · 裁-5（版权与数据通道总原则）：一切原始数据（真书名+原文例句+拆书文本+personas 原始卡）
 *   一律落 data/（gitignore）——本脚本产物 data/knowledge/、data/canary/ 均 gitignore；
 *   config/knowledge/ 只放蒸馏后方法论产物（后续轮次），本脚本不写 config/。
 * · 裁-6（quality 过滤口径）：原始 `BETWEEN 8 AND 10`（kb_writing_techniques = 1310 行）；
 *   0-100 刻度行（133 行，75-93）是另一套打分体系，整段排除不混入；
 *   normScore 仅作排序辅助字段（norm_score）保留，不参与过滤。
 * · 裁-4（金丝雀数据链）：kb_corpus_tags 必须导出 data/canary/tags.json 作选样标签字典。
 * · 红方 P1-8（dup_key）：kb_writing_techniques 导出条目计算
 *   dup_key = normalize(book_source) + '::' + normalize(technique_name)
 *   （归一：NFKC 全半角统一 + 去全部空白 + 循环去末尾括号后缀；不做大小写折叠），
 *   输出按 dup_key, category, id 排序——任务书字面「category, dup_key, id」在实测数据上
 *   无法兑现「同 key 条目相邻」（同 dup_key 条目的 category 实测完全发散，如 id 6/258/435
 *   分属世界观融入/信息差运用/叙事技法），按任务书「保证同 key 条目相邻（供蒸馏同批聚类）」
 *   的意图改为 dup_key 主导；偏差已记入计划文档 R0 执行偏差记录。
 * · author_name 归并预处理：kb_author_personas 不导出（裁-5，归 D4 直连试点），
 *   其归并逻辑（刘慈欣 5 变体/前导空格「 Priest」/同作者多行 17 组）不做；
 *   其余表 book_source/author 类字段仅做 trim。
 * · 幂等：meta.exported_at 为 UTC 日期粒度；同库状态下同日重跑字节一致（--verify 可复算对账）。
 *
 * ── 23 张 kb_* 表逐一处置（TABLE_DISPOSITIONS；实测清单以 SHOW TABLES LIKE 'kb\_%' 为准）──
 *   见下方 TABLE_DISPOSITIONS 注册表：16 张导出（含 kb_corpus_tags 双落 canary）、7 张不导逐条记理由。
 *
 * ── biz_* 显式排除声明 ──────────────────────────────────────────────────
 *   nwriter 库另有 biz_* 前缀表（红队快照 41 张；2026-08-29 实测 42 张）：
 *   biz_author_feature_profiles, biz_author_personas, biz_canon_snapshots, biz_chapter_briefs,
 *   biz_chapter_facts, biz_chapter_summaries, biz_chapters, biz_char_matrix, biz_character_relations,
 *   biz_characters, biz_chat_messages, biz_chat_sessions, biz_creative_strategy_drafts, biz_factions,
 *   biz_hooks, biz_locations, biz_mystery_designs, biz_node_runs, biz_novel_creation_plans,
 *   biz_novel_creation_steps, biz_novel_strategy_bindings, biz_novels, biz_optimization_suggestions,
 *   biz_outlines_versions, biz_pipeline_outputs, biz_pipeline_runs, biz_power_systems,
 *   biz_project_constitutions, biz_prompt_template_versions, biz_prompt_templates, biz_review_history,
 *   biz_story_core, biz_story_events, biz_subplots, biz_supervision_logs, biz_template_drafts,
 *   biz_volume_arc_nodes, biz_volumes, biz_warnings, biz_workflow, biz_world_state, biz_worldviews
 *   ——全部为 nwriter 应用运行时业务数据（小说/章节/工作流/聊天流水），非知识源，显式排除，
 *   后续轮次不得把 biz_worldviews / biz_power_systems 等语义相近表误当第二知识源开挖。
 *
 * ── 字段清洗规则 ─────────────────────────────────────────────────────────
 * · 所有表统一不导 created_at 等导入运行时元数据列；kb_technique_scene_maps 另丢
 *   priority_order（1..N 序列无信息量）/ combination_guides（全 NULL）/ book_examples（全 []）（计划 §1.6 裁决）。
 * · jsonColumns：text 列值 trim 后以 '[' 或 '{' 开头才 JSON.parse（数组→真数组、对象→真对象）；
 *   非 JSON 形态纯文本原样保真；形似 JSON 但解析失败 → 保留原字符串 + 条目级 `<col>_parse_error: true`，
 *   并记入 meta.parse_errors（仅 id+列名，不落内容）。
 * · trimColumns：book_source / author / book_name 类字段仅 trim。
 * · 溯源三件套：每条 item 必备 id（`kb:<域>:<orig_id>`）/ orig_id / book_source（无该列的表置 null）/ exported_at。
 * · NULL 传递：SQL 侧 IFNULL(col, CHAR(92,78)) 哨兵 → 解析侧还原 null（mysql -B 原生 NULL 打印
 *   'NULL' 与字符串值 'NULL' 不可区分，故用哨兵消歧）。
 *
 * ── 用法 ─────────────────────────────────────────────────────────────────
 *   node scripts/novelos-import-knowledge.mjs --all
 *   node scripts/novelos-import-knowledge.mjs --table kb_writing_techniques [--table kb_corpus_tags ...]
 *   node scripts/novelos-import-knowledge.mjs --verify
 *   选项：--out-dir data/knowledge（默认）  --canary-dir data/canary（默认）
 *         --mysql-host 127.0.0.1  --mysql-port 3306  --mysql-user root  --mysql-db nwriter
 *   凭据：密码经 MYSQL_PWD 环境变量传入（如 export MYSQL_PWD='…'），不进 argv、不进代码、不进日志。
 *   版权：本脚本不向终端/日志打印任何条目正文（仅表名与数字统计；dup_key 抽查仅含归一书名+技法名）。
 */

import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { parseArgs } from 'node:util';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

// ── 表处置注册表（23 张 kb_* 表逐一处置） ──────────────────────────────
// filterSql: null = 全量导出；否则 SQL WHERE 条件（裁-6 统一原始 BETWEEN 8 AND 10 口径）。
const TABLE_DISPOSITIONS = [
  // —— 导出（16 张） ——
  {
    table: 'kb_writing_techniques', disposition: 'export', idPrefix: 'kb:tech',
    reason: '写作技巧主源；R3 knowledge:techniques 槽 + 蒸馏首批源（裁-6 口径 1310 行）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'technique_name', 'category', 'sub_category', 'description', 'book_source',
      'applicable_scenes', 'application_rules', 'example_context', 'example_text', 'prerequisites',
      'difficulty_level', 'effectiveness_score', 'anti_patterns', 'quality_score'],
    jsonColumns: ['applicable_scenes', 'application_rules'],
    trimColumns: ['technique_name', 'book_source'],
    intColumns: ['id', 'difficulty_level', 'effectiveness_score', 'quality_score'],
    dupKeyFields: ['book_source', 'technique_name'],
    sort: 'category,dup_key,id',
  },
  {
    table: 'kb_technique_scene_maps', disposition: 'export', idPrefix: 'kb:scenemap',
    reason: '场景→技巧索引（15 行全量）；死引用仅 --verify 双口径报告，不自动剔除（不丢数据，蒸馏层否决）',
    filterSql: null,
    columns: ['id', 'scene_type', 'applicable_techniques', 'applicable_templates'],
    droppedColumns: ['priority_order（1..N 序列，无信息量）', 'combination_guides（全 NULL）', 'book_examples（全 []）'],
    jsonColumns: ['applicable_techniques', 'applicable_templates'],
    trimColumns: [],
    intColumns: ['id'],
    refCheck: { column: 'applicable_techniques', refTable: 'kb_writing_techniques' },
    sort: 'id',
  },
  {
    table: 'kb_book_summaries', disposition: 'export', idPrefix: 'kb:book',
    reason: '书级拆解；direction/architecture 参照（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'book_name', 'author', 'genre', 'word_count', 'chapter_count', 'analysis_date',
      'structure_type', 'core_theme', 'core_appeal', 'key_techniques', 'reusable_frameworks', 'notes', 'quality_score'],
    jsonColumns: ['key_techniques', 'reusable_frameworks'],
    trimColumns: ['book_name', 'author'],
    intColumns: ['id', 'word_count', 'chapter_count', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_dialogue_patterns', disposition: 'export', idPrefix: 'kb:dialogue',
    reason: '对话模式；chapter_plan 参照（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'pattern_name', 'book_source', 'dialogue_type', 'narrative_function', 'technique_desc',
      'formula', 'example_dialogue', 'character_voice', 'power_dynamics', 'anti_patterns', 'quality_score'],
    jsonColumns: ['formula'],
    trimColumns: ['pattern_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_scene_blueprints', disposition: 'export', idPrefix: 'kb:scene',
    reason: '场景蓝图；chapter_plan/volume_outline 参照（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'blueprint_name', 'book_source', 'scene_type', 'internal_structure', 'word_count_target',
      'hook_placement', 'cool_point_placement', 'suitable_contexts', 'pacing_notes', 'anti_patterns', 'quality_score'],
    jsonColumns: ['internal_structure'],
    trimColumns: ['blueprint_name', 'book_source'],
    intColumns: ['id', 'word_count_target', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_cool_point_patterns', disposition: 'export', idPrefix: 'kb:cool',
    reason: '爽点模式；strategy/volume_outline 参照（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'pattern_name', 'book_source', 'cool_point_type', 'frequency', 'formula', 'prerequisite',
      'intensity_curve', 'combined_patterns', 'reader_emotion', 'anti_patterns', 'quality_score'],
    jsonColumns: ['formula', 'combined_patterns', 'intensity_curve'],
    trimColumns: ['pattern_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_emotional_arc_patterns', disposition: 'export', idPrefix: 'kb:arc',
    reason: '情感弧线模式；story_arc 参照（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'pattern_name', 'book_source', 'arc_type', 'core_theme', 'stages', 'progression_rules',
      'trigger_events', 'resolution_pattern', 'suitable_genres', 'anti_patterns', 'quality_score'],
    jsonColumns: ['stages', 'suitable_genres'],
    trimColumns: ['pattern_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_plot_frameworks', disposition: 'export', idPrefix: 'kb:plot',
    reason: '情节框架；architecture/story_arc 参照（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'framework_name', 'book_source', 'genre_tags', 'framework_type', 'arc_config',
      'turning_points', 'vol_distribution', 'pacing_features', 'suitable_scenarios', 'narrative_function',
      'anti_patterns', 'quality_score'],
    jsonColumns: ['arc_config', 'turning_points', 'genre_tags', 'pacing_features', 'suitable_scenarios'],
    trimColumns: ['framework_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_story_genres', disposition: 'export', idPrefix: 'kb:genre',
    reason: '题材定义；direction 题材缺位兜底（全量 52，字段无 quality 脏数据）',
    filterSql: null,
    columns: ['id', 'genre_name', 'definition', 'example_titles', 'quality_score'],
    jsonColumns: [],
    trimColumns: ['genre_name'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_world_settings', disposition: 'export', idPrefix: 'kb:world',
    reason: '世界设定主表（kind=world）；world 参照（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'setting_name', 'book_source', 'world_type', 'core_rules', 'power_system',
      'special_elements', 'scope_scale', 'entry_point', 'immersive_details', 'atmosphere', 'anti_patterns', 'quality_score'],
    jsonColumns: ['core_rules', 'immersive_details'],
    jsonObjColumns: ['power_system'],
    trimColumns: ['setting_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_economic_systems', disposition: 'export', idPrefix: 'kb:econ',
    reason: '经济系统（kind=economic）；world 参照，与 world-settings 同族合并读取（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'system_name', 'book_source', 'world_type', 'currency_system', 'resource_types',
      'trade_patterns', 'price_anchoring', 'economic_tensions', 'class_and_economics', 'suitable_genres',
      'anti_patterns', 'quality_score'],
    jsonColumns: ['resource_types', 'trade_patterns', 'suitable_genres'],
    trimColumns: ['system_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_social_systems', disposition: 'export', idPrefix: 'kb:social',
    reason: '社会系统（kind=social）；world 参照，与 world-settings 同族合并读取（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'system_name', 'book_source', 'world_type', 'hierarchy_levels', 'social_rules',
      'daily_life_details', 'cultural_elements', 'status_symbols', 'mobility_pattern', 'suitable_genres',
      'anti_patterns', 'quality_score'],
    jsonColumns: ['hierarchy_levels', 'social_rules', 'suitable_genres'],
    trimColumns: ['system_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_faction_designs', disposition: 'export', idPrefix: 'kb:faction',
    reason: '势力设计（kind=faction）；world 参照，与 world-settings 同族合并读取（R4）',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'faction_name_pattern', 'book_source', 'faction_type', 'hierarchy_structure',
      'faction_goals', 'faction_resources', 'inter_faction_relations', 'reveal_pacing', 'narrative_function',
      'archetype', 'anti_patterns', 'quality_score'],
    jsonColumns: ['hierarchy_structure'],
    trimColumns: ['faction_name_pattern', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_character_archetypes', disposition: 'export', idPrefix: 'kb:archetype',
    reason: '人物原型；character 原型参照取材池（R4 后批）；book_source 仅 trim 不归并',
    filterSql: 'quality_score BETWEEN 8 AND 10',
    columns: ['id', 'archetype_name', 'book_source', 'character_role', 'personality_traits', 'background_pattern',
      'growth_arc', 'relationships_pattern', 'speech_pattern', 'narrative_function', 'pros_and_cons',
      'similar_characters', 'anti_patterns', 'quality_score'],
    jsonColumns: ['personality_traits', 'similar_characters'],
    trimColumns: ['archetype_name', 'book_source'],
    intColumns: ['id', 'quality_score'],
    sort: 'id',
  },
  {
    table: 'kb_worldbuilding_modules', disposition: 'export', idPrefix: 'kb:module',
    reason: '世界观构建模块（28 行全量）；world 参照（R4 后批接槽）',
    filterSql: null,
    columns: ['id', 'genre', 'module_name', 'badge_text', 'badge_priority', 'description', 'design_questions', 'design_prompt'],
    jsonColumns: ['design_questions'],
    trimColumns: ['module_name', 'genre'],
    intColumns: ['id', 'badge_priority'],
    sort: 'id',
  },
  {
    table: 'kb_corpus_tags', disposition: 'export', idPrefix: 'kb:tag',
    reason: '金丝雀选样标签字典（裁-4 必导）；双落 data/knowledge/kb_corpus_tags.json + data/canary/tags.json',
    filterSql: null,
    columns: ['id', 'tag_name', 'tag_type', 'description', 'keyword_patterns'],
    jsonColumns: ['keyword_patterns'],
    trimColumns: ['tag_name', 'tag_type'],
    intColumns: ['id'],
    canary: true,
    sort: 'id',
  },
  // —— 不导（7 张，逐条记理由） ——
  {
    table: 'kb_author_personas', disposition: 'skip', idPrefix: null, reason:
      '裁-5：版权红线优先于 staging 便利——personas 原始卡（含 author_name 5 变体等脏数据）由 D4 在 R5 轮走 MySQL 直连导入 12-16 条试点（ownership=\'style_seed\'）；'
      + 'D3 取消 staging 导出，author_name 归并预处理（刘慈欣 5 变体 6 条/前导空格「 Priest」/同作者多行 17 组）随之移交 D4，本脚本不做归并',
    filterSql: null, columns: [], jsonColumns: [], trimColumns: [], intColumns: [], sort: 'id',
  },
  {
    table: 'kb_corpus_articles', disposition: 'skip', idPrefix: null, reason:
      '裁-4/裁-5：人类语料原文（123 篇）不入本管道——由金丝雀选样执行员按 D2 装载器格式契约（data/canary/g{N}/*.md 分组）直连导出；jsonl 中间产物亦由选样执行员自持',
    filterSql: null, columns: [], jsonColumns: [], trimColumns: [], intColumns: [], sort: 'id',
  },
  {
    table: 'kb_corpus_excerpts', disposition: 'skip', idPrefix: null, reason:
      '裁-4/裁-5：同 kb_corpus_articles——选段原文由金丝雀选样执行员直连导出（436 段，article_id 关联），不落本脚本产物',
    filterSql: null, columns: [], jsonColumns: [], trimColumns: [], intColumns: [], sort: 'id',
  },
  {
    table: 'kb_worldbuilding_priority', disposition: 'skip', idPrefix: null, reason:
      '排序元数据表（genre×dimension×priority），信息已被 kb_worldbuilding_modules 覆盖，导出无消费方（计划 §2 裁决）',
    filterSql: null, columns: [], jsonColumns: [], trimColumns: [], intColumns: [], sort: 'id',
  },
  {
    table: 'kb_reusable_templates', disposition: 'skip', idPrefix: null, reason:
      'R5 计划既定暂不导：观察 knowledge 槽实际消耗后再定去留，防整表搬运（蒸馏不整表搬运红线）',
    filterSql: null, columns: [], jsonColumns: [], trimColumns: [], intColumns: [], sort: 'id',
  },
  {
    table: 'kb_memes', disposition: 'skip', idPrefix: null, reason:
      '梗百科登记表仅 3 行，非方法论知识源（计划 §2 裁决不导）',
    filterSql: null, columns: [], jsonColumns: [], trimColumns: [], intColumns: [], sort: 'id',
  },
  {
    table: 'kb_imported_files', disposition: 'skip', idPrefix: null, reason:
      '导入源文件登记表（source_file/imported_at/rows_inserted），无知识内容，仅审计用途',
    filterSql: null, columns: [], jsonColumns: [], trimColumns: [], intColumns: [], sort: 'id',
  },
];

const EXPORT_SPECS = TABLE_DISPOSITIONS.filter((s) => s.disposition === 'export');
const SPEC_BY_TABLE = new Map(TABLE_DISPOSITIONS.map((s) => [s.table, s]));
// R0 快照参考值：仅作 --verify 提示（不参与对账判定——对账一律以运行时 COUNT 为准）。
const R0_SNAPSHOT_HINTS = { kb_writing_techniques: 1310 };

// ── CLI ──────────────────────────────────────────────────────────────────
function usage() {
  return [
    '用法：',
    '  node scripts/novelos-import-knowledge.mjs --all                     # 导出全部 16 张导出表',
    '  node scripts/novelos-import-knowledge.mjs --table <name> [...]      # 导出指定表（可多次）',
    '  node scripts/novelos-import-knowledge.mjs --verify                  # 对现有产物做运行时 COUNT 行数对账',
    '选项：--out-dir data/knowledge  --canary-dir data/canary',
    '      --mysql-host 127.0.0.1  --mysql-port 3306  --mysql-user root  --mysql-db nwriter',
    '凭据：密码经 MYSQL_PWD 环境变量传入。',
    '23 张 kb_* 表处置清单见脚本头注释与 TABLE_DISPOSITIONS 注册表。',
  ].join('\n');
}

function parseCli() {
  let opts;
  try {
    ({ values: opts } = parseArgs({
      options: {
        table: { type: 'string', multiple: true },
        all: { type: 'boolean', default: false },
        verify: { type: 'boolean', default: false },
        'out-dir': { type: 'string', default: 'data/knowledge' },
        'canary-dir': { type: 'string', default: 'data/canary' },
        'mysql-host': { type: 'string', default: '127.0.0.1' },
        'mysql-port': { type: 'string', default: '3306' },
        'mysql-user': { type: 'string', default: 'root' },
        'mysql-db': { type: 'string', default: 'nwriter' },
        help: { type: 'boolean', default: false },
      },
      strict: true,
    }));
  } catch (e) {
    fail(2, `CLI 参数错误：${e.message}\n${usage()}`);
  }
  if (opts.help || (!opts.all && !opts.verify && (opts.table ?? []).length === 0)) fail(2, usage());
  if (opts.all && (opts.table ?? []).length > 0) fail(2, '--all 与 --table 互斥\n' + usage());
  return opts;
}

function fail(code, msg) {
  console.error(msg);
  process.exit(code);
}

// ── MySQL TSV 导出（只读） ───────────────────────────────────────────────
function mysqlClient(opts) {
  if (!process.env.MYSQL_PWD) {
    fail(1, 'MYSQL_PWD 未设置——密码须经环境变量传入（不进 argv/代码/日志）。示例：export MYSQL_PWD=\'…\' && node scripts/novelos-import-knowledge.mjs --all');
  }
  return (sql) => {
    const r = spawnSync('mysql', [
      '-B', '-N', '--default-character-set=utf8mb4',
      '-h', opts['mysql-host'], '-P', opts['mysql-port'], '-u', opts['mysql-user'],
      opts['mysql-db'], '-e', sql,
    ], { env: { ...process.env }, encoding: 'utf8', maxBuffer: 256 * 1024 * 1024, timeout: 120_000 });
    if (r.error) fail(1, `mysql 启动失败：${r.error.message}`);
    if (r.status !== 0) fail(1, `mysql 退出码 ${r.status}：${(r.stderr || '').trim()}`);
    return r.stdout ?? '';
  };
}

// NULL 哨兵：SQL 侧 IFNULL(col, CHAR(92,78)) 输出两字符 `\N`；字符串值 'NULL' 因此不与真 NULL 混淆。
const NULL_SENTINEL = '\\N';

function unescapeField(s) {
  if (!s.includes('\\')) return s;
  let out = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === '\\' && i + 1 < s.length) {
      const n = s[++i];
      switch (n) {
        case '0': out += '\0'; break;
        case 'b': out += '\b'; break;
        case 'n': out += '\n'; break;
        case 'r': out += '\r'; break;
        case 't': out += '\t'; break;
        case 'Z': out += '\x1a'; break;
        default: out += n; break; // \\ → \，\' → ' 等
      }
    } else {
      out += c;
    }
  }
  return out;
}

function parseTsv(tsv) {
  const lines = tsv.split('\n');
  if (lines.length && lines[lines.length - 1] === '') lines.pop();
  return lines
    .filter((l) => l.length > 0)
    .map((line) => line.split('\t').map((raw) => (raw === NULL_SENTINEL ? null : unescapeField(raw))));
}

const qid = (name) => `\`${name}\``;

function countsSql(spec) {
  const total = `SELECT COUNT(*) FROM ${qid(spec.table)}`;
  if (!spec.filterSql) return total;
  return `SELECT COUNT(*) FROM ${qid(spec.table)}; SELECT COUNT(*) FROM ${qid(spec.table)} WHERE ${spec.filterSql}`;
}

function readCounts(runSql, spec) {
  const out = runSql(countsSql(spec)).trim();
  const nums = out.split('\n').map((l) => Number(l.trim()));
  if (spec.filterSql) {
    if (nums.length !== 2 || nums.some((n) => !Number.isFinite(n))) fail(1, `${spec.table}: COUNT 对账查询返回异常`);
    return { total: nums[0], filtered: nums[1] };
  }
  if (!Number.isFinite(nums[0])) fail(1, `${spec.table}: COUNT 对账查询返回异常`);
  return { total: nums[0], filtered: nums[0] };
}

function exportSql(spec) {
  const cols = spec.columns.map((c) => `IFNULL(${qid(c)}, CHAR(92,78)) AS ${qid(c)}`).join(', ');
  let sql = `SELECT ${cols} FROM ${qid(spec.table)}`;
  if (spec.filterSql) sql += ` WHERE ${spec.filterSql}`;
  sql += ' ORDER BY ' + qid('id');
  return sql;
}

// ── 清洗 ─────────────────────────────────────────────────────────────────
function toNumber(v) {
  if (v === null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : v; // 怪异数值保真为原字符串，不丢行
}

// JSON-in-text：仅当 trim 后以 '[' 或 '{' 开头才尝试解析；形似 JSON 但解析失败 → 原字符串 + parse_error。
function cleanJsonCol(raw, col, spec, rowId, parseErrors) {
  if (raw === null) return { value: null };
  const t = raw.trim();
  if (t === '') return { value: null };
  if (t[0] !== '[' && t[0] !== '{') return { value: raw };
  try {
    return { value: JSON.parse(t) };
  } catch {
    parseErrors.push({ id: rowId, col });
    return { value: raw, parseError: true };
  }
}

// dup_key 归一（红方 P1-8）：NFKC 全半角统一 → 去全部空白 → 循环去末尾括号后缀。不做大小写折叠。
function normalizeDupKeyPart(v) {
  if (v === null || v === undefined) return '';
  let s = String(v).normalize('NFKC');
  s = s.replace(/\s+/g, '');
  let prev;
  do {
    prev = s;
    s = s.replace(/[（(【\[][^（）()【】\[\]]*[）)】\]]$/u, '');
  } while (s !== prev);
  return s;
}

function computeDupKey(spec, row) {
  if (!spec.dupKeyFields) return undefined;
  return spec.dupKeyFields.map((f) => normalizeDupKeyPart(row[f])).join('::');
}

function cmpStr(x, y) {
  const a = x ?? '';
  const b = y ?? '';
  return a < b ? -1 : a > b ? 1 : 0;
}

function sortItems(spec, items) {
  if (spec.sort === 'category,dup_key,id') {
    // dup_key 主导（见头注释）：先 dup_key 聚类、再 category、最后 orig_id——保证同 key 全局相邻。
    items.sort((a, b) => cmpStr(a.dup_key, b.dup_key) || cmpStr(a.category, b.category) || (a.orig_id - b.orig_id));
  } else {
    items.sort((a, b) => a.orig_id - b.orig_id);
  }
}

// ── 单表导出 ─────────────────────────────────────────────────────────────
function exportTable(spec, opts, runSql, outDir, exportedAt) {
  const { total, filtered } = readCounts(runSql, spec);
  const rows = parseTsv(runSql(exportSql(spec)));
  if (rows.length !== filtered) {
    fail(1, `${spec.table}: TSV 行数 ${rows.length} ≠ COUNT(filtered) ${filtered}——导出与对账口径不一致，中止`);
  }

  const parseErrors = [];
  const items = rows.map((cells) => {
    const row = {};
    spec.columns.forEach((col, i) => {
      row[col] = cells[i];
    });
    const origId = toNumber(row.id);
    const item = {};
    // 溯源三件套（每条必备）
    item.id = `${spec.idPrefix}:${origId}`;
    item.orig_id = origId;
    item.book_source = row.book_source !== undefined ? row.book_source : null;
    item.exported_at = exportedAt;
    // 业务字段（保序清洗）
    for (const col of spec.columns) {
      if (col === 'id' || col === 'book_source') continue;
      let v = row[col];
      if (spec.trimColumns.includes(col) && typeof v === 'string') v = v.trim();
      if (spec.intColumns.includes(col)) v = toNumber(v);
      if (spec.jsonColumns.includes(col) || (spec.jsonObjColumns ?? []).includes(col)) {
        const { value, parseError } = cleanJsonCol(v, col, spec, origId, parseErrors);
        v = value;
        if (parseError) item[`${col}_parse_error`] = true;
      }
      item[col] = v;
    }
    const dk = computeDupKey(spec, item);
    if (dk !== undefined) item.dup_key = dk;
    if (spec.filterSql) item.norm_score = item.quality_score; // 裁-6：仅排序辅助字段保留，不参与过滤
    return item;
  });

  sortItems(spec, items);

  const meta = {
    schema_version: 1,
    source_table: spec.table,
    source: { host: opts['mysql-host'], port: opts['mysql-port'], user: opts['mysql-user'], database: opts['mysql-db'] },
    source_rows: total,
    exported_rows: items.length,
    filter: spec.filterSql ?? '全量（无 quality 过滤）',
    filter_note: spec.filterSql
      ? '裁-6：原始 quality_score BETWEEN 8 AND 10（SQL 侧过滤）；0-100 刻度行整段排除不混入；norm_score 仅作排序辅助字段保留'
      : '无 quality 过滤（该表全量导出）',
    dropped_rows: spec.filterSql ? { q_filter: total - items.length } : {},
    columns: spec.columns,
    json_columns: [...(spec.jsonColumns ?? []), ...(spec.jsonObjColumns ?? [])],
    dropped_columns: spec.droppedColumns ?? [],
    sort: spec.sort === 'category,dup_key,id' ? 'dup_key, category, id（dup_key 主导保证同 key 相邻——同 key 条目 category 实测发散，字面 category 优先序无法兑现相邻契约；供蒸馏同批聚类）' : 'id 升序',
    parse_errors: parseErrors,
    provenance: '溯源契约：每条 item 必备 id（kb:<域>:<orig_id>）/ orig_id / book_source / exported_at',
    disposition: spec.reason,
    exported_at: exportedAt,
    idempotency_note: 'exported_at 为 UTC 日期粒度；同库状态下同日重跑字节一致（--verify 运行时 COUNT 对账）',
    git_note: '裁-5：原始拆解数据（真书名/原文例句/拆书文本）落 data/（gitignore），不进 git；config/knowledge/ 仅放蒸馏产物',
  };
  const doc = { meta, items };
  const file = join(outDir, `${spec.table}.json`);
  writeFileSync(file, JSON.stringify(doc, null, 2) + '\n', 'utf8');

  if (spec.canary) writeCanaryTags(doc, opts, exportedAt);

  const dupKeyInfo = spec.dupKeyFields
    ? `  dup_key 组数=${new Set(items.map((i) => i.dup_key)).size}`
    : '';
  console.log(
    `[export] ${spec.table}  source=${total}  exported=${items.length}` +
      (spec.filterSql ? `  dropped(q_filter)=${total - items.length}` : '  (全量)') +
      `  parse_errors=${parseErrors.length}${dupKeyInfo}`,
  );
  return { spec, total, items, parseErrors };
}

function writeCanaryTags(doc, opts, exportedAt) {
  const typeCounts = {};
  for (const t of doc.items) {
    const k = t.tag_type ?? '(null)';
    typeCounts[k] = (typeCounts[k] ?? 0) + 1;
  }
  const canary = {
    meta: {
      schema_version: 1,
      purpose: '金丝雀选样标签字典（裁-4：按标签覆盖频道轴选样；消费方=D1 选样/D2 装载器）',
      source_table: doc.meta.source_table,
      source: doc.meta.source,
      rows: doc.items.length,
      type_counts: typeCounts,
      exported_at: exportedAt,
      git_note: 'data/canary/ 已 gitignore；本文件与 data/knowledge/kb_corpus_tags.json 同源同内容口径',
    },
    tags: doc.items,
  };
  const file = join(opts['canary-dir'], 'tags.json');
  writeFileSync(file, JSON.stringify(canary, null, 2) + '\n', 'utf8');
  console.log(`[canary] ${file}  tags=${doc.items.length}  types=${Object.keys(typeCounts).length}`);
}

// ── --verify：运行时 COUNT 对账（不写死数字） ────────────────────────────
function verify(opts, runSql) {
  const outDir = resolve(REPO_ROOT, opts['out-dir']);
  const problems = [];
  const report = [];
  const exportedAt = new Date().toISOString().slice(0, 10);

  const techniquesSpec = SPEC_BY_TABLE.get('kb_writing_techniques');
  const exportedTechIds = new Set();
  const techFile = join(outDir, `${techniquesSpec.table}.json`);
  if (existsSync(techFile)) {
    for (const it of JSON.parse(readFileSync(techFile, 'utf8')).items ?? []) exportedTechIds.add(it.orig_id);
  }

  for (const spec of EXPORT_SPECS) {
    const file = join(outDir, `${spec.table}.json`);
    if (!existsSync(file)) {
      problems.push(`${spec.table}: 产物缺失 ${file}`);
      continue;
    }
    const doc = JSON.parse(readFileSync(file, 'utf8'));
    const items = doc.items ?? [];
    const meta = doc.meta ?? {};
    const { total, filtered } = readCounts(runSql, spec);

    if (meta.source_rows !== total) problems.push(`${spec.table}: meta.source_rows=${meta.source_rows} ≠ 运行时 COUNT(*)=${total}`);
    if (items.length !== filtered) problems.push(`${spec.table}: items.length=${items.length} ≠ 运行时 COUNT(filter)=${filtered}`);
    if (meta.exported_rows !== items.length) problems.push(`${spec.table}: meta.exported_rows=${meta.exported_rows} ≠ items.length=${items.length}`);

    let provMissing = 0;
    for (const it of items) {
      if (typeof it.orig_id !== 'number' || !('book_source' in it) || typeof it.exported_at !== 'string') provMissing++;
    }
    if (provMissing > 0) problems.push(`${spec.table}: ${provMissing} 条缺溯源三件套（orig_id/book_source/exported_at）`);

    const itemErrCount = items.reduce((n, it) => n + Object.keys(it).filter((k) => k.endsWith('_parse_error')).length, 0);
    const metaErrCount = (meta.parse_errors ?? []).length;
    if (itemErrCount !== metaErrCount) problems.push(`${spec.table}: 条目级 _parse_error 标记数 ${itemErrCount} 与 meta.parse_errors ${metaErrCount} 不一致`);
    const parseErrCount = itemErrCount;

    let dupAdjacent = null;
    if (spec.sort === 'category,dup_key,id') {
      const seen = new Map();
      let bad = 0;
      for (let i = 0; i < items.length; i++) {
        const k = items[i].dup_key;
        if (seen.has(k) && seen.get(k) !== i - 1) bad++;
        seen.set(k, i);
      }
      dupAdjacent = bad === 0;
      if (bad > 0) problems.push(`${spec.table}: ${bad} 处 dup_key 不相邻（排序契约破坏）`);
    }

    const specLines = [];
    if (spec.refCheck) {
      const refIds = new Set();
      for (const it of items) {
        const refs = it[spec.refCheck.column];
        if (Array.isArray(refs)) for (const r of refs) refIds.add(Number(r));
      }
      const existing = new Set();
      const idList = [...refIds].filter((n) => Number.isFinite(n));
      for (let i = 0; i < idList.length; i += 500) {
        const batch = idList.slice(i, i + 500).join(',');
        for (const line of runSql(`SELECT id FROM ${qid(spec.refCheck.refTable)} WHERE id IN (${batch})`).split('\n')) {
          const n = Number(line.trim());
          if (Number.isFinite(n)) existing.add(n);
        }
      }
      const dead = [...refIds].filter((n) => !existing.has(n));
      const outOfFilter = [...refIds].filter((n) => existing.has(n) && !exportedTechIds.has(n));
      if (dead.length > 0) specLines.push(`  [ref] ${spec.table}.${spec.refCheck.column}: 死引用 ${dead.length} 个（源表无此 id）`);
      specLines.push(`  [ref] ${spec.table}.${spec.refCheck.column}: 引用 ${refIds.size} 个 id，源表存在 ${existing.size}，其中已入 quality 过滤导出集 ${existing.size - outOfFilter.length}（过滤外失联 ${outOfFilter.length}——预期，蒸馏/槽检索层处理）`);
    }

    if (spec.canary) {
      const canaryFile = join(resolve(REPO_ROOT, opts['canary-dir']), 'tags.json');
      if (!existsSync(canaryFile)) {
        problems.push(`${spec.table}: canary 产物缺失 ${canaryFile}`);
      } else {
        const c = JSON.parse(readFileSync(canaryFile, 'utf8'));
        if ((c.tags ?? []).length !== items.length) problems.push(`${spec.table}: canary tags 行数 ${(c.tags ?? []).length} ≠ 主产物 ${items.length}`);
      }
    }

    const hint = R0_SNAPSHOT_HINTS[spec.table];
    const hintTxt = hint !== undefined && items.length !== hint ? `  ⚠ 与 R0 快照参考值 ${hint} 偏离（库可能已变化，仅提示）` : hint !== undefined ? `  (R0 快照参考值 ${hint} ✓)` : '';
    report.push(`[ok] ${spec.table}  file_rows=${items.length}  runtime_count(filter)=${filtered}  runtime_count(*)=${total}  parse_errors=${parseErrCount}${dupAdjacent === null ? '' : `  dup_key 相邻=${dupAdjacent ? '✓' : '✗'}`}${hintTxt}`);
    report.push(...specLines);
  }

  // dup_key 聚类抽查：取重数最高的 3 组（仅供人工抽查相邻性，不含正文内容）
  const techDoc = existsSync(techFile) ? JSON.parse(readFileSync(techFile, 'utf8')) : null;
  if (techDoc) {
    const groups = new Map();
    for (const it of techDoc.items ?? []) {
      if (!groups.has(it.dup_key)) groups.set(it.dup_key, []);
      groups.get(it.dup_key).push(it.orig_id);
    }
    const top3 = [...groups.entries()].filter(([, ids]) => ids.length > 1)
      .sort((a, b) => b[1].length - a[1].length).slice(0, 3);
    for (const [k, ids] of top3) {
      const idxs = (techDoc.items ?? []).map((it, i) => (it.dup_key === k ? i : -1)).filter((i) => i >= 0);
      const contiguous = idxs.every((v, i) => i === 0 || v === idxs[i - 1] + 1);
      report.push(`  [dup] dup_key=${k}  ids=[${ids.join(', ')}]  行号相邻=${contiguous ? '✓' : '✗'}`);
      if (!contiguous) problems.push(`kb_writing_techniques: dup_key「${k}」条目不相邻`);
    }
  }

  console.log('—— verify 对账（全部以运行时 COUNT 为准） ——');
  for (const line of report) console.log(line);
  if (problems.length > 0) {
    console.error('\n—— FAIL ——');
    for (const p of problems) console.error(`  ✗ ${p}`);
    fail(1, `verify 失败：${problems.length} 项问题`);
  }
  console.log('\nverify 全绿 ✓');
}

// ── main ─────────────────────────────────────────────────────────────────
function main() {
  const opts = parseCli();
  const runSql = mysqlClient(opts);
  const exportedAt = new Date().toISOString().slice(0, 10);

  if (opts.verify) {
    verify(opts, runSql);
    return;
  }

  let specs;
  if (opts.all) {
    specs = EXPORT_SPECS;
  } else {
    specs = (opts.table ?? []).map((t) => {
      const spec = SPEC_BY_TABLE.get(t);
      if (!spec) fail(2, `未知表「${t}」——可选导出表：\n  ${EXPORT_SPECS.map((s) => s.table).join('\n  ')}\n（23 张 kb_* 全处置清单见脚本头注释）`);
      if (spec.disposition === 'skip') fail(1, `表「${t}」登记为不导——理由：${spec.reason}`);
      return spec;
    });
  }

  const outDir = resolve(REPO_ROOT, opts['out-dir']);
  mkdirSync(outDir, { recursive: true });
  mkdirSync(resolve(REPO_ROOT, opts['canary-dir']), { recursive: true });

  const started = process.hrtime.bigint();
  let contentHashInput = '';
  for (const spec of specs) {
    const r = exportTable(spec, opts, runSql, outDir, exportedAt);
    contentHashInput += `${spec.table}:${r.items.length};`;
  }
  const ms = Number(process.hrtime.bigint() - started) / 1e6;
  const batchSha = createHash('sha256').update(contentHashInput).digest('hex').slice(0, 12);
  console.log(`\ndone: ${specs.length} 张表 → ${outDir}${specs.some((s) => s.canary) ? ` + ${opts['canary-dir']}/tags.json` : ''}  (${ms.toFixed(0)}ms, batch=${batchSha}, exported_at=${exportedAt})`);
  console.log('版权注记：产物均为原始拆解数据，落 data/（gitignore），不进 git、不打印正文。');
}

main();
