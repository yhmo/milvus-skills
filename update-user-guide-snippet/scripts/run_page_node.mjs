#!/usr/bin/env node
// Run the javascript snippets of a user-guide page against a live Milvus server.
//
// Extracts every ```javascript block, hoists the imports from the first block to
// the top (ESM), concatenates the block bodies in order inside one async main(),
// and runs it with node. Reports pass/fail per block and exits non-zero on any
// failure.
//
// Usage: node run_page_node.mjs <page.md>
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const page = process.argv[2];
// repo root = scripts dir is <repo>/update-user-guide-snippet/scripts -> up 2
const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.join(here, '..', '..');
const runDir = path.join(repo, 'sdk-tmp', 'snippet-run', 'node');
fs.mkdirSync(runDir, { recursive: true });
const runFile = path.join(runDir, 'run_page_node_run.mjs');

const md = fs.readFileSync(page, 'utf8');
const blocks = [...md.matchAll(/```javascript\n([\s\S]*?)```/g)].map(m => m[1]);

// hoist ALL unique imports from every block (ESM requires them at the top).
// Merge duplicate imports of the same module: `import { A }` + `import { A, B }`
// must collapse to `import { A, B }` instead of being emitted twice (repeated
// declarations are a SyntaxError). Whole-line dedup alone misses that.
const importMap = new Map(); // module -> Set of named bindings (or '' for default)
const bodies = blocks.map(b => {
  const kept = [];
  for (const line of b.split('\n')) {
    const m = /^\s*import\s+\{([^}]*)\}\s+from\s+['"]([^'"]+)['"]/.exec(line);
    if (m) {
      const bindings = m[1].split(',').map(s => s.trim()).filter(Boolean);
      const mod = m[2];
      if (!importMap.has(mod)) importMap.set(mod, new Set());
      for (const bnd of bindings) importMap.get(mod).add(bnd);
      continue;
    }
    const dm = /^\s*import\s+['"]([^'"]+)['"]/.exec(line);
    if (dm) {
      if (!importMap.has(dm[1])) importMap.set(dm[1], new Set());
      continue;
    }
    const dm2 = /^\s*import\s+(\w+)\s+from\s+['"]([^'"]+)['"]/.exec(line);
    if (dm2) {
      if (!importMap.has(dm2[2])) importMap.set(dm2[2], new Set());
      continue;
    }
    kept.push(line);
  }
  return kept.join('\n');
});
const imports = [...importMap.entries()].map(([mod, bindings]) => {
  if (bindings.size === 0) return `import '${mod}';`;
  return `import { ${[...bindings].join(', ')} } from '${mod}';`;
});

// strip per-block client init so one shared client is created in main()
const stripped = bodies.map(b =>
  b.replace(/const\s+client\s*=\s*new\s+MilvusClient\([\s\S]*?\);/g, '')
    .replace(/\bconst\s+/g, 'var ')
    .replace(/\blet\s+/g, 'var ')
);

const prog =
  [...imports].join('\n') +
  '\n\nasync function main() {\n' +
  '  const client = new MilvusClient({ address: "http://localhost:19530", token: "root:Milvus" });\n' +
  stripped
    .map((b, i) => `  // === block ${i} ===\n${b
        .split('\n')
        .map(l => '    ' + l)
        .join('\n')}`)
    .join('\n\n') +
  '\n}\n' +
  'main()\n' +
  "  .then(() => { console.log('ALL BLOCKS OK'); process.exit(0); })\n" +
  "  .catch(e => { console.error('FAILED:', e.message); process.exit(1); });\n";

fs.writeFileSync(runFile, prog);
console.log(`blocks: ${blocks.length}`);
try {
  const { execFileSync } = await import('child_process');
  execFileSync('node', [runFile], { stdio: 'inherit' });
} catch (e) {
  process.exit(e.status || 1);
} finally {
  try {
    fs.rmSync(runFile, { force: true });
  } catch {}
}
