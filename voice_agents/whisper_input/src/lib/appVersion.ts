import packageJson from '../../package.json';

export const APP_VERSION = packageJson.version;
export const APP_VERSION_LABEL = `v${APP_VERSION}`;
// 当前 build 是不是 Beta 版？约定：semver prerelease 段（含 `-`）= Beta，
// 例如 `1.2.24-1` / `1.2.24-2`；正式版没有 `-`，例如 `1.2.23` / `1.2.24`。
// 用于 UI 条件渲染——Beta 标签只在 Beta build 出现。
export const IS_BETA_BUILD = APP_VERSION.includes('-');
