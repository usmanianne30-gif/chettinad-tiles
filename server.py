"""
server.py – Chettinad Tiles WebSocket Game Server
Deploy this to Render / Railway / any cloud platform.

Protocol (JSON messages over WebSocket):
  C→S: { "type": "create_lobby", "name": "Alice" }
  C→S: { "type": "join_lobby",   "name": "Bob",   "code": "ABC123" }
  C→S: { "type": "start_game" }          # host only
  C→S: { "type": "place_tiles",  "placements": [...], "storage": [...] }
  C→S: { "type": "ready_next_round" }    # after score screen
  C→S: { "type": "ping" }

  S→C: { "type": "lobby_created",  "code": "ABC123", "player_id": 0 }
  S→C: { "type": "lobby_joined",   "player_id": 1, "players": [...] }
  S→C: { "type": "lobby_update",   "players": [...] }
  S→C: { "type": "error",          "msg": "..." }
  S→C: { "type": "game_started",   "state": {...} }
  S→C: { "type": "round_started",  "state": {...} }
  S→C: { "type": "round_scores",   "scores": {...} }
  S→C: { "type": "game_over",      "final": {...} }
  S→C: { "type": "pong" }
"""
from __future__ import annotations
import asyncio
import json
import random
import string
import logging
import os
import http
from typing import Optional

import websockets
from websockets.server import ServerConnection

from game_logic import (
    Tile, Goal, make_supply, make_goals,
    floor_to_list, floor_from_list, supply_to_list, supply_from_list,
    full_score, MOTIFS, CENTRES
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("server")

MAX_PLAYERS  = 6
TOTAL_ROUNDS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────
class PlayerState:
    def __init__(self, pid: int, name: str, ws: ServerConnection):
        self.pid       = pid
        self.name      = name
        self.ws        = ws
        self.floor     = [[None]*4 for _ in range(4)]
        self.inventory: list[Tile] = []
        self.storage:   list[Tile] = []
        self.storage_cap = 4
        self.total_score = 0
        self.score_history: list[dict] = []
        self.goal_counts  = [0, 0, 0]
        self.ready_next   = False   # ready for next round
        self.placements_done = False

    def to_public_dict(self):
        return {
            "pid":          self.pid,
            "name":         self.name,
            "floor":        floor_to_list(self.floor),
            "total_score":  self.total_score,
            "storage_cap":  self.storage_cap,
            "storage_count": len(self.storage),
        }

    def inventory_for_self(self):
        return [t.to_dict() for t in self.inventory]


class Lobby:
    def __init__(self, code: str):
        self.code     = code
        self.players: list[PlayerState] = []
        self.host_pid = 0
        self.started  = False
        self.round    = 0
        self.supply:  list[Tile] = []
        self.goals:   list[Goal] = []

    def add_player(self, name: str, ws: ServerConnection) -> PlayerState:
        pid = len(self.players)
        p   = PlayerState(pid, name, ws)
        self.players.append(p)
        return p

    def get_player_by_ws(self, ws) -> Optional[PlayerState]:
        for p in self.players:
            if p.ws is ws:
                return p
        return None

    def all_placements_done(self) -> bool:
        return all(p.placements_done for p in self.players)

    def all_ready_next(self) -> bool:
        return all(p.ready_next for p in self.players)

    def public_players(self):
        return [p.to_public_dict() for p in self.players]


# ─────────────────────────────────────────────────────────────────────────────
# Global state
# ─────────────────────────────────────────────────────────────────────────────
lobbies: dict[str, Lobby] = {}
ws_to_lobby: dict[ServerConnection, Lobby] = {}


def gen_code() -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in lobbies:
            return code


async def send(ws, data: dict):
    try:
        await ws.send(json.dumps(data))
    except Exception:
        pass


async def broadcast(lobby: Lobby, data: dict, exclude=None):
    for p in lobby.players:
        if p.ws is not exclude:
            await send(p.ws, data)


# ─────────────────────────────────────────────────────────────────────────────
# Round logic
# ─────────────────────────────────────────────────────────────────────────────
async def start_round(lobby: Lobby):
    lobby.round += 1
    log.info(f"Lobby {lobby.code}: starting round {lobby.round}")

    # Reset flags
    for p in lobby.players:
        p.placements_done = False
        p.ready_next      = False

    # Pick 4 tiles from supply for each player
    for p in lobby.players:
        for _ in range(4):
            if lobby.supply:
                p.inventory.append(lobby.supply.pop())

    # ── Tile passing: 3 → 2 → 1 (simultaneously, circular left) ────────────
    for n in (3, 2, 1):
        batches = []
        for p in lobby.players:
            # pass the first n tiles from inventory
            batch = p.inventory[:n]
            p.inventory = p.inventory[n:]
            batches.append(batch)
        # each player receives from the right (i receives batch[i+1 % N])
        np = len(lobby.players)
        for i, p in enumerate(lobby.players):
            p.inventory.extend(batches[(i + 1) % np])

    # Send each player their personal state
    goals_data = [g.to_dict() for g in lobby.goals]
    public     = lobby.public_players()
    for p in lobby.players:
        await send(p.ws, {
            "type":      "round_started",
            "round":     lobby.round,
            "goals":     goals_data,
            "inventory": p.inventory_for_self(),
            "storage":   [t.to_dict() for t in p.storage],
            "storage_cap": p.storage_cap,
            "players":   public,
        })


async def finish_round(lobby: Lobby):
    """Score all players and send results."""
    is_last = (lobby.round == TOTAL_ROUNDS)

    round_results = {}
    for p in lobby.players:
        a, b, c, d, e, total, nc = full_score(
            p.floor, lobby.goals, p.goal_counts, is_last
        )
        p.goal_counts  = nc
        p.total_score += total
        record = {"a": a, "b": b, "c": c, "d": d, "e": e, "total": total, "cumulative": p.total_score}
        p.score_history.append(record)
        round_results[p.pid] = record

        # Discard one storage slot
        p.storage_cap = max(0, p.storage_cap - 1)
        if len(p.storage) > p.storage_cap:
            p.storage = p.storage[:p.storage_cap]

    public = lobby.public_players()

    if is_last:
        # Game over
        winner = max(lobby.players, key=lambda p: p.total_score)
        await broadcast(lobby, {
            "type":          "game_over",
            "round_results": round_results,
            "players":       public,
            "winner_pid":    winner.pid,
            "winner_name":   winner.name,
        })
    else:
        await broadcast(lobby, {
            "type":          "round_scores",
            "round":         lobby.round,
            "round_results": round_results,
            "players":       public,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Message handlers
# ─────────────────────────────────────────────────────────────────────────────
async def handle_create_lobby(ws, msg: dict):
    name = str(msg.get("name", "Player"))[:20]
    code = gen_code()
    lobby = Lobby(code)
    lobbies[code] = lobby
    ws_to_lobby[ws] = lobby
    p = lobby.add_player(name, ws)
    log.info(f"Lobby {code} created by {name}")
    await send(ws, {"type": "lobby_created", "code": code, "player_id": p.pid, "name": name})


async def handle_join_lobby(ws, msg: dict):
    code = str(msg.get("code", "")).upper()
    name = str(msg.get("name", "Player"))[:20]

    if code not in lobbies:
        await send(ws, {"type": "error", "msg": "Lobby not found."})
        return
    lobby = lobbies[code]
    if lobby.started:
        await send(ws, {"type": "error", "msg": "Game already started."})
        return
    if len(lobby.players) >= MAX_PLAYERS:
        await send(ws, {"type": "error", "msg": f"Lobby is full (max {MAX_PLAYERS})."})
        return

    ws_to_lobby[ws] = lobby
    p = lobby.add_player(name, ws)
    log.info(f"Player {name} (pid={p.pid}) joined lobby {code}")

    await send(ws, {
        "type": "lobby_joined", "code": code,
        "player_id": p.pid, "name": name,
        "players": lobby.public_players()
    })
    await broadcast(lobby, {
        "type": "lobby_update",
        "players": lobby.public_players()
    }, exclude=ws)


async def handle_start_game(ws, lobby: Lobby, player: PlayerState):
    if player.pid != lobby.host_pid:
        await send(ws, {"type": "error", "msg": "Only the host can start the game."})
        return
    if len(lobby.players) < 2:
        await send(ws, {"type": "error", "msg": "Need at least 2 players."})
        return
    if lobby.started:
        return

    lobby.started = True
    lobby.supply  = make_supply()
    lobby.goals   = make_goals()
    log.info(f"Lobby {lobby.code}: game started with {len(lobby.players)} players")

    await broadcast(lobby, {
        "type":    "game_started",
        "players": lobby.public_players(),
        "goals":   [g.to_dict() for g in lobby.goals],
    })
    await start_round(lobby)


async def handle_place_tiles(ws, lobby: Lobby, player: PlayerState, msg: dict):
    """Player submits their tile placements and storage decisions."""
    if player.placements_done:
        return

    placements = msg.get("placements", [])   # list of {tid, row, col}
    store_tids = msg.get("store_tids", [])   # list of tids to put in storage

    # Build tid → Tile map from inventory
    inv_map = {t.tid: t for t in player.inventory}
    # Also include storage tiles (they stay unless explicitly moved)

    # Apply placements
    for pm in placements:
        tid = pm["tid"]; r = pm["row"]; c = pm["col"]
        if tid in inv_map and player.floor[r][c] is None:
            player.floor[r][c] = inv_map.pop(tid)

    # Apply storage
    for tid in store_tids:
        if tid in inv_map and len(player.storage) < player.storage_cap:
            player.storage.append(inv_map.pop(tid))

    # Force remaining inventory onto floor
    for tile in list(inv_map.values()):
        placed = False
        for r in range(4):
            for c in range(4):
                if player.floor[r][c] is None and not placed:
                    player.floor[r][c] = tile
                    placed = True
        if not placed and len(player.storage) < player.storage_cap:
            player.storage.append(tile)

    player.inventory  = []
    player.placements_done = True

    # Broadcast updated public state
    await broadcast(lobby, {
        "type":    "player_placed",
        "pid":     player.pid,
        "players": lobby.public_players(),
    })

    # Check if all players done
    if lobby.all_placements_done():
        await finish_round(lobby)


async def handle_ready_next(ws, lobby: Lobby, player: PlayerState):
    player.ready_next = True
    if lobby.all_ready_next() and lobby.round < TOTAL_ROUNDS:
        await start_round(lobby)


# ─────────────────────────────────────────────────────────────────────────────
# Connection handler
# ─────────────────────────────────────────────────────────────────────────────
async def handler(ws: ServerConnection):
    log.info(f"New connection: {ws.remote_address}")
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype  = msg.get("type")
            lobby  = ws_to_lobby.get(ws)
            player = lobby.get_player_by_ws(ws) if lobby else None

            if mtype == "ping":
                await send(ws, {"type": "pong"})

            elif mtype == "create_lobby":
                await handle_create_lobby(ws, msg)

            elif mtype == "join_lobby":
                await handle_join_lobby(ws, msg)

            elif mtype == "start_game" and lobby and player:
                await handle_start_game(ws, lobby, player)

            elif mtype == "place_tiles" and lobby and player:
                await handle_place_tiles(ws, lobby, player, msg)

            elif mtype == "ready_next_round" and lobby and player:
                await handle_ready_next(ws, lobby, player)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        log.info(f"Disconnected: {ws.remote_address}")
        if ws in ws_to_lobby:
            lobby = ws_to_lobby.pop(ws)
            # Notify others
            if lobby:
                await broadcast(lobby, {
                    "type":    "lobby_update",
                    "players": [p.to_public_dict() for p in lobby.players if p.ws is not ws],
                    "msg":     "A player disconnected."
                })


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
async def health_check(connection, request):
    if request.headers.get("Upgrade", "").lower() != "websocket":
        return connection.respond(http.HTTPStatus.OK, "Chettinad Tiles WebSocket Server is Online!\n")
    return None


async def main():
    port = int(os.environ.get("PORT", 8765))
    host = "0.0.0.0"
    log.info(f"Starting Chettinad Tiles server on {host}:{port}")
    async with websockets.serve(handler, host, port, process_request=health_check):
        await asyncio.get_event_loop().create_future()   # run forever


if __name__ == "__main__":
    asyncio.run(main())
