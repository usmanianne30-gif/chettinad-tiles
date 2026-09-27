"""
game_logic.py – Pure game logic for Chettinad Tiles (no pygame dependency).
Shared between server and client.
"""
from __future__ import annotations
import random
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Tile constants
# ─────────────────────────────────────────────────────────────────────────────
MOTIFS  = ["Leaf", "Petal", "Arrow", "Swirl"]
CENTRES = ["Star", "Flower", "Butterfly", "Diamond", "Pinwheel"]

MOTIF_COLOURS = {
    "Leaf":      (70,  160,  70),
    "Petal":     (200, 100, 160),
    "Arrow":     (80,  120, 200),
    "Swirl":     (200, 140,  60),
}
CENTRE_COLOURS = {
    "Star":      (255, 200,  50),
    "Flower":    (220,  80, 140),
    "Butterfly": (100, 180, 240),
    "Diamond":   (160, 100, 220),
    "Pinwheel":  (80,  200, 120),
}

# ─────────────────────────────────────────────────────────────────────────────
# Tile
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Tile:
    motif:  str
    centre: str
    tid:    int

    def to_dict(self):
        return {"motif": self.motif, "centre": self.centre, "tid": self.tid}

    @staticmethod
    def from_dict(d):
        if d is None:
            return None
        return Tile(d["motif"], d["centre"], d["tid"])

    def __repr__(self):
        return f"T({self.motif[:2]},{self.centre[:2]},{self.tid})"


def make_supply() -> list[Tile]:
    """Create 70 Playing tiles (3 copies of each of 20 combos + 10 extras)."""
    tiles = []
    tid   = 0
    combos = [(m, c) for m in MOTIFS for c in CENTRES]   # 20 combos
    extras = random.sample(combos, 10)
    for m, c in combos:
        for _ in range(3):
            tiles.append(Tile(m, c, tid)); tid += 1
    for m, c in extras:
        tiles.append(Tile(m, c, tid)); tid += 1
    random.shuffle(tiles)
    return tiles


# ─────────────────────────────────────────────────────────────────────────────
# Goal
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Goal:
    """3-motif goal (column of 3 goal-tiles)."""
    motifs: list[str]   # 3 motif strings

    def to_dict(self):  return {"motifs": self.motifs}

    @staticmethod
    def from_dict(d):   return Goal(d["motifs"])

    # ── shape detection ──────────────────────────────────────────────────────
    def _valid_shape(self, p0, p1, p2) -> bool:
        pts  = [p0, p1, p2]
        rows = [p[0] for p in pts]
        cols = [p[1] for p in pts]
        sr   = sorted(rows); sc = sorted(cols)

        # Horizontal – same row, 3 consecutive cols (with wrap)
        if len(set(rows)) == 1:
            if sc == list(range(sc[0], sc[0]+3)):
                return True
            if set(cols) in ({0,2,3}, {0,1,3}):
                return True

        # Vertical – same col, 3 consecutive rows (with wrap)
        if len(set(cols)) == 1:
            if sr == list(range(sr[0], sr[0]+3)):
                return True
            if set(rows) in ({0,2,3}, {0,1,3}):
                return True

        # Diagonal (strict TL-BR or TR-BL, consecutive)
        dr = (rows[1]-rows[0], rows[2]-rows[1])
        dc = (cols[1]-cols[0], cols[2]-cols[1])
        if dr[0]==dr[1] and dc[0]==dc[1] and abs(dr[0])==1 and abs(dc[0])==1:
            return True

        # L-shape: any 2 in a row/col, 3rd perpendicular adjacent
        for a, b in [(0,1),(0,2),(1,2)]:
            c_idx = [x for x in range(3) if x not in (a,b)][0]
            ra,ca = pts[a]; rb,cb = pts[b]; rc,cc = pts[c_idx]
            if ra==rb and abs(ca-cb)==1:
                if (rc==ra+1 or rc==ra-1) and cc in (ca,cb):
                    return True
            if ca==cb and abs(ra-rb)==1:
                if (cc==ca+1 or cc==ca-1) and rc in (ra,rb):
                    return True
        return False

    def check(self, floor_grid) -> int:
        """Return # of times this goal is completed (different tile-sets)."""
        pos_for: dict[str, list] = {}
        for m in set(self.motifs):
            pos_for[m] = []
        for r in range(4):
            for c in range(4):
                t = floor_grid[r][c]
                if t and t.motif in pos_for:
                    pos_for[t.motif].append((r, c))

        count    = 0
        seen_pos = []   # track frozenset of positions used
        for p0 in pos_for[self.motifs[0]]:
            for p1 in pos_for[self.motifs[1]]:
                if p1 == p0: continue
                for p2 in pos_for[self.motifs[2]]:
                    if p2 in (p0, p1): continue
                    fs = frozenset([p0, p1, p2])
                    if fs in seen_pos: continue
                    if self._valid_shape(p0, p1, p2):
                        seen_pos.append(fs)
                        count += 1
        return count


def make_goals() -> list[Goal]:
    """Pick 3 goals; each is a column of 3 motifs (no two identical adjacent)."""
    goals = []
    for _ in range(3):
        col   = []
        tries = 0
        while len(col) < 3 and tries < 200:
            m = random.choice(MOTIFS)
            if col and col[-1] == m:
                tries += 1; continue
            col.append(m)
        goals.append(Goal(col))
    return goals


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────
def score_motifs(fg) -> int:
    """(a) +1 per completed motif (2×2 matching-motif block)."""
    s = 0
    for r in range(3):
        for c in range(3):
            quad = [fg[r][c], fg[r][c+1], fg[r+1][c], fg[r+1][c+1]]
            if all(quad) and len({t.motif for t in quad}) == 1:
                s += 1
    return s


def score_sequences(fg) -> tuple[int, int]:
    """(b) +1 per 3-centrepiece run; (c) +2 per 4-centrepiece run."""
    b = c = 0
    lines = []
    for r in range(4): lines.append([(r, cc) for cc in range(4)])
    for cc in range(4): lines.append([(rr, cc) for rr in range(4)])
    lines += [[(i, i) for i in range(4)], [(i, 3-i) for i in range(4)]]

    for line in lines:
        cps = [fg[r][cc].centre if fg[r][cc] else None for r, cc in line]
        for s in range(len(cps)):
            for e in range(s+2, len(cps)):
                seg = cps[s:e+1]
                if None in seg: continue
                if len(set(seg)) == 1:
                    ln = e - s + 1
                    if ln == 3: b += 1
                    if ln == 4: c += 2
    return b, c


def score_goals(fg, goals: list[Goal], prev_counts: list[int]) -> tuple[int, list[int]]:
    """(d) +2 per completed goal; re-scored each round (advantage for scoring early).
    Returns (d_score, new_counts)."""
    d = 0
    new = []
    for i, goal in enumerate(goals):
        total = goal.check(fg)
        d    += total * 2      # ALL completions scored every round
        new.append(total)
    return d, new


def score_half_motifs(fg) -> int:
    """(e) +1 per half-motif on edges (end-game only)."""
    s = 0
    for r in range(4):
        for c in range(4):
            if fg[r][c] is None: continue
            if r == 0: s += 1
            if r == 3: s += 1
            if c == 0: s += 1
            if c == 3: s += 1
    return s


def full_score(fg, goals, prev_counts, is_last: bool):
    """Compute all scoring categories."""
    a       = score_motifs(fg)
    b, c    = score_sequences(fg)
    d, nc   = score_goals(fg, goals, prev_counts)
    e       = score_half_motifs(fg) if is_last else 0
    return a, b, c, d, e, a+b+c+d+e, nc


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation helpers
# ─────────────────────────────────────────────────────────────────────────────
def floor_to_list(fg) -> list:
    return [[t.to_dict() if t else None for t in row] for row in fg]

def floor_from_list(data) -> list:
    return [[Tile.from_dict(cell) for cell in row] for row in data]

def supply_to_list(supply: list[Tile]) -> list:
    return [t.to_dict() for t in supply]

def supply_from_list(data) -> list[Tile]:
    return [Tile.from_dict(d) for d in data]
