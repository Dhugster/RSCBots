import './style.css'

const API = '/api'

type Bot = {
  bot_id: string
  account_name: string
  username: string
  script_name: string
  script_args: string[]
  status: string
  runtime_formatted: string
  xp_per_hour: number
  items_collected: number
}

type Preset = { name: string; script: string; args: string[] }

let bots: Bot[] = []
let presets: Preset[] = []
let scriptsList: string[] = []
let selectedIds = new Set<string>()
let logViewCleared = false

async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(API + path, { ...opts, headers: { 'Content-Type': 'application/json', ...opts?.headers } })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || r.statusText)
  }
  return r.json()
}

function botsEqual(a: Bot[], b: Bot[]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    const x = a[i], y = b[i]
    if (x.bot_id !== y.bot_id || x.status !== y.status || x.script_name !== y.script_name ||
        x.runtime_formatted !== y.runtime_formatted || (x.script_args?.join(',') !== y.script_args?.join(',')))
      return false
  }
  return true
}

/** Fetch latest bots and update in-memory state only (no DOM update). */
async function syncBots(): Promise<void> {
  bots = await api<Bot[]>('/bots')
}

async function loadBots(forceRender = false) {
  const next = await api<Bot[]>('/bots')
  if (!forceRender && botsEqual(bots, next)) return
  bots = next
  render()
}

async function loadPresets() {
  presets = await api<Preset[]>('/presets')
}

async function loadScripts() {
  const data = await api<{ scripts: string[] }>('/scripts')
  scriptsList = data.scripts && data.scripts.length ? data.scripts : ['', 'FishingBot', 'MiningBot', 'CombatBot', 'HarvestBot']
}

async function startBot(botId: string) {
  await api(`/bots/${botId}/start`, { method: 'POST' })
  await loadBots()
}

async function stopBot(botId: string) {
  await api(`/bots/${botId}/stop`, { method: 'POST' })
  await loadBots()
}

async function setBotScript(botId: string, scriptName: string, scriptArgs?: string[]) {
  await api(`/bots/${botId}`, {
    method: 'PUT',
    body: JSON.stringify({
      script_name: scriptName,
      ...(scriptArgs !== undefined && { script_args: scriptArgs }),
    }),
  })
  await syncBots()
}

async function applyPreset(presetName: string) {
  const ids = selectedIds.size ? [...selectedIds] : bots.map(b => b.bot_id)
  await api('/bots/apply-preset', {
    method: 'POST',
    body: JSON.stringify({ bot_ids: ids, preset_name: presetName }),
  })
  await syncBots()
}

async function applyScriptToBots(scriptName: string, botIds: string[]) {
  for (const id of botIds) {
    await setBotScript(id, scriptName)
  }
}

async function deleteBot(botId: string) {
  if (!confirm(`Delete bot "${botId}"?`)) return
  await api(`/bots/${botId}`, { method: 'DELETE' })
  selectedIds.delete(botId)
  await loadBots()
}

function toggleSelect(botId: string) {
  if (selectedIds.has(botId)) selectedIds.delete(botId)
  else selectedIds.add(botId)
  const cb = document.querySelector(`.bot-select[data-bot-id="${botId}"]`) as HTMLInputElement | null
  if (cb) cb.checked = selectedIds.has(botId)
}

function statusColor(s: string): string {
  if (s === 'running') return 'var(--status-run)'
  if (s === 'idle' || s === 'stopped') return 'var(--status-idle)'
  if (s === 'error' || s === 'crashed') return 'var(--status-err)'
  if (s === 'disconnected') return 'var(--status-disco)'
  return 'var(--text-muted)'
}

function scriptSelectOptions(): string {
  return scriptsList.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s || '(none)')}</option>`).join('')
}

function render() {
  const root = document.querySelector<HTMLDivElement>('#app')!
  root.innerHTML = ''
  const el = document.createElement('div')
  el.className = 'dashboard'

  const header = document.createElement('header')
  header.className = 'header'
  header.innerHTML = `
    <h1>IdleRSC Manager</h1>
    <p class="subtitle">Coleslaw World · Dashboard</p>
    <button type="button" class="btn btn-ghost" id="btn-refresh">Refresh</button>
  `
  el.appendChild(header)

  const main = document.createElement('main')
  main.className = 'main'

  const botSection = document.createElement('section')
  botSection.className = 'bot-section'
  botSection.innerHTML = '<h2>Bots</h2>'

  const grid = document.createElement('div')
  grid.className = 'bot-grid'
  for (const b of bots) {
    const card = document.createElement('div')
    card.className = 'bot-card'
    card.dataset.botId = b.bot_id
    const argsStr = b.script_args?.length ? b.script_args.join(', ') : '—'
    const isSelected = selectedIds.has(b.bot_id)
    const currentScript = b.script_name || ''
    card.innerHTML = `
      <div class="bot-card-header">
        <input type="checkbox" ${isSelected ? 'checked' : ''} data-bot-id="${b.bot_id}" class="bot-select" />
        <span class="bot-id">${escapeHtml(b.bot_id)}</span>
        <span class="bot-status" style="color:${statusColor(b.status)}">${escapeHtml(b.status)}</span>
      </div>
      <div class="bot-card-body">
        <div class="bot-row"><span class="label">User</span> ${escapeHtml(b.username)}</div>
        <div class="bot-row bot-row-script">
          <span class="label">Script</span>
          <select class="script-select" data-bot-id="${b.bot_id}" data-action="script-change">
            ${scriptsList.map(s => `<option value="${escapeHtml(s)}" ${s === currentScript ? 'selected' : ''}>${escapeHtml(s || '(none)')}</option>`).join('')}
          </select>
        </div>
        <div class="bot-row"><span class="label">Args</span> ${escapeHtml(argsStr)}</div>
        <div class="bot-row"><span class="label">Runtime</span> ${escapeHtml(b.runtime_formatted)}</div>
        <div class="bot-actions">
          ${b.status === 'running'
            ? `<button type="button" class="btn btn-danger btn-sm" data-action="stop">Stop</button>`
            : `<button type="button" class="btn btn-success btn-sm" data-action="start">Start</button>`
          }
          <button type="button" class="btn btn-ghost btn-sm" data-action="delete">Delete</button>
        </div>
      </div>
    `
    grid.appendChild(card)
  }
  botSection.appendChild(grid)

  // Apply script to selected / all
  const applyScriptRow = document.createElement('div')
  applyScriptRow.className = 'preset-row'
  applyScriptRow.innerHTML = `
    <span class="label">Script for selected or all:</span>
    <select class="apply-script-select" id="apply-script-select">
      ${scriptSelectOptions()}
    </select>
    <button type="button" class="btn btn-sm" id="btn-apply-selected">To selected</button>
    <button type="button" class="btn btn-sm" id="btn-apply-all">To all</button>
  `
  botSection.appendChild(applyScriptRow)

  if (presets.length) {
    const presetRow = document.createElement('div')
    presetRow.className = 'preset-row'
    presetRow.innerHTML = `<span class="label">Or apply preset to selected:</span>`
    const presetBtns = document.createElement('div')
    presetBtns.className = 'preset-btns'
    for (const p of presets) {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'btn btn-sm'
      btn.textContent = p.name
      btn.onclick = () => applyPreset(p.name)
      presetBtns.appendChild(btn)
    }
    presetRow.appendChild(presetBtns)
    botSection.appendChild(presetRow)
  }

  main.appendChild(botSection)

  const logSection = document.createElement('section')
  logSection.className = 'log-section'
  const logHeader = document.createElement('div')
  logHeader.className = 'log-section-header'
  logHeader.innerHTML = '<h2>Logs</h2><button type="button" class="btn btn-ghost btn-sm" id="btn-clear-log">Clear</button>'
  logSection.appendChild(logHeader)
  const logPre = document.createElement('pre')
  logPre.className = 'log-view'
  logPre.id = 'log-view'
  logPre.textContent = 'Loading…'
  logSection.appendChild(logPre)
  main.appendChild(logSection)

  el.appendChild(main)

  const addSection = document.createElement('section')
  addSection.className = 'add-section'
  addSection.innerHTML = `
    <h2>Add account</h2>
    <form id="form-add-bot" class="form-add">
      <input name="bot_id" placeholder="Bot ID" required />
      <input name="username" placeholder="Username" required />
      <input name="password" type="password" placeholder="Password" required />
      <select name="script_name">
        ${scriptSelectOptions()}
      </select>
      <input name="script_args" placeholder="Args (optional, comma-separated)" />
      <button type="submit" class="btn btn-primary">Add</button>
    </form>
  `
  el.appendChild(addSection)

  root.appendChild(el)

  el.addEventListener('change', (e) => {
    const t = e.target as HTMLInputElement
    if (t.classList.contains('bot-select') && t.dataset.botId) toggleSelect(t.dataset.botId)
    const sel = (e.target as HTMLElement).closest('.script-select') as HTMLSelectElement | null
    if (sel?.dataset.botId) {
      setBotScript(sel.dataset.botId, sel.value)
    }
  })
  el.addEventListener('click', async (e) => {
    const btn = (e.target as HTMLElement).closest('[data-action]') as HTMLElement | null
    if (!btn) return
    const card = btn.closest('.bot-card')
    const botId = card?.getAttribute('data-bot-id')
    if (botId) {
      if (btn.dataset.action === 'start') await startBot(botId)
      if (btn.dataset.action === 'stop') await stopBot(botId)
      if (btn.dataset.action === 'delete') await deleteBot(botId)
    }
  })

  const applySelect = document.getElementById('apply-script-select') as HTMLSelectElement
  document.getElementById('btn-apply-selected')?.addEventListener('click', async () => {
    const script = applySelect?.value ?? ''
    const ids = selectedIds.size ? [...selectedIds] : []
    if (!ids.length) { alert('Select at least one bot, or use "To all".'); return }
    await applyScriptToBots(script, ids)
  })
  document.getElementById('btn-apply-all')?.addEventListener('click', async () => {
    const script = applySelect?.value ?? ''
    await applyScriptToBots(script, bots.map(b => b.bot_id))
  })

  header.querySelector('#btn-refresh')?.addEventListener('click', () => {
    logViewCleared = false
    loadBots(true)
  })

  document.getElementById('btn-clear-log')?.addEventListener('click', () => {
    logViewCleared = true
    const pre = document.getElementById('log-view')
    if (pre) pre.textContent = ''
  })

  document.getElementById('form-add-bot')?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const form = e.target as HTMLFormElement
    const fd = new FormData(form)
    const scriptArgsRaw = (fd.get('script_args') as string)?.trim()
    const script_args = scriptArgsRaw ? scriptArgsRaw.split(',').map(s => s.trim()).filter(Boolean) : []
    try {
      await api('/bots', {
        method: 'POST',
        body: JSON.stringify({
          bot_id: fd.get('bot_id'),
          account_name: fd.get('username'),
          username: fd.get('username'),
          password: fd.get('password'),
          script_name: (fd.get('script_name') as string) ?? '',
          script_args,
        }),
      })
      form.reset()
      await loadBots()
    } catch (err) {
      alert((err as Error).message)
    }
  })

  api<{ lines: string[] }>('/logs?tail=80').then(({ lines }) => {
    if (logViewCleared) return
    const pre = document.getElementById('log-view')
    if (pre) {
      pre.textContent = lines.length ? lines.join('\n') : 'No log output yet.'
      requestAnimationFrame(() => { pre.scrollTop = pre.scrollHeight })
    }
  }).catch(() => {})
}

function escapeHtml(s: string): string {
  const div = document.createElement('div')
  div.textContent = s
  return div.innerHTML
}

async function init() {
  try {
    await loadScripts()
    await loadPresets()
    await loadBots()
  } catch (e) {
    document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
      <div class="dashboard error">
        <h1>IdleRSC Manager</h1>
        <p>Cannot reach API. Start the server:</p>
        <pre>cd idlersc_manager && uvicorn api_server:app --host 127.0.0.1 --port 8000</pre>
        <p><small>${escapeHtml((e as Error).message)}</small></p>
      </div>
    `
  }
}

init()
setInterval(() => loadBots(), 15000)
