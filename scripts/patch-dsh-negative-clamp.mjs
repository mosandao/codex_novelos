// patch-dsh-negative-clamp.mjs — DSH 版本更新后一键重打投影负值补丁
// 背景：DSH 更新会覆盖 node_modules 补丁，导致 history unavailable ... too_small(messageTokens) 复发。
// 用法：node "D:\github\codex_novelos\scripts\patch-dsh-negative-clamp.mjs"（改完需重启 GUI 生效）
import fs from 'node:fs';
import path from 'node:path';

const BASE = 'D:\\Program Files\\DSH Desktop\\dsh-desktop\\node_modules\\@deepseek-ai';
const edits = [
  {
    file: path.join(BASE, 'dsh-token-meter', 'lib', 'index.js'),
    subs: [
      ['surfaceTokens: next.surfaceTokens + fold.deltaTokens',
       'surfaceTokens: Math.max(0, next.surfaceTokens + fold.deltaTokens)'],
      ['messageTokens: state.messageTokens + fold.deltaTokens,',
       'messageTokens: Math.max(0, state.messageTokens + fold.deltaTokens),'],
    ],
  },
  {
    file: path.join(BASE, 'dsh-token-meter', 'lib', 'types', 'breakdown-projection.js'),
    subs: [
      ['messageTokens: state.messageTokens + fold.deltaTokens,',
       'messageTokens: Math.max(0, state.messageTokens + fold.deltaTokens),'],
    ],
  },
  {
    file: path.join(BASE, 'dsh-token-meter', 'lib', 'types', 'usage-projection.js'),
    subs: [
      ['surfaceTokens: next.surfaceTokens + fold.deltaTokens',
       'surfaceTokens: Math.max(0, next.surfaceTokens + fold.deltaTokens)'],
    ],
  },
  {
    // fail-soft：restore() 损坏检查点行降级为全量重折叠
    file: path.join(BASE, 'dsh-session-projection', 'lib', 'index.js'),
    subs: [
      [`			const usable = row !== void 0 && row.ver === def.stateVersion && row.seq >= baseSeq - 1 && row.seq <= endSeq;
			if (!usable && baseSeq > 0) throw`,
       `			let usable = row !== void 0 && row.ver === def.stateVersion && row.seq >= baseSeq - 1 && row.seq <= endSeq;
			let parsedState;
			if (usable) try {
				parsedState = def.stateSchema.parse(row.val);
			} catch {
				usable = false;
			}
			if (!usable && baseSeq > 0) throw`],
      ['let state = usable ? def.stateSchema.parse(row.val) : def.init();',
       'let state = usable ? parsedState : def.init();'],
      [`				state = def.stateSchema.parse(row.val);
			} catch {
				continue;
			}
			values[def.key] = def.wire.viewSchema.parse(def.wire.view(state));`,
       `				state = def.stateSchema.parse(row.val);
			} catch {
				continue;
			}
			try {
				values[def.key] = def.wire.viewSchema.parse(def.wire.view(state));
			} catch {
				continue;
			}`],
    ],
  },
];

let failed = 0;
for (const { file, subs } of edits) {
  if (!fs.existsSync(file)) { console.log(`MISSING: ${file}`); failed++; continue; }
  let src = fs.readFileSync(file, 'utf8');
  let changed = false;
  for (const [from, to] of subs) {
    if (src.includes(to)) continue; // 已打
    if (!src.includes(from)) { console.log(`PATTERN NOT FOUND in ${path.basename(file)}:\n  ${from.split('\n')[0].trim()}...`); failed++; continue; }
    src = src.split(from).join(to);
    changed = true;
  }
  if (changed) {
    fs.copyFileSync(file, file + '.preclamp-bak');
    fs.writeFileSync(file, src);
    console.log(`PATCHED: ${file}`);
  } else {
    console.log(`ALREADY OK: ${file}`);
  }
}
console.log(failed ? `DONE WITH ${failed} ISSUE(S)` : 'ALL PATCHES APPLIED');
