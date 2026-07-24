declare module '@tauri-apps/plugin-autostart' {
  export function enable(): Promise<void>;
  export function disable(): Promise<void>;
  export function isEnabled(): Promise<boolean>;
}
