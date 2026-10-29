import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { affectsPwa, decideBuild } from './ignore-vercel-build.mjs';

const env = { VERCEL_GIT_PREVIOUS_SHA: 'a'.repeat(40), VERCEL_GIT_COMMIT_SHA: 'b'.repeat(40) };
const compare = paths => decideBuild({ env, git: args => {
  assert.deepEqual(args, ['diff', '--name-only', '-z', '--no-renames', env.VERCEL_GIT_PREVIOUS_SHA, env.VERCEL_GIT_COMMIT_SHA, '--']);
  return { status: 0, stdout: paths.join('\0') + '\0' };
} });
test('Toss-only, documentation and unrelated check scripts skip PWA', () => {
  assert.equal(compare(['apps/toss/src/App.tsx', 'apps/toss/package.json', 'progress.md', 'docs/requirements.md', 'apps/web/README.md', 'scripts/check-toss-banner.mjs']).skip, true);
  assert.equal(compare([]).skip, true);
});
test('PWA source/assets, shared code, content and build inputs continue', () => {
  for (const path of ['apps/web/src/App.tsx', 'apps/web/public/icon-512.png', 'packages/shared/src/index.ts', 'data/english/words.json', 'data/cheonjamun/reviewed/review.json', 'sajaseongeo_image_working.csv', 'scripts/prepare-data.mjs', 'scripts/ignore-vercel-build.mjs', 'vercel.json', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'tsconfig.base.json', '.npmrc', '.gitattributes']) {
    assert.equal(compare([path]).skip, false, path);
  }
});
test('renaming a PWA input into Toss still builds via deletion path', () => {
  assert.equal(compare(['apps/web/src/deleted.ts', 'apps/toss/src/moved.ts']).skip, false);
  assert.equal(affectsPwa('apps/web-other/src/App.tsx'), false);
});
test('missing/invalid baseline, shallow clone, Git errors and exceptions build', () => {
  assert.equal(decideBuild({ env: {} }).skip, false);
  assert.equal(decideBuild({ env: { ...env, VERCEL_GIT_PREVIOUS_SHA: '--help' } }).skip, false);
  for (const git of [() => ({ status: 128 }), () => ({ status: null, error: new Error() }), () => { throw new Error(); }]) {
    assert.equal(decideBuild({ env, git }).skip, false);
  }
});
test('real CLI uses 1 to build without baseline, 0 to skip unchanged Git tree', () => {
  const command = fileURLToPath(new URL('./ignore-vercel-build.mjs', import.meta.url));
  const sha = spawnSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).stdout.trim();
  assert.match(sha, /^[a-f0-9]{40,64}$/);
  const run = (previous, current) => spawnSync(process.execPath, [command], {
    encoding: 'utf8', env: { ...process.env, VERCEL_GIT_PREVIOUS_SHA: previous, VERCEL_GIT_COMMIT_SHA: current },
  });
  assert.equal(run('', '').status, 1);
  const unchanged = run(sha, sha);
  assert.equal(unchanged.status, 0, unchanged.stderr);
  assert.match(unchanged.stdout, /SKIP/);
});
