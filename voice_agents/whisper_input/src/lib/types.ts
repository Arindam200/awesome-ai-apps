// TypeScript mirror of src-tauri/src/types.rs.
// All keys are camelCase (Rust serializes with #[serde(rename_all = "camelCase")]).
// PolishMode is an exception — Rust uses lowercase serialization.

export type PolishMode = 'raw' | 'light' | 'structured' | 'formal';

export type InsertStatus = 'inserted' | 'pasteSent' | 'copiedFallback' | 'failed';

export interface DictationSession {
  id: string;
  createdAt: string; // ISO-8601
  rawTranscript: string;
  finalText: string;
  mode: PolishMode;
  appBundleId: string | null;
  appName: string | null;
  insertStatus: InsertStatus;
  errorCode: string | null;
  durationMs: number | null;
  dictionaryEntryCount: number | null;
  asrProviderId?: string | null;
  llmProviderId?: string | null;
}

export interface DictionaryEntry {
  id: string;
  phrase: string;
  note: string | null;
  enabled: boolean;
  hits: number;
  createdAt: string;
}

export interface CorrectionRule {
  id: string;
  pattern: string;
  replacement: string;
  enabled: boolean;
  createdAt: string;
}

export interface VocabPreset {
  id: string;
  name: string;
  phrases: string[];
}

export interface VocabPresetStore {
  custom: VocabPreset[];
  overrides: VocabPreset[];
  disabledBuiltinPresetIds: string[];
}

export type HotkeyTrigger =
  | 'rightOption'
  | 'leftOption'
  | 'rightControl'
  | 'leftControl'
  | 'rightCommand'
  | 'fn'
  | 'rightAlt'
  | 'custom';

export type HotkeyMode = 'toggle' | 'hold' | 'doubleClick';

export interface HotkeyKey {
  code: string;
}

export interface HotkeyBinding {
  trigger: HotkeyTrigger;
  mode: HotkeyMode;
  keys?: HotkeyKey[] | null;
}

export type HotkeyAdapterKind = 'macEventTap' | 'windowsLowLevel' | 'rdev';

export interface HotkeyCapability {
  adapter: HotkeyAdapterKind;
  availableTriggers: HotkeyTrigger[];
  requiresAccessibilityPermission: boolean;
  supportsModifierOnlyTrigger: boolean;
  supportsSideSpecificModifiers: boolean;
  explicitFallbackAvailable: boolean;
  statusHint: string | null;
}

export interface HotkeyInstallError {
  code: string;
  message: string;
}

export type HotkeyStatusState = 'starting' | 'installed' | 'failed';

export interface HotkeyStatus {
  adapter: HotkeyAdapterKind;
  state: HotkeyStatusState;
  message: string | null;
  lastError: HotkeyInstallError | null;
}

export interface ShortcutBinding {
  /** 主键，例如 "D" / "Space" / "F1" / "RightOption" / "RightAlt" / "Shift" */
  primary: string;
  /** 修饰符列表，元素小写："cmd" | "shift" | "alt" | "ctrl"。 */
  modifiers: string[];
}

/** 划词语音问答快捷键绑定。null 表示未启用。详见 issue #118。 */
export type QaHotkeyBinding = ShortcutBinding;

/** 自定义录音组合键绑定。当 hotkey.trigger == 'custom' 时使用。 */
export type ComboBinding = ShortcutBinding;

/** 模拟粘贴时按下的快捷键。仅 Windows/Linux 生效；macOS 走 AX 直写。
 *  - ctrlV       : 标准粘贴（默认；大多数编辑器、浏览器、IDE）
 *  - ctrlShiftV  : kitty / alacritty / wezterm / gnome-terminal / foot 等终端
 *  - shiftInsert : xterm / urxvt 等老派 X11 终端
 *  详见 issue #360。 */
export type PasteShortcut = 'ctrlV' | 'ctrlShiftV' | 'shiftInsert';

export type ChineseScriptPreference = 'auto' | 'simplified' | 'traditional';

export type OutputLanguagePreference = 'auto' | 'zhCn' | 'zhTw' | 'en' | 'ja' | 'ko';

export type WindowsImeInstallState =
  | 'installed'
  | 'notInstalled'
  | 'registrationBroken'
  | 'notWindows';

export interface WindowsImeStatus {
  state: WindowsImeInstallState;
  usingTsfBackend: boolean;
  message: string;
  dllPath: string | null;
}

/** Auto-update 渠道偏好。stable = 跟正式版（默认）；beta = Settings 里多一个
 *  手动下载 Beta 的入口。不影响 plugin-updater 的自动检查路径。 */
export type UpdateChannel = 'stable' | 'beta';

export interface UserPreferences {
  hotkey: HotkeyBinding;
  dictationHotkey: ShortcutBinding;
  defaultMode: PolishMode;
  enabledModes: PolishMode[];
  launchAtLogin: boolean;
  showCapsule: boolean;
  /** 录音期间临时静音系统输出，停止/取消/出错后恢复原静音状态。 */
  muteDuringRecording: boolean;
  /** 录音输入设备名称。空字符串 = 使用系统默认麦克风。 */
  microphoneDeviceName: string;
  activeAsrProvider: string;
  activeLlmProvider: string;
  /** LLM 思考模式开关。默认关闭，保持既有尽量关闭思考的行为。详见 issue #402。 */
  llmThinkingEnabled: boolean;
  /** 仅 Windows/Linux：粘贴成功后是否恢复用户原剪贴板。默认 true。详见 issue #111。 */
  restoreClipboardAfterPaste: boolean;
  /** 仅 Windows/Linux：模拟粘贴时按下的快捷键。详见 issue #360：kitty/alacritty
   *  等终端只接受 Ctrl+Shift+V，硬编码 Ctrl+V 会被吞掉，听写文本只剩在剪贴板里。
   *  macOS 走 AX 直写不受影响。默认 'ctrlV' 与历史行为一致。 */
  pasteShortcut: PasteShortcut;
  /** Windows：TSF 失败后是否允许 SendInput / 粘贴类非 TSF 兜底。关闭后可验证是否真实 TSF 上屏。 */
  allowNonTsfInsertionFallback: boolean;
  /** 用户的工作语言（多选，原生名）；作为前提注入 LLM polish/translate prompt 头部。 */
  workingLanguages: string[];
  /** 翻译模式目标语言（单选，原生名）；空串 = 不启用 Shift 翻译。详见 issue #4。 */
  translationTargetLanguage: string;
  /** 中文输出字形偏好：可由输出语言选择明确设置；未设置时仍可跟随界面语言同步。 */
  chineseScriptPreference: ChineseScriptPreference;
  /** 最终输出语言偏好：独立于界面语言；English 会路由到翻译路径。 */
  outputLanguagePreference: OutputLanguagePreference;
  /** 是否由用户通过独立输出语言控件显式选择；旧配置里的语言同步值不算显式选择。 */
  outputLanguagePreferenceExplicit: boolean;
  /** 划词语音问答快捷键。null = 未启用。详见 issue #118。 */
  qaHotkey: QaHotkeyBinding | null;
  /** 全局历史记录开关。关闭后不再向本地历史追加新条目。 */
  historyEnabled: boolean;
  /** 是否把 Q&A 历史写到本地存档。详见 issue #118。 */
  qaSaveHistory: boolean;
  /** 自定义录音组合键。当 hotkey.trigger == 'custom' 时使用。null = 未设置。 */
  customComboHotkey: ComboBinding | null;
  /** 录音中触发翻译的全局快捷键。默认 Shift。 */
  translationHotkey: ShortcutBinding;
  /** 切换到上一个润色风格的全局快捷键。 */
  switchStyleHotkey: ShortcutBinding;
  /** 打开 Whisper Input 主窗口的全局快捷键。 */
  openAppHotkey: ShortcutBinding;
  /** 本地 Qwen3-ASR 当前激活的模型 id。仅在 activeAsrProvider === 'local-qwen3' 时有意义。 */
  localAsrActiveModel: string;
  /** 本地模型下载源镜像（'huggingface' / 'hf-mirror'）。 */
  localAsrMirror: string;
  /** 本地 ASR 引擎在内存中的保留时长（秒）。0 = 说完话即释放；
   *  300 = 默认 5 分钟；86400 ≈ 不释放（保持加载）。 */
  localAsrKeepLoadedSecs: number;
  /** Windows Foundry Local Whisper 当前激活的模型 alias。 */
  foundryLocalAsrModel: string;
  /** Windows Foundry Local native runtime 下载源。 */
  foundryLocalRuntimeSource: string;
  /** Windows Foundry Local Whisper 语言 hint。空字符串表示自动检测。 */
  foundryLocalAsrLanguageHint: string;
  /** Windows Foundry Local Whisper 模型在 runtime 中保持加载的秒数。 */
  foundryLocalAsrKeepLoadedSecs: number;
  /** 历史记录保留天数。0 = 不按时间清理（仍受 200 条上限）。默认 7。 */
  historyRetentionDays: number;
  /** 对话感知 polish 上下文窗口（分钟）。0 = 关闭。默认 5。详见 PR-A。 */
  polishContextWindowMinutes: number;
  /** 启动时静默运行（不弹主窗口）。Windows 开机自启场景常用——只想要后台 + 托盘，
   *  不想被主窗口打扰。开后所有启动路径都不弹窗，从菜单栏 / 托盘进入主窗口。默认 false。 */
  startMinimized: boolean;
  /** 自动更新渠道。'stable'（默认）= plugin-updater 仅检查正式版；
   *  'beta' = Settings → About 出现手动下载 Beta 的入口。 */
  updateChannel: UpdateChannel;
  /** 流式输入：润色 SSE 一边到达一边逐字模拟键盘事件输出到当前焦点。开启后用户感知到
   *  的处理时延显著降低。v1 限定 macOS + OpenAI-compatible provider，其他配置自动回落
   *  到原一次性插入。默认 false 与历史行为一致。 */
  streamingInsert: boolean;
  /** 流式输入成功后是否把最终润色文本写回剪贴板。开启后 Cmd+V 还能重复粘贴该次输出，
   *  与一次性路径行为对齐。默认 true。 */
  streamingInsertSaveClipboard: boolean;
  /** Windows RightAlt 历史迁移标记。保留字段仅为兼容旧 preferences。 */
  rightAltHotkeyMigrationVersion: number;
}

export interface MicrophoneDevice {
  name: string;
  isDefault: boolean;
}

/** Rust 通过 `qa:state` 事件下发的 payload。
 *  v2 (issue #118 v2)：支持多轮对话，messages 数组每次由后端整段下发（单一可信源）。
 *  v2.1：开 `stream:true`，LLM 答案逐 chunk 通过 `answer_delta` 事件推前端边渲染。 */
export type QaStateKind =
  | 'idle'
  | 'recording'
  | 'loading'
  | 'thinking'
  | 'answer_delta'
  | 'answer'
  | 'error';

export interface QaChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface QaStatePayload {
  kind: QaStateKind;
  /** 后端权威：当前已有的多轮对话历史（user → assistant 交替）。answer 事件带完整版。 */
  messages?: QaChatMessage[];
  /** recording 状态时附带的选区预览（前 60 字）。 */
  selection_preview?: string | null;
  /** error 状态时附带的提示。 */
  error?: string;
  /** answer_delta 事件时附带的本帧增量字符串。 */
  chunk?: string;
}

/** 内置语言列表 — 前端 Settings UI 用，后端只接收原生名字符串拼 prompt。
 *  添加新语言时直接在这里加一项（原生名），无需修改后端。 */
export const SUPPORTED_LANGUAGES: readonly string[] = [
  '简体中文',
  '繁体中文',
  'English',
  '日本語',
  '한국어',
  'Français',
  'Deutsch',
  'Español',
  'Italiano',
  'Português',
  'Русский',
  'العربية',
  'Tiếng Việt',
  'ไทย',
  'हिन्दी',
] as const;

export type CapsuleState =
  | 'idle'
  | 'recording'
  | 'transcribing'
  | 'polishing'
  | 'done'
  | 'cancelled'
  | 'error';

export interface CapsulePayload {
  state: CapsuleState;
  level: number; // 0..1 RMS
  elapsedMs: number;
  message: string | null;
  insertedChars: number | null;
  /** 当前 session 是否处于翻译模式（用户已按过 Shift）。详见 issue #4。 */
  translation: boolean;
}

export interface CredentialsStatus {
  activeAsrProvider: string;
  activeLlmProvider: string;
  asrConfigured: boolean;
  llmConfigured: boolean;
  /** 兼容旧字段（过渡期保留）。 */
  volcengineConfigured: boolean;
  arkConfigured: boolean;
}

export interface TodayMetrics {
  charsToday: number;
  segmentsToday: number;
  avgLatencyMs: number;
  totalDurationMs: number;
}

export interface UsageStats {
  totalChars: number;
  totalDurationMs: number;
  totalSegments: number;
}

export type PermissionStatus =
  | 'granted'
  | 'denied'
  | 'notDetermined'
  | 'restricted'
  | 'notApplicable';
