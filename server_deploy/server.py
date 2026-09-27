"""
server_deploy/server.py – standalone server for cloud deployment.
Copy of the main server.py without any local import dependencies.
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("server")

MAX_PLAYERS  = 6
TOTAL_ROUNDS = 4

MOTIFS  = ["Leaf", "Petal", "Arrow", "Swirl"]
CENTRES = ["Star", "Flower", "Butterfly", "Diamond", "Pinwheel"]


# ─────────────────────────────────────────────────────────────────────────────
# Tile / Goal / Scoring  (self-contained, no local imports)
# ─────────────────────────────────────────────────────────────────────────────
class Tile:
    __slots__ = ("motif","centre","tid")
    def __init__(self, motif, centre, tid):
        self.motif = motif; self.centre = centre; self.tid = tid
    def to_dict(self): return {"motif":self.motif,"centre":self.centre,"tid":self.tid}
    @staticmethod
    def from_dict(d):
        return Tile(d["motif"],d["centre"],d["tid"]) if d else None


def make_supply():
    tiles=[]; tid=0
    combos=[(m,c) for m in MOTIFS for c in CENTRES]
    extras=random.sample(combos,10)
    for m,c in combos:
        for _ in range(3): tiles.append(Tile(m,c,tid)); tid+=1
    for m,c in extras: tiles.append(Tile(m,c,tid)); tid+=1
    random.shuffle(tiles); return tiles


class Goal:
    def __init__(self,motifs): self.motifs=motifs
    def to_dict(self): return {"motifs":self.motifs}

    def _valid_shape(self,p0,p1,p2):
        pts=[p0,p1,p2]; rows=[p[0] for p in pts]; cols=[p[1] for p in pts]
        sr=sorted(rows); sc=sorted(cols)
        if len(set(rows))==1:
            if sc==list(range(sc[0],sc[0]+3)): return True
            if set(cols) in ({0,2,3},{0,1,3}): return True
        if len(set(cols))==1:
            if sr==list(range(sr[0],sr[0]+3)): return True
            if set(rows) in ({0,2,3},{0,1,3}): return True
        dr=(rows[1]-rows[0],rows[2]-rows[1]); dc=(cols[1]-cols[0],cols[2]-cols[1])
        if dr[0]==dr[1] and dc[0]==dc[1] and abs(dr[0])==1 and abs(dc[0])==1: return True
        for a,b in [(0,1),(0,2),(1,2)]:
            ci=[x for x in range(3) if x not in (a,b)][0]
            ra,ca=pts[a]; rb,cb=pts[b]; rc,cc=pts[ci]
            if ra==rb and abs(ca-cb)==1 and (rc==ra+1 or rc==ra-1) and cc in (ca,cb): return True
            if ca==cb and abs(ra-rb)==1 and (cc==ca+1 or cc==ca-1) and rc in (ra,rb): return True
        return False

    def check(self,floor_grid):
        pos_for={m:[] for m in set(self.motifs)}
        for r in range(4):
            for c in range(4):
                t=floor_grid[r][c]
                if t and t.motif in pos_for: pos_for[t.motif].append((r,c))
        count=0; seen=[]
        for p0 in pos_for[self.motifs[0]]:
            for p1 in pos_for[self.motifs[1]]:
                if p1==p0: continue
                for p2 in pos_for[self.motifs[2]]:
                    if p2 in (p0,p1): continue
                    fs=frozenset([p0,p1,p2])
                    if fs in seen: continue
                    if self._valid_shape(p0,p1,p2): seen.append(fs); count+=1
        return count


def make_goals():
    goals=[]
    for _ in range(3):
        col=[]; tries=0
        while len(col)<3 and tries<200:
            m=random.choice(MOTIFS)
            if col and col[-1]==m: tries+=1; continue
            col.append(m)
        goals.append(Goal(col))
    return goals


def score_motifs(fg):
    s=0
    for r in range(3):
        for c in range(3):
            q=[fg[r][c],fg[r][c+1],fg[r+1][c],fg[r+1][c+1]]
            if all(q) and len({t.motif for t in q})==1: s+=1
    return s


def score_sequences(fg):
    b=c=0
    lines=[]
    for r in range(4): lines.append([(r,cc) for cc in range(4)])
    for cc in range(4): lines.append([(rr,cc) for rr in range(4)])
    lines+=[ [(i,i) for i in range(4)],[(i,3-i) for i in range(4)] ]
    for line in lines:
        cps=[fg[r][cc].centre if fg[r][cc] else None for r,cc in line]
        for s in range(len(cps)):
            for e in range(s+2,len(cps)):
                seg=cps[s:e+1]
                if None in seg: continue
                if len(set(seg))==1:
                    ln=e-s+1
                    if ln==3: b+=1
                    if ln==4: c+=2
    return b,c


def score_goals(fg,goals,_prev):
    d=0; nc=[]
    for goal in goals:
        total=goal.check(fg); d+=total*2; nc.append(total)
    return d,nc


def score_half_motifs(fg):
    s=0
    for r in range(4):
        for c in range(4):
            if fg[r][c] is None: continue
            if r==0: s+=1
            if r==3: s+=1
            if c==0: s+=1
            if c==3: s+=1
    return s


def full_score(fg,goals,prev,is_last):
    a=score_motifs(fg); b,c=score_sequences(fg); d,nc=score_goals(fg,goals,prev)
    e=score_half_motifs(fg) if is_last else 0
    return a,b,c,d,e,a+b+c+d+e,nc


def floor_to_list(fg): return [[t.to_dict() if t else None for t in row] for row in fg]
def floor_from_list(data): return [[Tile.from_dict(cell) for cell in row] for row in data]


# ─────────────────────────────────────────────────────────────────────────────
# Server data structures (same as server.py)
# ─────────────────────────────────────────────────────────────────────────────
class PlayerState:
    def __init__(self, pid, name, ws):
        self.pid=pid; self.name=name; self.ws=ws
        self.floor=[[None]*4 for _ in range(4)]
        self.inventory=[]; self.storage=[]; self.storage_cap=4
        self.total_score=0; self.score_history=[]; self.goal_counts=[0,0,0]
        self.ready_next=False; self.placements_done=False

    def to_public_dict(self):
        return {"pid":self.pid,"name":self.name,"floor":floor_to_list(self.floor),
                "total_score":self.total_score,"storage_cap":self.storage_cap,
                "storage_count":len(self.storage)}

    def inventory_for_self(self): return [t.to_dict() for t in self.inventory]


class Lobby:
    def __init__(self,code):
        self.code=code; self.players=[]; self.host_pid=0
        self.started=False; self.round=0; self.supply=[]; self.goals=[]

    def add_player(self,name,ws):
        pid=len(self.players); p=PlayerState(pid,name,ws); self.players.append(p); return p

    def get_player_by_ws(self,ws):
        for p in self.players:
            if p.ws is ws: return p

    def all_placements_done(self): return all(p.placements_done for p in self.players)
    def all_ready_next(self): return all(p.ready_next for p in self.players)
    def public_players(self): return [p.to_public_dict() for p in self.players]


lobbies={}; ws_to_lobby={}


def gen_code():
    while True:
        code="".join(random.choices(string.ascii_uppercase+string.digits,k=6))
        if code not in lobbies: return code


async def send(ws,data):
    try: await ws.send(json.dumps(data))
    except Exception: pass


async def broadcast(lobby,data,exclude=None):
    for p in lobby.players:
        if p.ws is not exclude: await send(p.ws,data)


async def start_round(lobby):
    lobby.round+=1
    log.info(f"Lobby {lobby.code}: round {lobby.round}")
    for p in lobby.players: p.placements_done=False; p.ready_next=False
    for p in lobby.players:
        for _ in range(4):
            if lobby.supply: p.inventory.append(lobby.supply.pop())
    for n in (3,2,1):
        batches=[]
        for p in lobby.players:
            batch=p.inventory[:n]; p.inventory=p.inventory[n:]; batches.append(batch)
        np2=len(lobby.players)
        for i,p in enumerate(lobby.players): p.inventory.extend(batches[(i+1)%np2])
    goals_data=[g.to_dict() for g in lobby.goals]
    public=lobby.public_players()
    for p in lobby.players:
        await send(p.ws,{"type":"round_started","round":lobby.round,"goals":goals_data,
            "inventory":p.inventory_for_self(),"storage":[t.to_dict() for t in p.storage],
            "storage_cap":p.storage_cap,"players":public})


async def finish_round(lobby):
    is_last=(lobby.round==TOTAL_ROUNDS)
    round_results={}
    for p in lobby.players:
        a,b,c,d,e,total,nc=full_score(p.floor,lobby.goals,p.goal_counts,is_last)
        p.goal_counts=nc; p.total_score+=total
        round_results[str(p.pid)]={"a":a,"b":b,"c":c,"d":d,"e":e,"total":total,"cumulative":p.total_score}
        p.score_history.append(round_results[str(p.pid)])
        p.storage_cap=max(0,p.storage_cap-1)
        if len(p.storage)>p.storage_cap: p.storage=p.storage[:p.storage_cap]
    public=lobby.public_players()
    if is_last:
        winner=max(lobby.players,key=lambda p:p.total_score)
        await broadcast(lobby,{"type":"game_over","round_results":round_results,
            "players":public,"winner_pid":winner.pid,"winner_name":winner.name})
    else:
        await broadcast(lobby,{"type":"round_scores","round":lobby.round,
            "round_results":round_results,"players":public})


async def handle_create(ws,msg):
    name=str(msg.get("name","Player"))[:20]
    code=gen_code(); lobby=Lobby(code); lobbies[code]=lobby; ws_to_lobby[ws]=lobby
    p=lobby.add_player(name,ws)
    await send(ws,{"type":"lobby_created","code":code,"player_id":p.pid,"name":name})


async def handle_join(ws,msg):
    code=str(msg.get("code","")).upper(); name=str(msg.get("name","Player"))[:20]
    if code not in lobbies: await send(ws,{"type":"error","msg":"Lobby not found."}); return
    lobby=lobbies[code]
    if lobby.started: await send(ws,{"type":"error","msg":"Game already started."}); return
    if len(lobby.players)>=MAX_PLAYERS: await send(ws,{"type":"error","msg":f"Lobby full (max {MAX_PLAYERS})."}); return
    ws_to_lobby[ws]=lobby; p=lobby.add_player(name,ws)
    await send(ws,{"type":"lobby_joined","code":code,"player_id":p.pid,"name":name,"players":lobby.public_players()})
    await broadcast(lobby,{"type":"lobby_update","players":lobby.public_players()},exclude=ws)


async def handle_start(ws,lobby,player):
    if player.pid!=lobby.host_pid: await send(ws,{"type":"error","msg":"Only host can start."}); return
    if len(lobby.players)<2: await send(ws,{"type":"error","msg":"Need at least 2 players."}); return
    if lobby.started: return
    lobby.started=True; lobby.supply=make_supply(); lobby.goals=make_goals()
    await broadcast(lobby,{"type":"game_started","players":lobby.public_players(),"goals":[g.to_dict() for g in lobby.goals]})
    await start_round(lobby)


async def handle_place(ws,lobby,player,msg):
    if player.placements_done: return
    placements=msg.get("placements",[]); store_tids=msg.get("store_tids",[])
    inv_map={t.tid:t for t in player.inventory}
    for pm in placements:
        tid=pm["tid"]; r=pm["row"]; c=pm["col"]
        if tid in inv_map and player.floor[r][c] is None:
            player.floor[r][c]=inv_map.pop(tid)
    for tid in store_tids:
        if tid in inv_map and len(player.storage)<player.storage_cap:
            player.storage.append(inv_map.pop(tid))
    for tile in list(inv_map.values()):
        placed=False
        for r in range(4):
            for c in range(4):
                if player.floor[r][c] is None and not placed:
                    player.floor[r][c]=tile; placed=True
        if not placed and len(player.storage)<player.storage_cap:
            player.storage.append(tile)
    player.inventory=[]; player.placements_done=True
    await broadcast(lobby,{"type":"player_placed","pid":player.pid,"players":lobby.public_players()})
    if lobby.all_placements_done(): await finish_round(lobby)


async def handle_ready(ws,lobby,player):
    player.ready_next=True
    if lobby.all_ready_next() and lobby.round<TOTAL_ROUNDS: await start_round(lobby)


async def handler(ws):
    log.info(f"Connection: {ws.remote_address}")
    try:
        async for raw in ws:
            try: msg=json.loads(raw)
            except: continue
            t=msg.get("type"); lobby=ws_to_lobby.get(ws); player=lobby.get_player_by_ws(ws) if lobby else None
            if t=="ping": await send(ws,{"type":"pong"})
            elif t=="create_lobby": await handle_create(ws,msg)
            elif t=="join_lobby": await handle_join(ws,msg)
            elif t=="start_game" and lobby and player: await handle_start(ws,lobby,player)
            elif t=="place_tiles" and lobby and player: await handle_place(ws,lobby,player,msg)
            elif t=="ready_next_round" and lobby and player: await handle_ready(ws,lobby,player)
    except websockets.exceptions.ConnectionClosed: pass
    finally:
        log.info(f"Disconnected: {ws.remote_address}")
        if ws in ws_to_lobby:
            lobby=ws_to_lobby.pop(ws)
            if lobby:
                remaining=[p.to_public_dict() for p in lobby.players if p.ws is not ws]
                await broadcast(lobby,{"type":"lobby_update","players":remaining,"msg":"A player disconnected."})


async def health_check(connection, request):
    if request.headers.get("Upgrade", "").lower() != "websocket":
        return connection.respond(http.HTTPStatus.OK, "Chettinad Tiles WebSocket Server is Online!\n")
    return None

async def main():
    port=int(os.environ.get("PORT",8765)); host="0.0.0.0"
    log.info(f"Server on {host}:{port}")
    async with websockets.serve(handler,host,port,process_request=health_check):
        await asyncio.get_event_loop().create_future()

if __name__=="__main__":
    asyncio.run(main())
