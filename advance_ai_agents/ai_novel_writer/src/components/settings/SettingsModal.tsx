import { useState, useEffect, useRef } from 'react'
import {
  X, Plus, Trash2, Check, Save, Globe, Cpu, Database,
  Type, Settings2, Zap, Eye, EyeOff, ChevronDown, MessageSquare,
  Info,
} from 'lucide-react'
import PromptSettings from './PromptSettings'
import { useLLMStore } from '../../stores/llm-store'
import { useThemeStore, FONT_OPTIONS, type FontId } from '../../stores/theme-store'
import type { ModelProfile } from '../../shared/ipc-channels'
import type { ProviderPreset } from '../../shared/provider-presets'
import { BUILTIN_PRESETS } from '../../shared/provider-presets'
import { randomUUID } from '../../utils/id'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Label } from '../ui/Label'
import { NativeSelect } from '../ui/NativeSelect'
import { cn } from '../../lib/utils'
import { ipc } from '../../services/ipc-client'
import { Switch } from '../ui/Switch'
import { APP_BRAND } from '../../shared/brand'
import { useLayoutStore, type SettingsSection } from '../../stores/layout-store'
import { useLocaleStore } from '../../stores/locale-store'
import type { Locale } from '../../i18n/types'

// ==================== 分类定义 ====================

interface SectionItem {
  id: SettingsSection
  label: string
  labelEn: string
  icon: React.ReactNode
  description: string
  descriptionEn: string
}

const SECTIONS: SectionItem[] = [
  { id: 'llm', label: 'AI 生成模型', labelEn: 'Generation models', icon: <Cpu size={16} />, description: '配置用于文章生成、改写、摘要的语言模型', descriptionEn: 'Models used for writing, rewriting, and summarization' },
  { id: 'embedding', label: '向量模型', labelEn: 'Embedding model', icon: <Database size={16} />, description: '配置用于知识库检索的 Embedding 模型', descriptionEn: 'Embedding model used for knowledge retrieval' },
  { id: 'proxy', label: '网络代理', labelEn: 'Network proxy', icon: <Globe size={16} />, description: '配置 HTTP / SOCKS5 代理，用于访问受限 API', descriptionEn: 'HTTP / SOCKS5 proxy for restricted APIs' },
  { id: 'editor', label: '编辑器', labelEn: 'Editor', icon: <Type size={16} />, description: '字体大小、自动保存等编辑器偏好设置', descriptionEn: 'Fonts and other editor preferences' },
  { id: 'prompts', label: '提示词模板', labelEn: 'Prompt templates', icon: <MessageSquare size={16} />, description: '自定义 AI 创作各环节使用的提示词模板', descriptionEn: 'Customize guidance for each AI writing stage' },
  { id: 'about', label: '关于', labelEn: 'About', icon: <Info size={16} />, description: '版本、定位与本地部署说明', descriptionEn: 'Version, positioning, and local deployment' },
]

// ==================== 主组件 ====================

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

/** 全屏设置弹窗 */
export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  const text = useLocaleStore(s => s.text)
  const requestedSection = useLayoutStore(s => s.settingsSection)
  const [section, setSection] = useState<SettingsSection>(requestedSection)

  useEffect(() => {
    if (open) {
      setSection(requestedSection)
    }
  }, [open, requestedSection])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="relative flex w-[880px] h-[600px] rounded-2xl overflow-hidden shadow-2xl"
        style={{
          backgroundColor: 'var(--color-editor-bg)',
          border: '1px solid var(--color-border)',
        }}
      >
        {/* 左侧导航 */}
        <aside
          className="flex flex-col w-52 flex-shrink-0 py-5 gap-1"
          style={{
            backgroundColor: 'var(--color-sidebar)',
            borderRight: '1px solid var(--color-border)',
          }}
        >
          {/* 标题 */}
          <div className="flex items-center gap-2 px-4 mb-4">
            <Settings2 size={16} style={{ color: 'var(--color-accent)' }} />
            <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              {text('设置', 'Settings')}
            </span>
          </div>

          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className={cn(
                'flex items-center gap-2.5 mx-2 px-3 py-2.5 rounded-lg text-left text-sm transition-colors',
                section === s.id
                  ? 'bg-[var(--color-accent)] text-white'
                  : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]',
              )}
            >
              {s.icon}
              {text(s.label, s.labelEn)}
            </button>
          ))}
        </aside>

        {/* 右侧内容区 */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* 区域标题栏 */}
          <div
            className="flex items-center justify-between px-6 py-4 flex-shrink-0"
            style={{ borderBottom: '1px solid var(--color-border)' }}
          >
            <div>
              <h2 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>
                {(() => { const item = SECTIONS.find(s => s.id === section); return item ? text(item.label, item.labelEn) : '' })()}
              </h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                {(() => { const item = SECTIONS.find(s => s.id === section); return item ? text(item.description, item.descriptionEn) : '' })()}
              </p>
            </div>
            <button
              onClick={onClose}
              className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-[var(--color-hover)]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <X size={16} />
            </button>
          </div>

          {/* 区域内容 */}
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {section === 'llm' && <LLMSection purposes={['generation', 'refinement', 'summary']} purposeLabel={text('生成模型', 'generation models')} />}
            {section === 'embedding' && <LLMSection purposes={['embedding']} purposeLabel={text('向量模型', 'embedding models')} />}
            {section === 'proxy' && <ProxySection />}
            {section === 'editor' && <EditorSection />}
            {section === 'prompts' && <PromptSettings />}
            {section === 'about' && <AboutSection />}
          </div>
        </main>
      </div>
    </div>
  )
}

// ==================== LLM & Embedding 通用区 ====================

function LLMSection({
  purposes,
  purposeLabel,
}: {
  purposes: ModelProfile['purposes']
  purposeLabel: string
}) {
  const text = useLocaleStore(s => s.text)
  const models = useLLMStore(s => s.models)
  const defaultModelId = useLLMStore(s => s.defaultModelId)
  const defaultEmbeddingModelId = useLLMStore(s => s.defaultEmbeddingModelId)
  const loaded = useLLMStore(s => s.loaded)
  const loadModels = useLLMStore(s => s.loadModels)
  const saveModel = useLLMStore(s => s.saveModel)
  const deleteModel = useLLMStore(s => s.deleteModel)
  const setDefaultModel = useLLMStore(s => s.setDefaultModel)
  const setDefaultEmbeddingModel = useLLMStore(s => s.setDefaultEmbeddingModel)
  const [editingModel, setEditingModel] = useState<ModelProfile | null>(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (!loaded) loadModels()
  }, [loaded, loadModels])

  // 预设直接使用内置常量，无需 IPC 加载
  const presets = BUILTIN_PRESETS

  // 按用途过滤
  const filtered = models.filter((m) =>
    m.purposes?.some((p) => purposes.includes(p as ModelProfile['purposes'][number]))
  )

  /** 创建新模型，使用预设中 openai 的默认属性 */
  const handleAdd = () => {
    const isEmbedding = purposes.includes('embedding')
    const openaiPreset = presets.find((p) => p.provider === 'openai') ?? presets[0]
    setEditingModel({
      id: randomUUID(),
      name: '',
      provider: 'openai',
      protocol: (openaiPreset?.protocol ?? 'openai') as 'openai' | 'gemini',
      modelName: isEmbedding
        ? (openaiPreset?.embeddingModels[0] ?? 'text-embedding-3-small')
        : (openaiPreset?.models[0]?.name ?? 'gpt-4o'),
      apiKey: '',
      baseUrl: openaiPreset?.baseUrl ?? 'https://api.openai.com',
      temperature: 0.7,
      maxTokens: openaiPreset?.models[0]?.maxTokens ?? 4096,
      purposes: [...purposes],
    })
  }

  const isEmbeddingSection = purposes.includes('embedding')

  /** 保存模型；若是该分类第一个则自动设为默认 */
  const handleSave = async () => {
    if (!editingModel) return
    setSaving(true)
    await saveModel(editingModel)
    // 新增模型后，如果该分类还没有默认则自动设为默认
    const countBefore = filtered.length
    if (countBefore === 0) {
      if (isEmbeddingSection) {
        setDefaultEmbeddingModel(editingModel.id)
      } else {
        setDefaultModel(editingModel.id)
      }
    }
    setEditingModel(null)
    setSaving(false)
  }


  return (
    <div className="space-y-4">
      {/* 模型编辑表单 */}
      {editingModel && (
        <ModelForm
          model={editingModel}
          onChange={setEditingModel}
          onSave={handleSave}
          onCancel={() => setEditingModel(null)}
          saving={saving}
          purposeOptions={purposes}
          presets={presets}
        />
      )}

      {/* 模型列表 */}
      {!editingModel && (
        <>
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {text(`已配置 ${filtered.length} 个${purposeLabel}`, `${filtered.length} ${purposeLabel} configured`)}
            </span>
            <Button size="sm" onClick={handleAdd}>
              <Plus size={13} />
              {text(`添加${purposeLabel}`, `Add ${purposeLabel}`)}
            </Button>
          </div>

          {filtered.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-16 gap-3 rounded-xl"
              style={{ border: '1.5px dashed var(--color-border)' }}
            >
              <Zap size={28} style={{ color: 'var(--color-text-muted)', opacity: 0.5 }} />
              <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {text(`暂无${purposeLabel}配置`, `No ${purposeLabel} configured`)}
              </span>
              <Button size="sm" variant="outline" onClick={handleAdd}>
                <Plus size={13} />
                {text(`添加第一个${purposeLabel}`, `Add first ${purposeLabel}`)}
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map((model) => (
                <ModelCard
                  key={model.id}
                  model={model}
                  isDefault={isEmbeddingSection
                    ? defaultEmbeddingModelId === model.id
                    : defaultModelId === model.id}
                  onSetDefault={() => isEmbeddingSection
                    ? setDefaultEmbeddingModel(model.id)
                    : setDefaultModel(model.id)}
                  onEdit={() => setEditingModel({ ...model })}
                  onDelete={() => deleteModel(model.id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** 模型卡片 */
function ModelCard({
  model, isDefault, onSetDefault, onEdit, onDelete,
}: {
  model: ModelProfile
  isDefault: boolean
  onSetDefault: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const text = useLocaleStore(s => s.text)
  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3 rounded-xl group transition-colors',
        isDefault
          ? 'border border-[var(--color-accent)]'
          : 'border border-[var(--color-border)] hover:border-[var(--color-accent)]',
      )}
      style={{ backgroundColor: isDefault ? 'color-mix(in srgb, var(--color-accent) 5%, var(--color-panel))' : 'var(--color-panel)' }}
    >
      {/* 图标 */}
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-lg"
        style={{ backgroundColor: 'var(--color-hover)' }}
      >
        {providerIcon(model.provider)}
      </div>

      {/* 信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text)' }}>
            {model.name || model.modelName}
          </span>
          {isDefault && (
            <span className="text-[0.7rem] px-1.5 py-0.5 rounded-full bg-[var(--color-accent)] text-white flex-shrink-0">
              {text('默认', 'Default')}
            </span>
          )}
        </div>
        <p className="text-xs truncate mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
          {model.provider} · {model.modelName} · {model.baseUrl}
        </p>
      </div>

      {/* 操作按钮（hover 显示） */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {!isDefault && (
          <button
            onClick={onSetDefault}
            title={text('设为默认', 'Set as default')}
            className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-[var(--color-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <Check size={14} />
          </button>
        )}
        <button
          onClick={onEdit}
          title={text('编辑', 'Edit')}
          className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-[var(--color-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          <Settings2 size={14} />
        </button>
        <button
          onClick={onDelete}
          title={text('删除', 'Delete')}
          className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors hover:bg-red-500/10 text-[var(--color-text-muted)] hover:text-red-400"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

// ==================== 模型编辑表单 ====================


/** 模型编辑表单 */
function ModelForm({
  model, onChange, onSave, onCancel, saving, presets,
}: {
  model: ModelProfile
  onChange: (m: ModelProfile) => void
  onSave: () => void
  onCancel: () => void
  saving: boolean
  purposeOptions: ModelProfile['purposes']
  /** 服务商预设（来自 BUILTIN_PRESETS 常量） */
  presets: ProviderPreset[]
}) {
  const text = useLocaleStore(s => s.text)
  const [showKey, setShowKey] = useState(false)
  // 标记"模型标识"是否使用自定义输入模式
  const [customModelName, setCustomModelName] = useState(false)

  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean, error?: string } | null>(null)
  const testConnection = useLLMStore(s => s.testConnection)

  const isEmbedding = model.purposes?.includes('embedding')
  // 将预设数组转换为以 provider 为键的 Map 方便查找
  const presetMap = new Map(presets.map((p) => [p.provider, p]))
  const preset = presetMap.get(model.provider)
  // 生成模型列表为 ModelPreset[]，embedding 模型为 string列表转换过来的 ModelPreset
  const presetModels: import('../../shared/provider-presets').ModelPreset[] = isEmbedding
    ? (preset?.embeddingModels ?? []).map((name) => ({ name, maxTokens: 0 }))
    : (preset?.models ?? [])

  /** 更新单个字段 */
  const up = <K extends keyof ModelProfile>(key: K, val: ModelProfile[K]) =>
    onChange({ ...model, [key]: val })

  /**
   * 切换服务商：从持久化预设中自动填充 baseUrl / protocol
   * 并将模型名重置为该服务商的第一个预设模型
   */
  const handleProviderChange = (provider: ModelProfile['provider']) => {
    const p = presetMap.get(provider)
    const firstModel = isEmbedding ? null : (p?.models[0] ?? null)
    const defaultModelName = isEmbedding
      ? (p?.embeddingModels[0] ?? '')
      : (firstModel?.name ?? '')
    setCustomModelName(false)
    onChange({
      ...model,
      provider,
      protocol: (p?.protocol ?? 'openai') as 'openai' | 'gemini',
      baseUrl: p?.baseUrl ?? '',
      modelName: defaultModelName,
      maxTokens: firstModel?.maxTokens ?? 4096,
    })
  }

  /** 选择预设模型或切换到自定义输入 */
  const handleModelSelect = (val: string) => {
    if (val === '__custom__') {
      setCustomModelName(true)
      up('modelName', '')
    } else {
      setCustomModelName(false)
      // 找到对应的 ModelPreset，同时更新 modelName 和 maxTokens
      const matched = presetModels.find((m) => m.name === val)
      onChange({
        ...model,
        modelName: val,
        maxTokens: matched?.maxTokens ?? model.maxTokens,
      })
    }
  }


  // 当前模型名是否在预设列表里（决定下拉框显示）
  const isPresetValue = presetModels.some((m) => m.name === model.modelName)
  const selectValue = customModelName || (!isPresetValue && presetModels.length > 0)
    ? '__custom__'
    : model.modelName

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    const result = await testConnection(model)
    setTestResult(result)
    setTesting(false)
    setTimeout(() => setTestResult(null), 3000)
  }

  return (
    <div
      className="rounded-xl p-5 space-y-4"
      style={{ border: '1.5px solid var(--color-accent)', backgroundColor: 'var(--color-panel)' }}
    >
      <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {model.name ? text(`编辑：${model.name}`, `Edit: ${model.name}`) : text('新建模型配置', 'New model configuration')}
      </h3>

      {/* 显示名称 */}
      <div>
        <Label>{text('显示名称', 'Display name')}</Label>
        <Input
          value={model.name}
          onChange={(e) => up('name', e.target.value)}
          placeholder={text('如：DeepSeek 主力 / GPT-4o 备用', 'e.g. DeepSeek primary / GPT-4o backup')}
        />
      </div>

      {/* 服务商 + 协议 */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label>{text('服务商', 'Provider')}</Label>
          <NativeSelect
            value={model.provider}
            onChange={(e) => handleProviderChange(e.target.value as ModelProfile['provider'])}
          >
            <option value="openai">OpenAI</option>
            <option value="deepseek">DeepSeek</option>
            <option value="gemini">Google Gemini</option>
            <option value="ollama">{text('Ollama（本地）', 'Ollama (local)')}</option>
            <option value="bigmodel">{text('BigModel（智谱）', 'BigModel (Zhipu)')}</option>
            <option value="custom">{text('自定义', 'Custom')}</option>
          </NativeSelect>
        </div>
        <div>
          <Label>{text('调用协议', 'Protocol')}</Label>
          <NativeSelect
            value={model.protocol}
            onChange={(e) => up('protocol', e.target.value as 'openai' | 'gemini')}
          >
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini</option>
          </NativeSelect>
        </div>
      </div>

      {/* 模型标识：有预设时显示下拉，否则纯输入 */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <Label className="mb-0">{text('模型标识', 'Model ID')}</Label>
          {presetModels.length > 0 && (
            <button
              type="button"
              onClick={() => {
                if (customModelName) {
                  // 切回预设列表
                  const first = presetModels[0]
                  setCustomModelName(false)
                  onChange({ ...model, modelName: first.name, maxTokens: first.maxTokens ?? model.maxTokens })
                } else {
                  // 切换到自定义输入
                  setCustomModelName(true)
                  up('modelName', '')
                }
              }}
              className="text-xs transition-colors"
              style={{ color: 'var(--color-accent)' }}
            >
              {customModelName ? text('从列表选择', 'Choose from list') : text('手动输入', 'Enter manually')}
            </button>
          )}
        </div>

        {/* 有预设模型 且 未切到手动输入 → 显示下拉 */}
        {presetModels.length > 0 && !customModelName ? (
          <NativeSelect
            value={selectValue}
            onChange={(e) => handleModelSelect(e.target.value)}
          >
            {presetModels.map((m) => (
              <option key={m.name} value={m.name}>{m.name}</option>
            ))}
            <option value="__custom__">{text('手动输入', 'Enter manually')}</option>
          </NativeSelect>
        ) : (
          <div>
            <Input
              value={model.modelName}
              onChange={(e) => up('modelName', e.target.value)}
              placeholder={isEmbedding ? 'text-embedding-3-small' : 'gpt-4o'}
              autoFocus={customModelName}
            />
          </div>
        )}
      </div>

      {/* API 地址 */}
      <div>
        <Label>{text('API 地址', 'API URL')}</Label>
        <Input
          value={model.baseUrl}
          onChange={(e) => up('baseUrl', e.target.value)}
          placeholder="https://api.openai.com"
        />
        {model.provider !== 'custom' && (
          <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
            {text(`已自动填入 ${model.provider} 官方地址，如使用中转地址可手动修改`, `The official ${model.provider} URL was filled automatically. Edit it when using a gateway.`)}
          </p>
        )}
      </div>

      {/* API Key */}
      <div>
        <Label>API Key</Label>
        <div className="relative">
          <Input
            type={showKey ? 'text' : 'password'}
            value={model.apiKey}
            onChange={(e) => up('apiKey', e.target.value)}
            placeholder={model.provider === 'ollama' ? text('本地部署可留空', 'Optional for local deployment') : 'sk-...'}
            className="pr-9"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
      </div>

      {/* 温度 / Token（仅生成模型） */}
      {!isEmbedding && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>{text('温度', 'Temperature')}</Label>
            <Input
              type="number" min={0} max={2} step={0.1}
              value={model.temperature}
              onChange={(e) => up('temperature', (e.target.value === '' ? '' : parseFloat(e.target.value)) as number)}
              onBlur={() => {
                const v = Number(model.temperature);
                if (isNaN(v)) up('temperature', 0.7)
              }}
            />
          </div>
          <div>
            <Label>{text('最大 Tokens', 'Maximum tokens')}</Label>
            <Input
              type="number"
              value={model.maxTokens}
              onChange={(e) => up('maxTokens', (e.target.value === '' ? '' : parseInt(e.target.value)) as number)}
              onBlur={() => {
                const v = Number(model.maxTokens);
                if (!v || v < 1) up('maxTokens', 4096)
              }}
            />
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="outline"
          onClick={handleTest}
          disabled={testing || !model.baseUrl || (!model.apiKey && model.provider !== 'ollama')}
        >
          <Zap size={13} />
          {testing ? text('测试中...', 'Testing...') : text('测试连接', 'Test connection')}
        </Button>
        <Button
          className="flex-1"
          onClick={onSave}
          disabled={saving || !model.name || (!model.apiKey && model.provider !== 'ollama')}
        >
          <Save size={13} />
          {saving ? text('保存中...', 'Saving...') : text('保存配置', 'Save configuration')}
        </Button>
        <Button variant="ghost" onClick={onCancel}>{text('取消', 'Cancel')}</Button>
      </div>
      {testResult && (
        <div className={`text-xs p-2 rounded ${testResult.success ? 'bg-green-500/10 text-green-500 border border-green-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'} break-all`}>
          {testResult.success ? text('连接成功', 'Connection succeeded') : text(`连接失败：${testResult.error}`, `Connection failed: ${testResult.error}`)}
        </div>
      )}
    </div>
  )
}


// ==================== 代理设置 ====================

function ProxySection() {
  const text = useLocaleStore(s => s.text)
  const [proxy, setProxy] = useState<{
    enabled: boolean; type: 'http' | 'socks5'; host: string; port: number
  }>({ enabled: false, type: 'http', host: '', port: 7890 })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    ipc.invoke('config:get').then((cfg) => {
      if (cfg?.proxy) {
        setProxy({
          enabled: cfg.proxy.enabled ?? false, // 明确默认关闭
          type: cfg.proxy.type ?? 'http',
          host: cfg.proxy.host ?? '',
          port: cfg.proxy.port ?? 7890,
        })
      }
    }).catch(() => { })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    await ipc.invoke('config:set', { proxy }).catch(() => { })
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-[480px] space-y-5">
      {/* 启用开关 */}
      <div
        className="flex items-center justify-between p-4 rounded-xl"
        style={{ border: '1px solid var(--color-border)', backgroundColor: 'var(--color-panel)' }}
      >
        <div>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{text('启用代理', 'Enable proxy')}</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            {text('所有 AI API 请求将通过代理发送', 'All AI API requests will be sent through the proxy.')}
          </p>
        </div>
        <Switch
          checked={proxy.enabled}
          onCheckedChange={(checked) => setProxy({ ...proxy, enabled: checked })}
          aria-label={text('启用代理', 'Enable proxy')}
        />
      </div>

      {/* 代理详情 */}
      {proxy.enabled && (
        <div
          className="space-y-3 p-4 rounded-xl"
          style={{ border: '1px solid var(--color-border)', backgroundColor: 'var(--color-panel)' }}
        >
          <div>
            <Label>{text('代理类型', 'Proxy type')}</Label>
            <NativeSelect
              value={proxy.type}
              onChange={(e) => setProxy({ ...proxy, type: e.target.value as 'http' | 'socks5' })}
            >
              <option value="http">HTTP</option>
              <option value="socks5">SOCKS5</option>
            </NativeSelect>
          </div>
          <div className="grid grid-cols-[1fr_120px] gap-3">
            <div>
              <Label>{text('主机地址', 'Host')}</Label>
              <Input
                value={proxy.host}
                onChange={(e) => setProxy({ ...proxy, host: e.target.value })}
                placeholder="127.0.0.1"
              />
            </div>
            <div>
              <Label>{text('端口', 'Port')}</Label>
              <Input
                type="number"
                value={proxy.port}
                onChange={(e) => setProxy({ ...proxy, port: (e.target.value === '' ? '' : parseInt(e.target.value)) as number })}
                onBlur={() => {
                  const v = Number(proxy.port);
                  if (!v) setProxy({ ...proxy, port: 7890 })
                }}
              />
            </div>
          </div>
        </div>
      )}

      <Button onClick={handleSave} disabled={saving}>
        {saved ? <Check size={13} /> : <Save size={13} />}
        {saved ? text('已保存', 'Saved') : saving ? text('保存中...', 'Saving...') : text('保存代理配置', 'Save proxy settings')}
      </Button>
    </div>
  )
}

// ==================== 编辑器设置 ====================

/** 字体下拉菜单（界面字体 + 写作字体共用） */
function FontSelect({
  value,
  onChange,
}: {
  value: FontId
  onChange: (id: FontId) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const current = FONT_OPTIONS.find((o) => o.id === value) ?? FONT_OPTIONS[0]

  // 点击外部关闭
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div ref={ref} className="relative">
      {/* 触发按鈕 */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 w-full px-3 h-9 rounded-lg transition-colors text-left"
        style={{
          border: '1px solid var(--color-border)',
          backgroundColor: open ? 'var(--color-hover)' : 'var(--color-panel)',
          color: 'var(--color-text)',
        }}
      >
        {/* 当前字体预览 */}
        <span
          className="flex-1 text-sm truncate"
          style={{ fontFamily: current.family }}
        >
          {current.label}
        </span>
        <span className="text-xs flex-shrink-0" style={{ color: 'var(--color-text-muted)' }}>
          {current.preview}
        </span>
        <ChevronDown
          size={13}
          className="flex-shrink-0 transition-transform"
          style={{
            color: 'var(--color-text-muted)',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
        />
      </button>

      {/* 下拉选项列表 */}
      {open && (
        <div
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 rounded-xl overflow-hidden"
          style={{
            border: '1px solid var(--color-border)',
            backgroundColor: 'var(--color-panel)',
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          {FONT_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => { onChange(opt.id); setOpen(false) }}
              className="w-full text-left px-3 py-2.5 flex items-center gap-3 transition-colors hover:bg-[var(--color-hover)]"
              style={{
                backgroundColor: value === opt.id
                  ? 'color-mix(in srgb, var(--color-accent) 8%, transparent)'
                  : 'transparent',
              }}
            >
              {/* 选中标记 */}
              <span
                className="w-3.5 h-3.5 rounded-full flex-shrink-0 flex items-center justify-center"
                style={{
                  backgroundColor: value === opt.id ? 'var(--color-accent)' : 'transparent',
                  border: value === opt.id ? 'none' : '1.5px solid var(--color-border)',
                }}
              >
                {value === opt.id && (
                  <span className="w-1.5 h-1.5 rounded-full bg-white" />
                )}
              </span>

              {/* 字体名 + 描述 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-medium" style={{ color: 'var(--color-text)', fontFamily: opt.family }}>
                    {opt.label}
                  </span>
                  <span className="text-[0.65rem]" style={{ color: 'var(--color-text-muted)' }}>
                    {opt.labelEn}
                  </span>
                </div>
                <p className="text-[0.65rem] truncate mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                  {opt.desc}
                </p>
              </div>

              {/* 预览文字 */}
              <span
                className="text-sm flex-shrink-0"
                style={{ fontFamily: opt.family, color: 'var(--color-text-secondary)' }}
              >
                {opt.preview}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function EditorSection() {
  const { writingFont, setWritingFont, uiFont, setUiFont } = useThemeStore()
  const { locale, setLocale, t, text } = useLocaleStore()

  return (
    <div className="max-w-md space-y-5">
      <div className="space-y-1.5">
        <div>
          <p className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
            {t('language.settingLabel')}
          </p>
          <p className="text-[0.68rem] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            {t('language.settingDescription')}
          </p>
        </div>
        <NativeSelect
          value={locale}
          onChange={(event) => void setLocale(event.target.value as Locale)}
        >
          <option value="zh-CN">{text('简体中文', 'Simplified Chinese')}</option>
          <option value="en-US">English</option>
        </NativeSelect>
      </div>

      {/* 界面字体 */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>{text('界面字体', 'Interface font')}</p>
            <p className="text-[0.68rem] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
              {text('左侧栏、菜单、对话框等 UI 区域', 'Sidebars, menus, dialogs, and other interface areas')}
            </p>
          </div>
        </div>
        <FontSelect value={uiFont} onChange={setUiFont} />
      </div>

      {/* 写作字体 */}
      <div className="space-y-1.5">
        <div>
          <p className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>{text('写作字体', 'Writing font')}</p>
          <p className="text-[0.68rem] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            {text('草稿、终稿、架构文档等正文区域', 'Drafts, manuscripts, and architecture documents')}
          </p>
        </div>
        <FontSelect value={writingFont} onChange={setWritingFont} />
      </div>

      {/* 说明 */}
      <div
        className="flex items-start gap-2 px-3 py-2.5 rounded-lg text-xs"
        style={{ backgroundColor: 'var(--color-hover)', color: 'var(--color-text-muted)' }}
      >
        <span className="flex-shrink-0 mt-0.5" style={{ color: 'var(--color-text-muted)' }}>{text('提示', 'Note')}</span>
        <span>{text('所有字体已内置在应用中，无需网络连接，切换后立即生效。', 'All fonts are bundled with the app and switch immediately without a network connection.')}</span>
      </div>
    </div>
  )
}

// ==================== 关于区 ====================

function AboutSection() {
  const text = useLocaleStore(s => s.text)
  return (
    <div className="space-y-6 max-w-[600px] p-2">
      <div
        className="flex flex-col items-center justify-center py-8 rounded-xl space-y-2"
        style={{ backgroundColor: 'var(--color-sidebar)', border: '1px solid var(--color-border)' }}
      >
        <h1 className="text-2xl font-bold brand-gradient tracking-wider">{text(APP_BRAND.zhName, APP_BRAND.enName)}</h1>
        <p className="text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>{APP_BRAND.enName}</p>
        <p className="text-sm opacity-80" style={{ color: 'var(--color-text)' }}>v{__APP_VERSION__}</p>
      </div>

      <div className="space-y-3 pt-2">
        <h3
          className="text-sm font-semibold pb-2"
          style={{ borderBottom: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          {text('本地写作工作台', 'Local writing workspace')}
        </h3>
        <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          {text('这是面向中文长篇小说、角色设定、章节蓝图和本地模型生成的桌面写作环境。默认优先使用本机模型与本地项目数据，适合离线创作、风格拆解、章节规划和长文续写。', 'A desktop writing environment for long-form fiction, character design, chapter blueprints, and local model generation. It prioritizes local models and project data for offline writing, style analysis, planning, and continuation.')}
        </p>
      </div>

      <div
        className="grid grid-cols-2 gap-3 pt-2"
        style={{ color: 'var(--color-text-muted)' }}
      >
        <div className="rounded-xl p-3" style={{ border: '1px solid var(--color-border)', backgroundColor: 'var(--color-panel)' }}>
          <div className="text-xs font-semibold mb-1" style={{ color: 'var(--color-text)' }}>{text('核心流程', 'Core pipeline')}</div>
          <p className="text-xs leading-relaxed">{text('架构、角色、蓝图、草稿、评审、修订、定稿。', 'Architecture, characters, blueprints, drafts, reviews, revisions, and final manuscripts.')}</p>
        </div>
        <div className="rounded-xl p-3" style={{ border: '1px solid var(--color-border)', backgroundColor: 'var(--color-panel)' }}>
          <div className="text-xs font-semibold mb-1" style={{ color: 'var(--color-text)' }}>{text('模型连接', 'Model connections')}</div>
          <p className="text-xs leading-relaxed">{text('支持 OpenAI 兼容接口、Ollama、本地与自定义供应商。', 'Supports OpenAI-compatible APIs, Ollama, local models, and custom providers.')}</p>
        </div>
      </div>
    </div>
  )
}

// ==================== 工具函数 ====================

function providerIcon(provider: string) {
  const commonProps = { size: 18, strokeWidth: 1.8 }

  switch (provider) {
    case 'openai':
      return <Zap {...commonProps} />
    case 'deepseek':
      return <Database {...commonProps} />
    case 'gemini':
      return <Globe {...commonProps} />
    case 'ollama':
      return <Cpu {...commonProps} />
    case 'bigmodel':
      return <MessageSquare {...commonProps} />
    case 'custom':
      return <Settings2 {...commonProps} />
    default:
      return <Cpu {...commonProps} />
  }
}
