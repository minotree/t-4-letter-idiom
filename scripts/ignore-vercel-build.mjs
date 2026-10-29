import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const buildFiles = new Set([
  'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'vercel.json',
  '.npmrc', '.pnpmfile.cjs', '.node-version', '.nvmrc', '.gitattributes',
  'sajaseongeo_image_working.csv', 'scripts/prepare-data.mjs',
  'scripts/ignore-vercel-build.mjs',
]);
export function affectsPwa(path) {
  if (buildFiles.has(path)) return true;
  if (/^tsconfig[^/]*\.json$/.test(path)) return true;
  if (/\.(md|mdx)$/i.test(path)) return false;
  return ['apps/web/', 'packages/', 'data/'].some(prefix => path.startsWith(prefix));
}

// Vercel: exit 0 skips the build; exit 1 continues. Never skip on uncertain history.
export function decideBuild({ env = process.env, cwd = root, git = args => spawnSync('git', args, { cwd, encoding: 'utf8', timeout: 10000 }) } = {}) {
  const base = env.VERCEL_GIT_PREVIOUS_SHA;
  const head = env.VERCEL_GIT_COMMIT_SHA;
  if (![base, head].every(sha => /^[a-f0-9]{40,64}$/i.test(sha ?? ''))) {
    return { skip: false, reason: 'Previous successful deployment or current commit is unavailable.' };
  }
  try {
    // Use the last successful deployment, not HEAD^, so multi-commit pushes and
    // changes awaiting deployment after a failed build cannot be overlooked.
    const result = git(['diff', '--name-only', '-z', '--no-renames', base, head, '--']);
    if (result.error || result.status !== 0 || typeof result.stdout !== 'string') {
      return { skip: false, reason: 'Git comparison unavailable (for example, shallow history).' };
    }
    const changed = result.stdout.split('\0').filter(Boolean);
    const relevant = changed.filter(affectsPwa);
    return relevant.length
      ? { skip: false, reason: `PWA inputs changed: ${relevant.join(', ')}` }
      : { skip: true, reason: 'No PWA, shared package, content or build configuration changes.' };
  } catch {
    return { skip: false, reason: 'Git comparison failed; continue building.' };
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const result = decideBuild();
  console.log(`[Vercel] ${result.skip ? 'SKIP' : 'BUILD'}: ${result.reason}`);
  process.exitCode = result.skip ? 0 : 1;
}
