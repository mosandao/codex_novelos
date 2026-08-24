// fix-dsh-projcache.mjs — 修复 DSH session_projcache.json 中投影折叠产生的负 token 值
// 用法：在 **完全关闭 DSH Desktop GUI 之后** 运行：node scripts/fix-dsh-projcache.mjs
// 背景：surface replace 结算 deltaTokens 可为负，累计跌破 0 会持久化非法状态，
//       导致冷加载报 history unavailable ... too_small(messageTokens)。
//       运行中的 host 会把内存态回写覆盖本脚本的修改，故必须在 GUI 关闭后执行。
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const p = path.join(os.homedir(), '.dsh', 'storages', 'session_projcache.json');
const j = JSON.parse(fs.readFileSync(p, 'utf8'));

const bak = `${p}.bak-${new Date().toISOString().replace(/[:.]/g, '-')}`;
fs.copyFileSync(p, bak);
console.log('backup:', bak);

let fixed = 0;
const touched = [];
for (const [sid, entry] of Object.entries(j.tables?.sessions ?? {})) {
  for (const [key, row] of Object.entries(entry.rows ?? {})) {
    const v = row?.val;
    if (!v) continue;
    let hit = false;
    if (typeof v.messageTokens === 'number' && v.messageTokens < 0) { v.messageTokens = 0; hit = true; }
    if (typeof v.surfaceTokens === 'number' && v.surfaceTokens < 0) { v.surfaceTokens = 0; hit = true; }
    if (hit) { fixed++; touched.push(`${sid} ${key}`); }
  }
}
fs.writeFileSync(p, JSON.stringify(j));
console.log(`clamped fields: ${fixed}`);
if (touched.length) console.log(touched.map(s => '  - ' + s).join('\n'));

// 复核
const check = JSON.parse(fs.readFileSync(p, 'utf8'));
let neg = 0;
for (const e of Object.values(check.tables?.sessions ?? {}))
  for (const row of Object.values(e.rows ?? {})) {
    const v = row?.val;
    if (v && ((v.messageTokens ?? 0) < 0 || (v.surfaceTokens ?? 0) < 0)) neg++;
  }
console.log('remaining negatives:', neg);
process.exit(neg ? 1 : 0);
