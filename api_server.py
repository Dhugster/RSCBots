"""
IdleRSC Manager – HTTP API for the web dashboard.
Run: uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
"""
import zipfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Ensure we run from project root so config paths resolve
ROOT = Path(__file__).resolve().parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import datetime

from core.controller import BotController
from core.bot_instance import BotStatus

app = FastAPI(title="IdleRSC Manager API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_controller: BotController | None = None

# In-memory position store for map markers: bot_id -> { tile_x, tile_y, layer }
_position_store: dict[str, dict] = {}

# Debug session log (workspace path for Cursor debug mode)
_DEBUG_LOG_PATH = Path(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log")


def _write_debug_log(payload: dict) -> None:
    try:
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            import json
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def get_controller() -> BotController:
    global _controller
    if _controller is None:
        _controller = BotController(str(ROOT / "config" / "bots.yaml"))
        # Register position listener so log-parsed or client-reported positions update the map store
        def _on_position(bot_id: str, tile_x: int, tile_y: int, layer: str) -> None:
            _position_store[bot_id] = {"tile_x": tile_x, "tile_y": tile_y, "layer": layer}
        _controller.add_position_listener(_on_position)
    return _controller


def _sync_process_exits(c: BotController) -> None:
    """If any bot process has exited (closed/crashed), set status to CRASHED and clear from position store."""
    for bot_id, bot in list(c.bots.items()):
        if bot.process is not None and bot.process.poll() is not None:
            # #region agent log
            _write_debug_log({"location": "api_server:_sync_process_exits", "message": "process exited, marking crashed and clearing position", "data": {"bot_id": bot_id}, "hypothesisId": "H2", "timestamp": __import__("time").time() * 1000})
            # #endregion
            bot.stop_time = datetime.now()
            bot.status = BotStatus.CRASHED
            bot.process = None
            _position_store.pop(bot_id, None)


# --- Pydantic models (no password in responses) ---

class BotSummary(BaseModel):
    bot_id: str
    account_name: str
    username: str
    script_name: str
    script_args: list[str]
    status: str
    runtime_formatted: str
    xp_per_hour: float
    items_collected: int
    total_xp_gained: int = 0
    profit: int = 0


class BotCreate(BaseModel):
    bot_id: str
    account_name: str
    username: str
    password: str
    script_name: str = ""  # optional; pick from dropdown
    script_args: list[str] = []  # optional


class BotUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    script_name: str | None = None
    script_args: list[str] | None = None


class Preset(BaseModel):
    name: str
    script: str
    args: list[str]


def _bot_to_summary(bot) -> BotSummary:
    return BotSummary(
        bot_id=bot.bot_id,
        account_name=bot.account_name,
        username=bot.username,
        script_name=bot.script_name or "",
        script_args=bot.script_args or [],
        status=bot.status.value,
        runtime_formatted=bot.runtime_formatted,
        xp_per_hour=bot.metrics.xp_per_hour,
        items_collected=bot.metrics.items_collected,
        total_xp_gained=bot.metrics.total_xp_gained,
        profit=getattr(bot.metrics, "profit", 0),
    )


@app.get("/api/bots")
def list_bots():
    c = get_controller()
    _sync_process_exits(c)  # update status to crashed/stopped when process has exited
    for b in c.bots.values():
        if getattr(b, "update_runtime", None):
            b.update_runtime()  # refresh runtime and xp_per_hour for dashboard
    return [_bot_to_summary(b) for b in c.bots.values()]


@app.post("/api/bots")
def add_bot(body: BotCreate):
    c = get_controller()
    if body.bot_id in c.bots:
        raise HTTPException(status_code=400, detail="Bot ID already exists")
    config = {
        "id": body.bot_id,
        "account": body.account_name,
        "username": body.username,
        "password": body.password,
        "script": body.script_name,
        "args": body.script_args,
    }
    c.add_bot(config)
    c.save_bots_to_config()
    return _bot_to_summary(c.get_bot(body.bot_id))


@app.put("/api/bots/{bot_id}")
def update_bot(bot_id: str, body: BotUpdate):
    c = get_controller()
    bot = c.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if body.username is not None:
        bot.username = body.username
        bot.account_name = body.username
    if body.password is not None:
        bot.password = body.password
    if body.script_name is not None:
        bot.script_name = body.script_name
    if body.script_args is not None:
        bot.script_args = body.script_args
    c.save_bots_to_config()
    return _bot_to_summary(bot)


@app.delete("/api/bots/{bot_id}")
def delete_bot(bot_id: str):
    c = get_controller()
    if not c.remove_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot not found")
    c.save_bots_to_config()
    return {"ok": True}


@app.post("/api/bots/{bot_id}/start")
def start_bot(bot_id: str):
    c = get_controller()
    bot = c.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    try:
        ok = c.start_bot(bot_id)
        return {"ok": ok, "bot": _bot_to_summary(c.get_bot(bot_id))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bots/{bot_id}/stop")
def stop_bot(bot_id: str):
    c = get_controller()
    bot = c.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    try:
        c.stop_bot(bot_id)
        return {"ok": True, "bot": _bot_to_summary(c.get_bot(bot_id))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/debug-log")
def debug_log(payload: dict):
    """Append one NDJSON line to the session debug log (Cursor debug mode)."""
    _write_debug_log(payload)
    return {"ok": True}


@app.get("/api/bots/positions")
def get_bot_positions():
    """Return bot positions for map markers; only running bots. Stale entries cleared when process has exited."""
    # #region agent log
    _write_debug_log({"location": "api_server:get_bot_positions.entry", "message": "positions requested", "data": {"store_keys": list(_position_store.keys()), "store_count": len(_position_store)}, "hypothesisId": "H1", "timestamp": __import__("time").time() * 1000})
    # #endregion
    c = get_controller()
    _sync_process_exits(c)
    # Return only positions for bots that are currently running; remove stale entries from store
    running_ids = {bid for bid, b in c.bots.items() if b.is_running}
    for bid in list(_position_store):
        if bid not in running_ids:
            _position_store.pop(bid, None)
    out = {bid: _position_store[bid] for bid in _position_store if bid in running_ids}
    # Fallback: running bots with no position (no POST and no log parse) get a default so they appear on the map
    _DEFAULT_MAP_CENTER = (1200, 1200)  # surface, RSC map 2448x2736
    _MAP_W, _MAP_H = 2448, 2736
    for bid in running_ids:
        if bid not in out:
            h = sum(ord(c) for c in bid) % 400
            x = _DEFAULT_MAP_CENTER[0] + (h % 201) - 100
            y = _DEFAULT_MAP_CENTER[1] + ((h * 7) % 201) - 100
            # Clamp to map pixel bounds.
            x = max(0, min(_MAP_W - 1, x))
            y = max(0, min(_MAP_H - 1, y))
            out[bid] = {
                "tile_x": x,
                "tile_y": y,
                "layer": "surface",
            }
    # #region agent log
    _write_debug_log({"location": "api_server:get_bot_positions.return", "message": "positions response", "data": {"running_ids": list(running_ids), "returned_keys": list(out.keys()), "returned_count": len(out)}, "hypothesisId": "H1_H2", "timestamp": __import__("time").time() * 1000})
    # #endregion
    return out


# rsc-world-map uses 2448x2736; game coords use TILE_SIZE=3 and X flip (see entity-canvas)
from core.map_coords import MAP_W as _MAP_W, MAP_H as _MAP_H, game_tile_to_map_pixel


class PositionUpdate(BaseModel):
    tile_x: int | None = None
    tile_y: int | None = None
    # Map pixel coordinates for rsc-world-map overlay (X: 0..2448, Y: 0..2736).
    # If coordinate_system is "game_tile", tile_x/tile_y are game coords (e.g. client "Coords: 161 607") and are converted to map pixels.
    layer: str | None = None  # surface | floor1 | floor2 | dungeon
    coordinate_system: str | None = None  # "map_pixel" (default) | "game_tile"


@app.post("/api/bots/{bot_id}/position")
def update_bot_position(bot_id: str, body: PositionUpdate):
    """Update position for a bot.

    Coordinate contract:
    - tile_x, tile_y: either map pixels (0..2448, 0..2736) or game tiles if coordinate_system="game_tile"
    - layer: surface | floor1 | floor2 | dungeon
    - coordinate_system: "map_pixel" (default) or "game_tile" (client coords like "161 607" -> converted to map pixels)
    """
    # #region agent log
    _write_debug_log({"location": "api_server:update_bot_position", "message": "POST position", "data": {"bot_id": bot_id, "tile_x": body.tile_x, "tile_y": body.tile_y, "layer": body.layer}, "hypothesisId": "H4", "timestamp": __import__("time").time() * 1000})
    # #endregion
    c = get_controller()
    if c.get_bot(bot_id) is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    entry = _position_store.get(bot_id) or {}
    layer = (body.layer or "surface") or entry.get("layer", "surface")

    tile_x, tile_y = body.tile_x, body.tile_y
    if tile_x is not None and tile_y is not None and (body.coordinate_system or "").strip().lower() == "game_tile":
        tile_x, tile_y = game_tile_to_map_pixel(tile_x, tile_y, layer)

    if tile_x is not None:
        entry["tile_x"] = max(0, min(_MAP_W - 1, tile_x))
    if tile_y is not None:
        entry["tile_y"] = max(0, min(_MAP_H - 1, tile_y))
    if body.layer is not None:
        entry["layer"] = body.layer
    _position_store[bot_id] = entry
    return {"ok": True, "position": entry}


@app.post("/api/stop-all")
def stop_all_bots():
    """Stop all bot processes. Restart the server after this to pick up code changes."""
    c = get_controller()
    n = c.stop_all()
    return {"ok": True, "stopped": n}


@app.get("/api/logs")
def get_logs(bot_id: str | None = None, tail: int = 100):
    c = get_controller()
    lines = c.log_aggregator.get_aggregated_logs({"tail": tail})
    if bot_id:
        lines = [l for l in lines if l.startswith(f"[{bot_id}]")]
    return {"lines": lines[-tail:]}


@app.get("/api/presets")
def get_presets():
    c = get_controller()
    return [Preset(name=p["name"], script=p["script"], args=p["args"]) for p in c.get_task_presets()]


def _discover_scripts_from_jar() -> list[str] | None:
    """Discover script class names from the IdleRSC JAR (same list as in-game). Returns None if JAR missing or not a zip."""
    try:
        c = get_controller()
        jar_path = Path(c.settings.get("idlersc_jar_path", ""))
        if not jar_path:
            return None
        if not jar_path.is_absolute():
            jar_path = ROOT / jar_path
        jar_path = jar_path.resolve()
        if not jar_path.exists() or not jar_path.is_file():
            return None
        seen: set[str] = set()
        with zipfile.ZipFile(jar_path, "r") as z:
            for name in z.namelist():
                if not name.endswith(".class"):
                    continue
                if "$" in name:
                    continue
                name_lower = name.replace("\\", "/").lower()
                if "scripting" not in name_lower and "script" not in name_lower:
                    continue
                base = Path(name).stem
                if base and base not in ("Script", "IScript", "package"):
                    seen.add(base)
        if not seen:
            return None
        out = [""] + sorted(seen)
        return out
    except Exception:
        return None


def _load_scripts_from_config() -> list[str]:
    """Load script names from config/scripts.yaml (fallback)."""
    path = ROOT / "config" / "scripts.yaml"
    if not path.exists():
        return []
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return list(data.get("scripts", []))
    except Exception:
        return []


def _load_scripts_list() -> list[str]:
    """Script names for dropdown: discover from IdleRSC JAR, else config/scripts.yaml, else default."""
    from_jar = _discover_scripts_from_jar()
    if from_jar:
        return from_jar
    from_config = _load_scripts_from_config()
    if from_config:
        return from_config if from_config[0] == "" else [""] + from_config
    return ["", "FishingBot", "MiningBot", "CombatBot", "HarvestBot"]


@app.get("/api/scripts")
def get_scripts():
    """List of IdleRSC script names for dropdown (from JAR discovery, then config, then default)."""
    return {"scripts": _load_scripts_list()}


class ApplyPresetBody(BaseModel):
    bot_ids: list[str]
    preset_name: str


@app.post("/api/bots/apply-preset")
def apply_preset(body: ApplyPresetBody):
    c = get_controller()
    presets = {p["name"]: p for p in c.get_task_presets()}
    if body.preset_name not in presets:
        raise HTTPException(status_code=400, detail="Preset not found")
    p = presets[body.preset_name]
    updated = []
    for bid in body.bot_ids:
        bot = c.get_bot(bid)
        if bot:
            bot.script_name = p["script"]
            bot.script_args = list(p.get("args", []))
            updated.append(_bot_to_summary(bot))
    c.save_bots_to_config()
    return {"updated": updated}


@app.get("/api/analytics/summary")
def get_analytics_summary():
    """Aggregates: total XP/hr, items, profit; per-script breakdown."""
    c = get_controller()
    total_xp_per_hour = 0.0
    total_items = 0
    total_profit = 0
    by_script: dict[str, dict] = {}
    for bot in c.bots.values():
        xp = bot.metrics.xp_per_hour
        items = bot.metrics.items_collected
        profit = getattr(bot.metrics, "profit", 0)
        total_xp_per_hour += xp
        total_items += items
        total_profit += profit
        name = bot.script_name or "(none)"
        if name not in by_script:
            by_script[name] = {"bot_ids": [], "count": 0, "xp_per_hour": 0.0, "items_collected": 0, "profit": 0}
        by_script[name]["bot_ids"].append(bot.bot_id)
        by_script[name]["count"] += 1
        by_script[name]["xp_per_hour"] += xp
        by_script[name]["items_collected"] += items
        by_script[name]["profit"] += profit
    return {
        "total_xp_per_hour": total_xp_per_hour,
        "total_items_collected": total_items,
        "total_profit": total_profit,
        "by_script": by_script,
    }


# Serve built frontend when present (standalone)
_dist = ROOT / "web" / "dist"
if _dist.exists():
    _maps_dir = _dist / "maps"
    if _maps_dir.exists():
        _MAP_MEDIA_TYPES = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}

        @app.get("/maps/{filename:path}")
        def serve_map_file(filename: str):
            path = (_maps_dir / filename).resolve()
            base = _maps_dir.resolve()
            if not path.is_file() or not str(path).startswith(str(base)):
                raise HTTPException(status_code=404, detail="Not found")
            suffix = path.suffix.lower()
            media_type = _MAP_MEDIA_TYPES.get(suffix, "application/octet-stream")
            return FileResponse(path, media_type=media_type)
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="app")
