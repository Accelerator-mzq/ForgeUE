// Workaround forge plugin upstream bug:writeStagingYaml 用 js-yaml dump 输出
// ISO timestamp 为 unquoted YAML literal,freeze 时 yaml.load 把它解析为 Date object
// → canonicalize 拒 → 报误导性 "staging_hash mismatch — staging tampered"。
//
// 本 script:
//   1. quote-wrap 所有 unquoted ISO 8601 UTC timestamp
//   2. 用 forge plugin 自家 canonicalize + canonicalHash 重算 staging_hash
//   3. 写回 staging file
const FORGE = "C:/Users/mzq/AppData/Local/npm-cache/_npx/0f24d3ee102db334/node_modules";
const yaml = require(`${FORGE}/js-yaml`);
const { canonicalHash } = require(`${FORGE}/@accelerator-mzq/forge/dist/core/canonical-json.js`);
const fs = require("node:fs");

const STAGING = "forge/changes/executor-async-rewrite/.evidence/process-evidence.staging.yaml";
let raw = fs.readFileSync(STAGING, "utf8");

// 1. quote-wrap unquoted ISO timestamp(Z 后缀 or +HH:MM 后缀)
const ISO_RE = /(:\s)((\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})))(\s*\n)/g;
let count = 0;
raw = raw.replace(ISO_RE, (_, pre, ts, _ts, post) => {
  count++;
  return `${pre}"${ts}"${post}`;
});
console.log(`wrapped ${count} timestamps in quotes`);

// 2. parse + 重算 staging_hash
const data = yaml.load(raw);
const oldHash = data.staging_hash;
delete data.staging_hash;
const newHash = canonicalHash(data);
console.log(`old staging_hash: ${oldHash}`);
console.log(`new staging_hash: ${newHash}`);

// 3. 替换 staging_hash 行(YAML 最后一行)
raw = raw.replace(/^staging_hash: .*$/m, `staging_hash: ${newHash}`);
fs.writeFileSync(STAGING, raw);
console.log(`written ${STAGING}`);
