/**
 * Build map-manifest.json from RuneScape Classic Wiki MediaWiki API.
 * Run from repo root: node scripts/build-map-manifest.js
 * Writes to web/public/map-manifest.json.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const WIKI_API = 'https://classic.runescape.wiki/api.php';
const USER_AGENT = 'RSC-Map-App/1.0 (IdleRSC Manager; wiki map integration)';

const CATEGORIES = [
  'Category:Maps',
  'Category:Dungeon_maps',
  'Category:WorldMaps'
];

async function fetchJson(url, params = {}) {
  const u = new URL(url);
  Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
  const res = await fetch(u.toString(), {
    headers: { 'User-Agent': USER_AGENT }
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
  return res.json();
}

async function fetchCategoryMembers(cmtitle) {
  const all = [];
  let continueKey = null;
  do {
    const params = {
      action: 'query',
      list: 'categorymembers',
      cmtitle,
      cmtype: 'file',
      cmlimit: 'max',
      format: 'json'
    };
    if (continueKey) params.cmcontinue = continueKey;
    const data = await fetchJson(WIKI_API, params);
    const members = data.query?.categorymembers ?? [];
    all.push(...members);
    continueKey = data.continue?.cmcontinue ?? null;
  } while (continueKey);
  return all;
}

async function fetchImageInfo(titles) {
  if (titles.length === 0) return {};
  const titleList = titles.join('|');
  const data = await fetchJson(WIKI_API, {
    action: 'query',
    titles: titleList,
    prop: 'imageinfo',
    iiprop: 'url|size',
    format: 'json'
  });
  const pages = data.query?.pages ?? {};
  const out = {};
  for (const [pageid, page] of Object.entries(pages)) {
    const title = page.title;
    const info = page.imageinfo?.[0];
    if (title && info) {
      out[title] = { url: info.url, width: info.width, height: info.height };
    }
  }
  return out;
}

function inferType(fileTitle, inDungeonCategory, inWorldMapsCategory) {
  if (inWorldMapsCategory) return 'world';
  if (inDungeonCategory) return 'dungeons';
  const name = fileTitle.replace(/^File:/i, '').toLowerCase();
  if (name.includes('mine') || name.includes('mining')) return 'mines';
  if (name.includes('manor') || name.includes('palace') || name.includes('mansion') ||
      name.includes('guild') || name.includes('tower') || name.includes('hideout') ||
      name.includes('grand tree') || name.includes("melzar") || (name.includes('maze') && name.includes('map')) ||
      name.includes('keep ') || (name.includes('stronghold') && !name.includes('mine')) ||
      name.includes('basement') || name.includes('first floor') || name.includes('ground floor') ||
      name.includes('second floor') || name.includes('entrance map') || name.includes('entrances map'))
    return 'buildings';
  return 'regions';
}

function parentAndLabel(fileTitle) {
  const name = fileTitle.replace(/^File:/i, '').replace(/\.(png|gif|jpg|jpeg)$/i, '');
  const normalized = name.replace(/_/g, ' ');
  const mapNum = normalized.match(/\bmap\s*(\d+)\b/i);
  const mapWord = normalized.match(/\b(map\s+\d+|basement|ground floor|first floor|second floor|pit|platforms|entrance|entrances)\b/i);
  let parent = normalized;
  let subLabel = null;
  if (mapNum) {
    parent = normalized.replace(/\s+map\s*\d+.*$/i, '').trim();
    subLabel = `Map ${mapNum[1]}`;
  } else if (mapWord) {
    const m = mapWord[0];
    parent = normalized.replace(new RegExp('\\s*' + m.replace(/\s/g, '\\s') + '.*$', 'i'), '').trim();
    subLabel = m.charAt(0).toUpperCase() + m.slice(1).toLowerCase();
  }
  parent = parent.replace(/\s+map\s*$/i, '').trim();
  return { parent: parent || normalized, subLabel: subLabel || null };
}

function slugify(s) {
  return s.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase();
}

async function main() {
  console.log('Fetching category members...');
  const [mapsMembers, dungeonMembers, worldMembers] = await Promise.all(
    CATEGORIES.map(cat => fetchCategoryMembers(cat))
  );
  const inDungeon = new Set(dungeonMembers.map(m => m.title));
  const inWorld = new Set(worldMembers.map(m => m.title));

  const allTitles = [...new Set([
    ...mapsMembers.map(m => m.title),
    ...dungeonMembers.map(m => m.title),
    ...worldMembers.map(m => m.title)
  ])];
  allTitles.sort((a, b) => {
    const aD = inDungeon.has(a) ? 1 : 0, bD = inDungeon.has(b) ? 1 : 0;
    if (aD !== bD) return bD - aD;
    const aW = inWorld.has(a) ? 1 : 0, bW = inWorld.has(b) ? 1 : 0;
    return bW - aW;
  });
  console.log(`Total unique files: ${allTitles.length}`);

  const BATCH = 50;
  const imageInfoMap = {};
  for (let i = 0; i < allTitles.length; i += BATCH) {
    const batch = allTitles.slice(i, i + BATCH);
    const info = await fetchImageInfo(batch);
    Object.assign(imageInfoMap, info);
    console.log(`Fetched imageinfo ${Math.min(i + BATCH, allTitles.length)}/${allTitles.length}`);
  }

  const locations = new Map();
  const entries = [];

  for (const fileTitle of allTitles) {
    const info = imageInfoMap[fileTitle];
    if (!info?.url) continue;
    const type = inferType(fileTitle, inDungeon.has(fileTitle), inWorld.has(fileTitle));
    const { parent, subLabel } = parentAndLabel(fileTitle);
    const displayName = parent;
    const filename = fileTitle.startsWith('File:') ? fileTitle.slice(5).replace(/ /g, '_') : fileTitle;
    const locationId = slugify(parent);
    if (!locations.has(locationId)) {
      locations.set(locationId, { id: locationId, displayName, type, maps: [] });
    }
    const mapEntry = {
      fileTitle,
      filename,
      url: info.url,
      width: info.width,
      height: info.height,
      subLabel: subLabel || (locations.get(locationId).maps.length === 0 ? null : 'Map')
    };
    locations.get(locationId).maps.push(mapEntry);
    entries.push({ type, locationId, displayName, ...mapEntry });
  }

  const categories = {
    world: [],
    dungeons: [],
    buildings: [],
    mines: [],
    regions: []
  };
  for (const loc of locations.values()) {
    const item = {
      id: loc.id,
      displayName: loc.displayName,
      type: loc.type,
      mapCount: loc.maps.length,
      maps: loc.maps.map(m => ({
        url: m.url,
        width: m.width,
        height: m.height,
        subLabel: m.subLabel,
        filename: m.filename
      }))
    };
    if (categories[loc.type]) categories[loc.type].push(item);
  }

  const manifest = {
    generated: new Date().toISOString(),
    source: 'https://classic.runescape.wiki',
    categories,
    flatEntries: entries
  };

  const outPath = path.join(__dirname, '..', 'web', 'public', 'map-manifest.json');
  const outDir = path.dirname(outPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(manifest, null, 2), 'utf8');
  console.log(`Wrote ${outPath}`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
