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
  total_xp_gained?: number
  profit?: number
}

type Position = { tile_x: number; tile_y: number; layer: string }
type Positions = Record<string, Position>

type AnalyticsSummary = {
  total_xp_per_hour: number
  total_items_collected: number
  total_profit: number
  by_script: Record<string, { bot_ids: string[]; count: number; xp_per_hour: number; items_collected: number; profit: number }>
}

type Preset = { name: string; script: string; args: string[] }

let bots: Bot[] = []
let positions: Positions = {}
let presets: Preset[] = []
let scriptsList: string[] = []
let selectedIds = new Set<string>()
let logViewCleared = false
let mapPollTimer: number | null = null

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
  renderNav(el)

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

function getRoute(): 'dashboard' | 'map' | 'analytics' {
  const h = window.location.hash.replace(/^#\/?/, '') || 'dashboard'
  if (h === 'map') return 'map'
  if (h === 'analytics') return 'analytics'
  return 'dashboard'
}

function renderNav(container: HTMLElement) {
  const nav = document.createElement('nav')
  nav.className = 'top-nav'
  const r = getRoute()
  nav.innerHTML = `
    <a href="#/" class="nav-link ${r === 'dashboard' ? 'active' : ''}">Dashboard</a>
    <a href="#/map" class="nav-link ${r === 'map' ? 'active' : ''}">Map</a>
    <a href="#/analytics" class="nav-link ${r === 'analytics' ? 'active' : ''}">Analytics</a>
  `
  container.appendChild(nav)
}

async function loadPositions(): Promise<Positions> {
  try {
    positions = await api<Positions>('/bots/positions')
  } catch {
    positions = {}
  }
  return positions
}

// --- Map view ---
const MAP_LAYERS = [
  { id: 'surface', label: 'Surface', file: '/maps/surface.svg' },
  { id: 'floor1', label: '1st Floor', file: '/maps/floor1.svg' },
  { id: 'floor2', label: '2nd Floor', file: '/maps/floor2.svg' },
  { id: 'dungeon', label: 'Dungeon', file: '/maps/dungeon.svg' },
]

function renderMapView() {
  const root = document.querySelector<HTMLDivElement>('#app')!
  root.innerHTML = ''
  const el = document.createElement('div')
  el.className = 'map-page'
  renderNav(el)

  let currentLayer = 'surface'
  const runningBots = bots.filter(b => b.status === 'running')
  const byLayer: Record<string, Bot[]> = { surface: [], floor1: [], floor2: [], dungeon: [] }
  for (const b of runningBots) {
    const pos = positions[b.bot_id]
    const layer = (pos?.layer || 'surface') as keyof typeof byLayer
    if (byLayer[layer]) byLayer[layer].push(b)
    else byLayer.surface.push(b)
  }

  const totalsXp = runningBots.reduce((s, b) => s + (b.xp_per_hour || 0), 0)
  const totalsItems = runningBots.reduce((s, b) => s + (b.items_collected || 0), 0)
  const totalsProfit = runningBots.reduce((s, b) => s + ((b as Bot).profit ?? 0), 0)

  const header = document.createElement('header')
  header.className = 'map-header'
  header.innerHTML = `
    <h1>World Map</h1>
    <a href="#/analytics" class="map-totals">Total: ${formatXp(totalsXp)}/hr | ${totalsItems} items | ${formatProfit(totalsProfit)} gp</a>
  `
  el.appendChild(header)

  const mapWrap = document.createElement('div')
  mapWrap.className = 'map-wrap'
  const mapContainer = document.createElement('div')
  mapContainer.className = 'map-container'
  const mapImg = document.createElement('img')
  mapImg.alt = 'Map'
  mapImg.className = 'map-image'
  function setLayer(layer: string) {
    currentLayer = layer
    const spec = MAP_LAYERS.find(l => l.id === layer) || MAP_LAYERS[0]
    mapImg.src = spec.file
    mapContainer.querySelectorAll('.layer-btn').forEach((btn) => {
      (btn as HTMLElement).classList.toggle('active', (btn as HTMLElement).dataset.layer === layer)
    })
    mapContainer.querySelectorAll('.map-marker').forEach((m) => {
      const layerMatch = (m as HTMLElement).dataset.layer === layer
      ;(m as HTMLElement).style.display = layerMatch ? '' : 'none'
    })
  }
  setLayer('surface')
  mapContainer.appendChild(mapImg)

  const layerBtns = document.createElement('div')
  layerBtns.className = 'layer-btns'
  MAP_LAYERS.forEach((l) => {
    const count = byLayer[l.id as keyof typeof byLayer]?.length ?? 0
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'layer-btn'
    btn.dataset.layer = l.id
    btn.textContent = count > 0 ? `${l.label} (${count})` : l.label
    if (l.id === currentLayer) btn.classList.add('active')
    btn.onclick = () => setLayer(l.id)
    layerBtns.appendChild(btn)
  })
  mapContainer.appendChild(layerBtns)

  const tileInfo = document.createElement('div')
  tileInfo.className = 'map-tile-info'
  tileInfo.textContent = 'Tile: —'
  mapContainer.appendChild(tileInfo)

  // Markers (placeholder positions if no position store: use index for demo)
  const scale = 0.4
  Object.entries(positions).forEach(([bid, pos]) => {
    if (pos.layer !== currentLayer) return
    const bot = bots.find(b => b.bot_id === bid)
    const mx = 100 + (pos.tile_x % 700) * scale
    const my = 80 + (pos.tile_y % 500) * scale
    const marker = document.createElement('div')
    marker.className = 'map-marker'
    marker.dataset.botId = bid
    marker.dataset.layer = pos.layer
    marker.style.left = `${mx}px`
    marker.style.top = `${my}px`
    marker.title = bot?.username || bid
    marker.textContent = bot?.username || bid
    marker.onclick = (e) => {
      e.stopPropagation()
      renderMapPopup(el, bot || undefined)
    }
    mapContainer.appendChild(marker)
  })

  mapWrap.appendChild(mapContainer)

  const sidebar = document.createElement('aside')
  sidebar.className = 'map-sidebar'
  sidebar.innerHTML = '<h3>World Map</h3><div class="sidebar-tabs"><span class="tab active">Players</span></div>'
  const playerList = document.createElement('div')
  playerList.className = 'player-list'
  const groups = [
    { label: 'SURFACE', layer: 'surface' },
    { label: 'DUNGEON', layer: 'dungeon' },
    { label: '1ST FLOOR', layer: 'floor1' },
    { label: '2ND FLOOR', layer: 'floor2' },
  ]
  groups.forEach(({ label, layer }) => {
    const list = byLayer[layer as keyof typeof byLayer] || []
    if (list.length === 0) return
    const heading = document.createElement('div')
    heading.className = 'player-group-label'
    heading.textContent = `${label} (${list.length})`
    playerList.appendChild(heading)
    list.forEach((b) => {
      const row = document.createElement('div')
      row.className = 'player-row'
      row.dataset.botId = b.bot_id
      const tag = layer === 'surface' ? 'Sfc' : layer === 'dungeon' ? 'Dng' : layer === 'floor1' ? 'F1' : 'F2'
      row.innerHTML = `
        <span class="player-dot running"></span>
        <span class="player-name">${escapeHtml(b.username)}</span>
        <span class="player-xp">${formatXp(b.xp_per_hour || 0)}/h</span>
        <span class="player-script">${escapeHtml(b.script_name || '—')}</span>
        <span class="player-tag">${tag}</span>
      `
      row.onclick = () => renderMapPopup(el, b)
      playerList.appendChild(row)
    })
  })
  if (playerList.children.length === 0) {
    playerList.innerHTML = '<p class="dim">No running bots. Start bots from Dashboard.</p>'
  }
  sidebar.appendChild(playerList)
  mapWrap.appendChild(sidebar)
  el.appendChild(mapWrap)

  root.appendChild(el)
}

function renderMapPopup(parent: HTMLElement, bot: Bot | undefined) {
  parent.querySelectorAll('.map-popup').forEach((p) => p.remove())
  if (!bot) return
  const pos = positions[bot.bot_id]
  const popup = document.createElement('div')
  popup.className = 'map-popup'
  popup.innerHTML = `
    <div class="map-popup-inner">
      <h4>${escapeHtml(bot.username)}</h4>
      <p><strong>Position</strong> ${pos ? `(${pos.tile_x}, ${pos.tile_y}) [${pos.layer}]` : '—'}</p>
      <p><strong>Script</strong> ${escapeHtml(bot.script_name || '—')}</p>
      <p><strong>Status</strong> ${escapeHtml(bot.status)}</p>
      <p><strong>XP/hr</strong> ${formatXp(bot.xp_per_hour || 0)}</p>
      <p><strong>Items</strong> ${bot.items_collected ?? 0}</p>
      <p><strong>Profit</strong> ${formatProfit((bot as Bot).profit ?? 0)} gp</p>
      <p><strong>Skills</strong> —</p>
      <p><strong>Inventory</strong> —</p>
      <button type="button" class="btn btn-ghost btn-sm popup-close">Close</button>
    </div>
  `
  popup.querySelector('.popup-close')?.addEventListener('click', () => popup.remove())
  parent.appendChild(popup)
}

function formatXp(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(Math.round(n))
}

function formatProfit(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

// --- Analytics view ---
function renderAnalyticsView() {
  const root = document.querySelector<HTMLDivElement>('#app')!
  root.innerHTML = ''
  const el = document.createElement('div')
  el.className = 'analytics-page'
  renderNav(el)

  let summary: AnalyticsSummary = {
    total_xp_per_hour: 0,
    total_items_collected: 0,
    total_profit: 0,
    by_script: {},
  }
  api<AnalyticsSummary>('/analytics/summary').then((s) => { summary = s; renderAnalyticsContent(el, summary) }).catch(() => {})

  const header = document.createElement('header')
  header.className = 'analytics-header'
  header.innerHTML = '<h1>Analytics</h1>'
  el.appendChild(header)

  const content = document.createElement('main')
  content.className = 'analytics-content'
  content.id = 'analytics-content'
  el.appendChild(content)
  renderAnalyticsContent(el, summary)
  root.appendChild(el)
}

function renderAnalyticsContent(container: HTMLElement, summary: AnalyticsSummary) {
  const content = container.querySelector('#analytics-content')
  if (!content) return
  content.innerHTML = ''
  const cards = document.createElement('div')
  cards.className = 'analytics-cards'
  cards.innerHTML = `
    <div class="card"><span class="card-value">${formatXp(summary.total_xp_per_hour)}</span><span class="card-label">Total XP/hr</span></div>
    <div class="card"><span class="card-value">${summary.total_items_collected}</span><span class="card-label">Items collected</span></div>
    <div class="card"><span class="card-value">${formatProfit(summary.total_profit)}</span><span class="card-label">Profit (gp)</span></div>
  `
  content.appendChild(cards)

  const perBot = document.createElement('section')
  perBot.className = 'analytics-section'
  perBot.innerHTML = '<h2>Per bot</h2>'
  const botTable = document.createElement('table')
  botTable.className = 'analytics-table'
  botTable.innerHTML = `
    <thead><tr>
      <th>Bot</th><th>Script</th><th>Status</th><th>Runtime</th>
      <th>XP/hr</th><th>Total XP</th><th>Items</th><th>Profit</th>
    </tr></thead>
    <tbody></tbody>
  `
  const tbody = botTable.querySelector('tbody')!
  bots.forEach((b) => {
    const tr = document.createElement('tr')
    tr.innerHTML = `
      <td>${escapeHtml(b.bot_id)}</td>
      <td>${escapeHtml(b.script_name || '—')}</td>
      <td><span style="color:${statusColor(b.status)}">${escapeHtml(b.status)}</span></td>
      <td>${escapeHtml(b.runtime_formatted)}</td>
      <td>${formatXp(b.xp_per_hour || 0)}</td>
      <td>${(b as Bot).total_xp_gained ?? 0}</td>
      <td>${b.items_collected ?? 0}</td>
      <td>${formatProfit((b as Bot).profit ?? 0)}</td>
    `
    tbody.appendChild(tr)
  })
  perBot.appendChild(botTable)
  content.appendChild(perBot)

  const perScript = document.createElement('section')
  perScript.className = 'analytics-section'
  perScript.innerHTML = '<h2>Per script</h2>'
  const scriptTable = document.createElement('table')
  scriptTable.className = 'analytics-table'
  scriptTable.innerHTML = `
    <thead><tr>
      <th>Script</th><th>Bots</th><th>XP/hr</th><th>Items</th><th>Profit</th>
    </tr></thead>
    <tbody></tbody>
  `
  const stbody = scriptTable.querySelector('tbody')!
  Object.entries(summary.by_script).forEach(([name, data]) => {
    const tr = document.createElement('tr')
    tr.innerHTML = `
      <td>${escapeHtml(name)}</td>
      <td>${data.count}</td>
      <td>${formatXp(data.xp_per_hour)}</td>
      <td>${data.items_collected}</td>
      <td>${formatProfit(data.profit)}</td>
    `
    stbody.appendChild(tr)
  })
  perScript.appendChild(scriptTable)
  content.appendChild(perScript)
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
    return
  }

  function renderCurrent() {
    const route = getRoute()
    if (mapPollTimer != null) {
      clearInterval(mapPollTimer)
      mapPollTimer = null
    }
    if (route === 'dashboard') {
      render()
    } else if (route === 'map') {
      loadPositions().then(() => renderMapView())
      mapPollTimer = window.setInterval(async () => {
        await loadBots()
        await loadPositions()
        if (getRoute() === 'map') renderMapView()
      }, 8000) as unknown as number
    } else if (route === 'analytics') {
      renderAnalyticsView()
      mapPollTimer = window.setInterval(async () => {
        await loadBots()
        if (getRoute() === 'analytics') {
          const summary = await api<AnalyticsSummary>('/analytics/summary').catch(() => ({
            total_xp_per_hour: 0, total_items_collected: 0, total_profit: 0, by_script: {}
          }))
          const container = document.querySelector<HTMLElement>('.analytics-page')
          if (container) renderAnalyticsContent(container, summary)
        }
      }, 8000) as unknown as number
    }
  }

  window.addEventListener('hashchange', renderCurrent)
  renderCurrent()
}

init()
setInterval(() => { if (getRoute() === 'dashboard') loadBots(); }, 15000)
