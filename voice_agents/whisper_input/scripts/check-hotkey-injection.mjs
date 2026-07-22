import { spawnSync } from 'node:child_process';

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const cargo = process.platform === 'win32' ? 'cargo.exe' : 'cargo';
const githubActions = process.env.GITHUB_ACTIONS === 'true';

const checks = [
  {
    label: 'ShortcutRecorder UI recording contract',
    command: npx,
    args: ['--yes', 'tsx', 'src/components/ShortcutRecorder.test.ts'],
  },
  {
    label: 'Hotkey recorder parser',
    command: npx,
    args: ['--yes', 'tsx', 'src/lib/hotkeyRecorder.test.ts'],
  },
  {
    label: 'Window hotkey fallback',
    command: npx,
    args: ['--yes', 'tsx', 'src/lib/windowHotkeyFallback.test.ts'],
  },
  {
    label: githubActions
      ? 'CI-safe Windows RightAlt core tests'
      : 'Windows hotkey hook unit tests',
    command: cargo,
    args: githubActions
      ? [
          'test',
          '--manifest-path',
          'src-tauri/hotkey-regression/Cargo.toml',
          '--',
          '--test-threads=1',
        ]
      : [
          'test',
          '--manifest-path',
          'src-tauri/Cargo.toml',
          'hotkey',
          '--lib',
          '--',
          '--test-threads=1',
        ],
  },
];

for (const check of checks) {
  console.log(`\n==> ${check.label}`);
  const result = spawnSync(check.command, check.args, {
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });

  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}
