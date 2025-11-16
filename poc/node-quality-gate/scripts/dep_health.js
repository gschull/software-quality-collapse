#!/usr/bin/env node
/**
 * Basic dependency health check (warnings only):
 * - Uses package-lock.json to get exact versions (if present)
 * - Queries OSV.dev for known vulns for each dependency@version
 * - Queries npm registry for publish times to compute version age
 * - Prints a summary and non-zero WARN counts, but exits 0
 */

const fs = require('fs');
const path = require('path');

const OSV_API = 'https://api.osv.dev/v1/query';
const NPM_REG = 'https://registry.npmjs.org';

async function queryOSV(pkgName, version) {
  try {
    const res = await fetch(OSV_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        version,
        package: { ecosystem: 'npm', name: pkgName }
      })
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.vulns || [];
  } catch {
    return [];
  }
}

async function getVersionAgeDays(pkgName, version) {
  try {
    const res = await fetch(`${NPM_REG}/${encodeURIComponent(pkgName)}`);
    if (!res.ok) return null;
    const data = await res.json();
    const time = data.time || {};
    const published = time[version];
    if (!published) return null;
    const days = (Date.now() - new Date(published).getTime()) / (1000 * 60 * 60 * 24);
    return Math.floor(days);
  } catch {
    return null;
  }
}

function readLockDeps(lockPath) {
  if (!fs.existsSync(lockPath)) return [];
  const lock = JSON.parse(fs.readFileSync(lockPath, 'utf-8'));
  const deps = [];
  const depMap = lock.packages || {}; // npm v7+ lockfileVersion 2
  for (const [key, meta] of Object.entries(depMap)) {
    if (!key || key === '') continue; // root
    if (!meta.version) continue;
    // key is like node_modules/pkg
    const parts = key.split('node_modules/');
    const pkg = parts[parts.length - 1];
    if (!pkg || pkg.startsWith('@types/')) continue; // skip @types
    deps.push({ name: pkg, version: meta.version });
  }
  return deps;
}

(async () => {
  const root = process.cwd();
  const lockPath = path.join(root, 'package-lock.json');
  const pkgPath = path.join(root, 'package.json');

  if (!fs.existsSync(pkgPath)) {
    console.warn('No package.json found; skipping dep health');
    process.exit(0);
  }

  const deps = readLockDeps(lockPath);
  if (deps.length === 0) {
    console.warn('No dependencies found from package-lock.json; skipping OSV checks');
  }

  let vulnWarns = 0;
  let ageWarns = 0;
  const AGE_THRESHOLD_DAYS = parseInt(process.env.DEP_AGE_WARN_DAYS || '730', 10); // ~2 years
  const FAIL_ON_VULNS = String(process.env.DEP_FAIL_ON_VULNS || 'false').toLowerCase() === 'true';
  const FAIL_ON_AGE = String(process.env.DEP_FAIL_ON_AGE || 'false').toLowerCase() === 'true';
  const MAX_VULN_WARN = process.env.DEP_MAX_VULN_WARN ? parseInt(process.env.DEP_MAX_VULN_WARN, 10) : null;
  const MAX_AGE_WARN = process.env.DEP_MAX_AGE_WARN ? parseInt(process.env.DEP_MAX_AGE_WARN, 10) : null;

  console.log('Dependency Health Check (warnings only)');
  console.log('------------------------------------------------');

  for (const { name, version } of deps.slice(0, 200)) { // cap to 200 for speed
    const [vulns, ageDays] = await Promise.all([
      queryOSV(name, version),
      getVersionAgeDays(name, version)
    ]);

    if (vulns && vulns.length > 0) {
      vulnWarns += 1;
      console.warn(`WARN: ${name}@${version} has ${vulns.length} known vulnerability entries in OSV`);
    }
    if (ageDays != null && ageDays > AGE_THRESHOLD_DAYS) {
      ageWarns += 1;
      console.warn(`WARN: ${name}@${version} is ${ageDays} days old (> ${AGE_THRESHOLD_DAYS})`);
    }
  }

  console.log('------------------------------------------------');
  console.log(`Summary: OSV warnings=${vulnWarns}, Age warnings=${ageWarns}`);

  let shouldFail = false;
  if (FAIL_ON_VULNS && vulnWarns > 0) shouldFail = true;
  if (FAIL_ON_AGE && ageWarns > 0) shouldFail = true;
  if (MAX_VULN_WARN != null && vulnWarns > MAX_VULN_WARN) shouldFail = true;
  if (MAX_AGE_WARN != null && ageWarns > MAX_AGE_WARN) shouldFail = true;

  if (shouldFail) {
    console.error('Dependency health gating failed based on configured thresholds.');
    process.exit(1);
  }

  process.exit(0);
})();
