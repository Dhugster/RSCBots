"""Shared coordinate conversion utilities for RSC map overlay."""

# rsc-world-map uses 2448x2736; game coords use TILE_SIZE=3 and X flip (see entity-canvas)
MAP_W, MAP_H = 2448, 2736
TILE_SIZE = 3


def game_tile_to_map_pixel(gx: int, gy: int, layer: str) -> tuple[int, int]:
    """Convert game tile coords (e.g. client 'Coords: 161 607') to map pixel for rsc-world-map overlay.
    
    Args:
        gx: Game tile X coordinate (e.g. 161)
        gy: Game tile Y coordinate (e.g. 607)
        layer: One of 'surface', 'floor1', 'floor2', 'dungeon'
    
    Returns:
        Tuple of (map_pixel_x, map_pixel_y) in range 0..2448, 0..2736
    """
    plane = {"surface": 0, "floor1": 1, "floor2": 2, "dungeon": 3}.get(layer, 0)
    # Same formula as @2003scape/rsc-world-map src/entity-canvas.js (addObjects):
    # x = imageWidth - (gx*TILE_SIZE) - 2; y = gy*TILE_SIZE - 1; then for plane>0 subtract plane offset
    px = MAP_W - (gx * TILE_SIZE) - 2
    py = gy * TILE_SIZE - 1
    if plane != 0:
        sector_size, min_ry, max_ry = 48, 37, 55
        py -= plane * sector_size * TILE_SIZE * (max_ry - min_ry) + plane * 240
    px = max(0, min(MAP_W - 1, px))
    py = max(0, min(MAP_H - 1, py))
    return px, py
