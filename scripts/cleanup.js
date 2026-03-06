/**
 * QAForge Demo Cleanup Script
 *
 * Removes test cases and test plans created during demo runs,
 * keeping the original baseline data intact.
 *
 * Usage:
 *   node cleanup.js                    # Preview what will be deleted (dry run)
 *   node cleanup.js --confirm          # Actually delete
 *   node cleanup.js --after 2026-03-06 # Delete everything created after this date
 *   node cleanup.js --keep 25          # Keep the oldest N test cases, delete the rest
 *
 * Default: deletes test cases created after the baseline date (2026-03-05)
 */

const https = require('https');

const BASE = 'https://qaforge.freshgravity.net/api/agent';
const KEY = 'qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG';

// Baseline: everything created on or before this date is kept
const DEFAULT_BASELINE = '2026-03-05';

const args = process.argv.slice(2);
const confirm = args.includes('--confirm');
const afterIdx = args.indexOf('--after');
const keepIdx = args.indexOf('--keep');
const baselineDate = afterIdx !== -1 ? args[afterIdx + 1] : DEFAULT_BASELINE;
const keepCount = keepIdx !== -1 ? parseInt(args[keepIdx + 1]) : null;

function apiCall(method, path, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(`${BASE}${path}`);
    const options = {
      method,
      hostname: url.hostname,
      path: url.pathname + url.search,
      headers: {
        'X-Agent-Key': KEY,
        'Content-Type': 'application/json',
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(data);
        }
      });
    });
    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

(async () => {
  console.log('QAForge Demo Cleanup');
  console.log('====================\n');

  // Fetch all test cases
  const testCases = await apiCall('GET', '/test-cases');
  const testPlans = await apiCall('GET', '/test-plans');
  const summary = await apiCall('GET', '/summary');

  console.log(`Current state: ${testCases.length} test cases, ${testPlans.length} test plans`);
  console.log(`Pass rate: ${summary.pass_rate}%, ${summary.total_executions} executions\n`);

  // Sort by created_at
  const sorted = testCases.sort((a, b) => a.created_at.localeCompare(b.created_at));

  // Determine what to delete
  let toDelete;
  if (keepCount !== null) {
    toDelete = sorted.slice(keepCount);
    console.log(`Strategy: keep oldest ${keepCount}, delete the rest`);
  } else {
    toDelete = sorted.filter(tc => tc.created_at > baselineDate + 'T23:59:59');
    console.log(`Strategy: delete test cases created after ${baselineDate}`);
  }

  const toKeep = sorted.filter(tc => !toDelete.find(d => d.id === tc.id));

  console.log(`\nKeeping: ${toKeep.length} test cases`);
  console.log(`Deleting: ${toDelete.length} test cases\n`);

  if (toDelete.length === 0) {
    console.log('Nothing to clean up!');
    return;
  }

  // Show what will be deleted
  console.log('Will DELETE:');
  for (const tc of toDelete) {
    console.log(`  ${tc.created_at.slice(0, 19)} | ${tc.test_case_id.padEnd(18)} | ${tc.title.slice(0, 50)}`);
  }

  console.log('\nWill KEEP:');
  for (const tc of toKeep.slice(0, 5)) {
    console.log(`  ${tc.created_at.slice(0, 19)} | ${tc.test_case_id.padEnd(18)} | ${tc.title.slice(0, 50)}`);
  }
  if (toKeep.length > 5) {
    console.log(`  ... and ${toKeep.length - 5} more`);
  }

  if (!confirm) {
    console.log('\n--- DRY RUN --- Add --confirm to actually delete');
    return;
  }

  // Delete in batches
  console.log('\nDeleting...');
  const ids = toDelete.map(tc => tc.id);
  const batchSize = 20;
  let deleted = 0;

  for (let i = 0; i < ids.length; i += batchSize) {
    const batch = ids.slice(i, i + batchSize);
    const result = await apiCall('DELETE', '/test-cases', { test_case_ids: batch });
    deleted += batch.length;
    console.log(`  Deleted batch ${Math.floor(i / batchSize) + 1}: ${batch.length} test cases`);
  }

  // Fetch updated summary
  const after = await apiCall('GET', '/summary');
  console.log(`\nDone! Deleted ${deleted} test cases.`);
  console.log(`New state: ${after.total_test_cases} test cases, ${after.total_executions} executions, ${after.pass_rate}% pass rate`);
})().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
