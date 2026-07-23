import { useState, useEffect } from 'react'
import { Plus, Trash2, Check, Zap, Save, Globe, CheckCircle2, XCircle } from 'lucide-react'
import { useLLMStore } from '../../stores/llm-store'
import type { ModelProfile } from '../../shared/ipc-channels'
import { randomUUID } from '../../utils/id'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Label } from '../ui/Label'
import { NativeSelect } from '../ui/NativeSelect'
import { cn } from '../../lib/utils'
import { useLocaleStore } from '../../stores/locale-store'

/** 模型设置面板 — 在侧边栏 settings 视图中展示 */
export default function ModelSettings() {
  const text = useLocaleStore(s => s.text)
  const models = useLLMStore(s => s.models)
  const defaultModelId = useLLMStore(s => s.defaultModelId)
  const loaded = useLLMStore(s => s.loaded)
  const loadModels = useLLMStore(s => s.loadModels)
  const saveModel = useLLMStore(s => s.saveModel)
  const deleteModel = useLLMStore(s => s.deleteModel)
  const setDefaultModel = useLLMStore(s => s.setDefaultModel)
  const [editingModel, setEditingModel] = useState<ModelProfile | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!loaded) loadModels()
  }, [loaded, loadModels])

  /** 创建新模型配置 */
  const handleAddModel = () => {
    setEditingModel({
      id: randomUUID(),
      name: '',
      provider: 'openai',
      protocol: 'openai',
      modelName: 'gpt-4o',
      apiKey: '',
      baseUrl: 'https://api.openai.com',
      temperature: 0.7,
      maxTokens: 4096,
      purposes: ['generation'],
    })
  }

  /** 保存模型 */
  const handleSave = async () => {
    if (!editingModel) return
    setSaving(true)
    await saveModel(editingModel)
    setEditingModel(null)
    setSaving(false)
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 标题栏 */}
      <div className="panel-header flex items-center justify-between">
        <span>{text('模型配置', 'Model profiles')}</span>
        <Button variant="ghost" size="icon" onClick={handleAddModel} title={text('添加模型', 'Add model')}>
          <Plus size={16} />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {/* 编辑表单 */}
        {editingModel && (
          <ModelForm
            model={editingModel}
            onChange={setEditingModel}
            onSave={handleSave}
            onCancel={() => setEditingModel(null)}
            saving={saving}
          />
        )}

        {/* 空状态 */}
        {!editingModel && models.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 gap-3 opacity-40">
            <Zap size={32} />
            <span className="text-sm">{text('暂无模型配置', 'No model profiles yet')}</span>
            <Button onClick={handleAddModel} size="sm">{text('添加第一个模型', 'Add your first model')}</Button>
          </div>
        )}

        {/* 模型列表 */}
        {!editingModel && models.map((model) => (
          <div
            key={model.id}
            className={cn(
              'p-3 rounded-lg cursor-pointer group bg-[var(--color-panel)] border',
              defaultModelId === model.id ? 'border-[var(--color-accent)]' : 'border-[var(--color-border)]'
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-sm text-[var(--color-text)]">
                {model.name || model.modelName}
              </span>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {defaultModelId !== model.id && (
                  <Button variant="ghost" size="icon" onClick={() => setDefaultModel(model.id)} title={text('设为默认', 'Set as default')}>
                    <Check size={14} />
                  </Button>
                )}
                <Button variant="ghost" size="icon" onClick={() => setEditingModel({ ...model })} title={text('编辑', 'Edit')}>
                  <Save size={14} />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => deleteModel(model.id)} title={text('删除', 'Delete')} className="hover:text-red-400">
                  <Trash2 size={14} />
                </Button>
              </div>
            </div>
            <div className="text-xs text-[var(--color-text-muted)]">
              {model.provider} · {model.modelName}
              {defaultModelId === model.id && (
                <span className="ml-2 px-1.5 py-0.5 rounded text-[0.7rem] bg-[var(--color-accent)] text-white">
                  {text('默认', 'Default')}
                </span>
              )}
            </div>
          </div>
        ))}

        {/* 代理配置 */}
        {!editingModel && (
          <ProxySettings />
        )}
      </div>
    </div>
  )
}

/** 模型编辑表单 */
function ModelForm({
  model,
  onChange,
  onSave,
  onCancel,
  saving,
}: {
  model: ModelProfile
  onChange: (m: ModelProfile) => void
  onSave: () => void
  onCancel: () => void
  saving: boolean
}) {
  const text = useLocaleStore(s => s.text)
  const testConnection = useLLMStore(s => s.testConnection)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean, error?: string } | null>(null)

  const update = <K extends keyof ModelProfile>(key: K, value: ModelProfile[K]) => {
    onChange({ ...model, [key]: value })
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    const result = await testConnection(model)
    setTestResult(result)
    setTesting(false)
    setTimeout(() => setTestResult(null), 3000)
  }

  return (
    <div className="p-3 rounded-lg space-y-3 bg-[var(--color-panel)] border border-[var(--color-accent)]">
      <div>
        <Label>{text('名称', 'Name')}</Label>
        <Input value={model.name} onChange={(e) => update('name', e.target.value)} placeholder={text('如：GPT-4o 主力', 'e.g. Primary GPT-4o')} />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label>{text('服务商', 'Provider')}</Label>
          <NativeSelect value={model.provider} onChange={(e) => update('provider', e.target.value as ModelProfile['provider'])}>
            <option value="openai">OpenAI</option>
            <option value="deepseek">DeepSeek</option>
            <option value="gemini">Gemini</option>
            <option value="nebius">Nebius Token Factory</option>
            <option value="ollama">Ollama</option>
            <option value="custom">{text('自定义', 'Custom')}</option>
          </NativeSelect>
        </div>
        <div>
          <Label>{text('协议', 'Protocol')}</Label>
          <NativeSelect value={model.protocol} onChange={(e) => update('protocol', e.target.value as ModelProfile['protocol'])}>
            <option value="openai">{text('OpenAI 兼容', 'OpenAI compatible')}</option>
            <option value="gemini">Gemini</option>
          </NativeSelect>
        </div>
      </div>

      <div>
        <Label>{text('模型名称', 'Model name')}</Label>
        <Input value={model.modelName} onChange={(e) => update('modelName', e.target.value)} placeholder="gpt-4o / deepseek-chat" />
      </div>
      <div>
        <Label>{text('API 地址', 'API endpoint')}</Label>
        <Input value={model.baseUrl} onChange={(e) => update('baseUrl', e.target.value)} placeholder="https://api.openai.com" />
      </div>
      <div>
        <Label>API Key</Label>
        <Input type="password" value={model.apiKey} onChange={(e) => update('apiKey', e.target.value)} placeholder="sk-..." />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label>{text('温度', 'Temperature')}</Label>
          <Input
            value={String(model.temperature)}
            onChange={(e) => update('temperature', (e.target.value === '' ? '' : parseFloat(e.target.value)) as number)}
            onBlur={() => {
              const v = Number(model.temperature);
              if (isNaN(v)) update('temperature', 0.7);
            }}
          />
        </div>
        <div>
          <Label>{text('最大 Tokens', 'Max tokens')}</Label>
          <Input
            value={String(model.maxTokens)}
            onChange={(e) => update('maxTokens', (e.target.value === '' ? '' : parseInt(e.target.value)) as number)}
            onBlur={() => {
              const v = Number(model.maxTokens);
              if (!v || v < 1) update('maxTokens', 4096);
            }}
          />
        </div>
      </div>

      {/* 操作按钮 */}
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
          {saving ? text('保存中...', 'Saving...') : text('保存', 'Save')}
        </Button>
        <Button variant="ghost" onClick={onCancel}>{text('取消', 'Cancel')}</Button>
      </div>
      {testResult && (
        <div className={`text-xs p-2 rounded ${testResult.success ? 'bg-green-500/10 text-green-500 border border-green-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'} break-all`}>
          {testResult.success
            ? <><CheckCircle2 size={13} className="inline mr-1" />{text('连接成功！', 'Connection succeeded!')}</>
            : <><XCircle size={13} className="inline mr-1" />{text('连接失败：{error}', 'Connection failed: {error}', { error: testResult.error ?? '' })}</>}
        </div>
      )}
    </div>
  )
}

/** 代理配置面板 */
function ProxySettings() {
  const text = useLocaleStore(s => s.text)
  const [proxy, setProxy] = useState<{
    enabled: boolean; type: 'http' | 'socks5'; host: string; port: number
  }>({ enabled: false, type: 'http', host: '', port: 7890 })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const loadProxy = async () => {
      try {
        const { ipc } = await import('../../services/ipc-client')
        const config = await ipc.invoke('config:get')
        if (config.proxy) setProxy(config.proxy)
      } catch { /* 忽略 */ }
    }
    void loadProxy()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const { ipc } = await import('../../services/ipc-client')
      await ipc.invoke('config:set', { proxy })
    } catch { /* 忽略 */ }
    setSaving(false)
  }

  return (
    <div className="mt-4 p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-panel)]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-[var(--color-text)] flex items-center gap-1">
          <Globe size={13} /> {text('代理配置', 'Proxy settings')}
        </span>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={proxy.enabled}
            onChange={(e) => setProxy({ ...proxy, enabled: e.target.checked })}
            className="rounded"
          />
          <span className="text-[0.7rem] text-[var(--color-text-muted)]">
            {proxy.enabled ? text('已启用', 'Enabled') : text('已禁用', 'Disabled')}
          </span>
        </label>
      </div>
      {proxy.enabled && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Label className="text-[0.7rem] w-12 flex-shrink-0">{text('类型', 'Type')}</Label>
            <NativeSelect
              value={proxy.type}
              onChange={(e) => setProxy({ ...proxy, type: e.target.value as 'http' | 'socks5' })}
              className="h-7 text-xs"
            >
              <option value="http">HTTP</option>
              <option value="socks5">SOCKS5</option>
            </NativeSelect>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-[0.7rem] w-12 flex-shrink-0">{text('主机', 'Host')}</Label>
            <Input
              className="h-7 text-xs flex-1"
              value={proxy.host}
              onChange={(e) => setProxy({ ...proxy, host: e.target.value })}
              placeholder="127.0.0.1"
            />
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-[0.7rem] w-12 flex-shrink-0">{text('端口', 'Port')}</Label>
            <Input
              className="h-7 text-xs w-24"
              type="number"
              value={proxy.port}
              onChange={(e) => setProxy({ ...proxy, port: (e.target.value === '' ? '' : parseInt(e.target.value)) as number })}
              onBlur={() => {
                const v = Number(proxy.port);
                if (!v) setProxy({ ...proxy, port: 7890 });
              }}
            />
          </div>
          <Button variant="outline" size="sm" onClick={handleSave} disabled={saving} className="w-full mt-2">
            <Save size={12} /> {saving ? text('保存中...', 'Saving...') : text('保存代理配置', 'Save proxy settings')}
          </Button>
        </div>
      )}
    </div>
  )
}
