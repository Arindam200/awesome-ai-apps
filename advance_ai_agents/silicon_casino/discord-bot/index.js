import fetch from 'node-fetch'
import { AttachmentBuilder } from 'discord.js'
import { Client, GatewayIntentBits, REST, Routes, SlashCommandBuilder } from 'discord.js'

const token = process.env.DISCORD_BOT_TOKEN
const appId = process.env.DISCORD_APP_ID
const guildId = process.env.DISCORD_GUILD_ID
const channelId = process.env.DISCORD_CHANNEL_ID
const apiBase = process.env.API_BASE || 'http://localhost:8080'
const adminKey = process.env.ADMIN_API_KEY || ''
const allinThreshold = parseInt(process.env.ALLIN_THRESHOLD || '20000', 10)

if (!token || !appId || !channelId) {
  console.error('Missing DISCORD_BOT_TOKEN / DISCORD_APP_ID / DISCORD_CHANNEL_ID')
  process.exit(1)
}

const client = new Client({ intents: [GatewayIntentBits.Guilds] })

const commands = [
  new SlashCommandBuilder().setName('watch').setDescription('Get current spectate link'),
  new SlashCommandBuilder().setName('leaderboard').setDescription('Show top agents by CC')
].map((c) => c.toJSON())

const rest = new REST({ version: '10' }).setToken(token)

async function registerCommands() {
  if (guildId) {
    await rest.put(Routes.applicationGuildCommands(appId, guildId), { body: commands })
  } else {
    await rest.put(Routes.applicationCommands(appId), { body: commands })
  }
}

client.on('ready', async () => {
  console.log(`Bot logged in as ${client.user.tag}`)
  try {
    await registerCommands()
  } catch (e) {
    console.error('register commands failed', e)
  }
  startWatcher()
})

client.on('interactionCreate', async (interaction) => {
  if (!interaction.isChatInputCommand()) return
  if (interaction.commandName === 'watch') {
    await interaction.reply(`Spectate: ${apiBase}`)
    return
  }
  if (interaction.commandName === 'leaderboard') {
    const data = await fetchLeaderboard()
    const lines = data.slice(0, 10).map((e, i) => `${i + 1}. ${e.name} (${e.net_cc})`).join('\n')
    await interaction.reply(lines || 'No data')
  }
})

async function fetchLeaderboard() {
  const headers = adminKey ? { Authorization: `Bearer ${adminKey}` } : {}
  const res = await fetch(`${apiBase}/api/leaderboard?limit=10`, { headers })
  if (!res.ok) return []
  return res.json()
}

function handleSpectatorMessage(msg) {
  if (msg.type === 'state_update') {
    if (msg.pot && msg.pot >= allinThreshold) {
      sendChannel(`All-in Alert: pot=${msg.pot}`)
    }
    return
  }
  if (msg.type !== 'hand_end') return
  if (!Array.isArray(msg.balances)) return
  msg.balances.forEach((b) => {
    if (b.balance <= 0) {
      const file = new AttachmentBuilder(new URL('./tombstone.svg', import.meta.url))
      sendChannelWithFile(`Death Notice: ${b.agent_id} is bankrupt`, file)
    }
  })
}

function parseSSEChunk(chunk, state) {
  state.buffer += chunk
  const lines = state.buffer.split('\n')
  state.buffer = lines.pop() || ''
  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    if (line.startsWith('data: ')) {
      state.data = line.slice(6)
      continue
    }
    if (line !== '' || !state.data) {
      continue
    }
    try {
      const envelope = JSON.parse(state.data)
      const evt = envelope?.event
      const data = envelope?.data || {}
      if (evt === 'table_snapshot') {
        handleSpectatorMessage({ type: 'state_update', ...data })
      } else if (evt === 'hand_end') {
        handleSpectatorMessage({ type: 'hand_end', ...data })
      }
    } catch (_) {
      // ignore malformed events
    }
    state.data = ''
  }
}

async function startWatcher() {
  while (true) {
    try {
      const res = await fetch(`${apiBase}/api/public/spectate/events`, {
        headers: { accept: 'text/event-stream' }
      })
      if (!res.ok || !res.body) {
        throw new Error(`sse connect failed (${res.status})`)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      const state = { buffer: '', data: '' }
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        parseSSEChunk(decoder.decode(value, { stream: true }), state)
      }
    } catch (_) {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 2000))
  }
}

async function sendChannel(text) {
  try {
    const channel = await client.channels.fetch(channelId)
    if (channel) channel.send(text)
  } catch (e) {
    console.error('send failed', e)
  }
}

async function sendChannelWithFile(text, file) {
  try {
    const channel = await client.channels.fetch(channelId)
    if (channel) channel.send({ content: text, files: [file] })
  } catch (e) {
    console.error('send failed', e)
  }
}

client.login(token)
