"""
main.py – Chettinad Tiles client entry point.
Professional front-page, online lobby, full 4×4 floor game.
"""
from __future__ import annotations
import sys, os, math, random, string, time
import pygame
import pygame.gfxdraw

from network import NetworkClient, SERVER_URL, LOCAL_URL
from game_logic import (
    Tile, Goal, floor_from_list, supply_from_list,
    MOTIFS, CENTRES, MOTIF_COLOURS, CENTRE_COLOURS
)

# ─────────────────────────────────────────────────────────────────────────────
# Display / timing
# ─────────────────────────────────────────────────────────────────────────────
W, H = 1280, 800
FPS  = 60

# ─────────────────────────────────────────────────────────────────────────────
# Palette
# ─────────────────────────────────────────────────────────────────────────────
C = {
    "bg":        (16,  14,  22),
    "panel":     (28,  24,  38),
    "panel2":    (38,  32,  52),
    "border":    (80,  60, 100),
    "accent":    (220, 160,  60),
    "accent2":   (180,  80, 140),
    "white":     (255, 255, 255),
    "grey":      (140, 130, 150),
    "ltgrey":    (200, 190, 210),
    "red":       (200,  60,  60),
    "green":     (60,  180,  80),
    "darkred":   (120,  30,  30),
    "cream":     (255, 245, 220),
    "tile_bg":   (240, 232, 215),
    "tile_bdr":  (180, 160, 130),
    "slot_bg":   (45,  40,  60),
    "slot_bdr":  (80,  70,  95),
    "gold":      (255, 210,  50),
    "shadow":    (  0,   0,   0, 120),
}

TILE_SZ  = 76
GAP      = 5

# ─────────────────────────────────────────────────────────────────────────────
# Utility drawing helpers
# ─────────────────────────────────────────────────────────────────────────────
def aa_circle(surf, color, pos, r):
    pygame.gfxdraw.aacircle(surf, pos[0], pos[1], r, color)
    pygame.gfxdraw.filled_circle(surf, pos[0], pos[1], r, color)


def draw_rounded_rect(surf, color, rect, radius=10, border=0, border_color=None):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surf, border_color, rect, border, border_radius=radius)


def draw_text(surf, text, font, color, cx, cy, anchor="center"):
    rendered = font.render(text, True, color)
    r = rendered.get_rect()
    if anchor == "center": r.center = (cx, cy)
    elif anchor == "left": r.midleft = (cx, cy)
    elif anchor == "right": r.midright = (cx, cy)
    surf.blit(rendered, r)
    return r


def glow_rect(surf, color, rect, blur=8, alpha=80):
    """Simple glow by drawing successively larger translucent rects."""
    s = pygame.Surface((rect.w + blur*2, rect.h + blur*2), pygame.SRCALPHA)
    for i in range(blur, 0, -1):
        a = int(alpha * (blur - i + 1) / blur)
        col = (*color[:3], a)
        pygame.draw.rect(s, col, (blur-i, blur-i, rect.w+i*2, rect.h+i*2),
                         border_radius=10)
    surf.blit(s, (rect.x - blur, rect.y - blur))


# ─────────────────────────────────────────────────────────────────────────────
# Tile renderer
# ─────────────────────────────────────────────────────────────────────────────
_tile_cache: dict = {}

def render_tile(tile: Tile, size: int = TILE_SZ, selected: bool = False,
                alpha: int = 255) -> pygame.Surface:
    key = (tile.motif, tile.centre, size, selected)
    if key in _tile_cache:
        s = _tile_cache[key].copy()
        s.set_alpha(alpha)
        return s

    s = pygame.Surface((size, size), pygame.SRCALPHA)
    # Background
    pygame.draw.rect(s, C["tile_bg"], (0, 0, size, size), border_radius=6)
    # Motif corner ornaments
    mc  = MOTIF_COLOURS[tile.motif]
    cc  = CENTRE_COLOURS[tile.centre]
    hs  = size // 2
    cs  = max(4, size // 6)   # corner circle size

    for qr, qc in ((0,0),(0,1),(1,0),(1,1)):
        px = qc * hs + hs // 2
        py = qr * hs + hs // 2
        # Outer petal
        aa_circle(s, mc, (px, py), cs)
        # Inner highlight
        aa_circle(s, tuple(min(255,x+60) for x in mc), (px-cs//4, py-cs//4), cs//3)

    # Centrepiece
    _draw_centre(s, tile.centre, hs, hs, max(6, hs//2 - 4), cc)

    # Border
    bdr_col = C["accent"] if selected else C["tile_bdr"]
    bdr_w   = 3 if selected else 1
    pygame.draw.rect(s, bdr_col, (0, 0, size, size), bdr_w, border_radius=6)
    if selected:
        # glow
        glow_rect(s, C["accent"], pygame.Rect(0,0,size,size), blur=6, alpha=120)

    _tile_cache[key] = s.copy()
    s.set_alpha(alpha)
    return s


def _draw_centre(surf, name, cx, cy, r, color):
    if name == "Star":
        _star(surf, cx, cy, r, color)
    elif name == "Flower":
        _flower(surf, cx, cy, r, color)
    elif name == "Butterfly":
        _butterfly(surf, cx, cy, r, color)
    elif name == "Diamond":
        _diamond(surf, cx, cy, r, color)
    elif name == "Pinwheel":
        _pinwheel(surf, cx, cy, r, color)


def _star(surf, cx, cy, r, col):
    pts = []
    for i in range(8):
        a = math.radians(i*45 - 90)
        rr = r if i%2==0 else int(r*0.42)
        pts.append((cx + rr*math.cos(a), cy + rr*math.sin(a)))
    pygame.gfxdraw.aapolygon(surf, [(int(x),int(y)) for x,y in pts], col)
    pygame.gfxdraw.filled_polygon(surf, [(int(x),int(y)) for x,y in pts], col)
    aa_circle(surf, (0,0,0), (cx,cy), 3)

def _flower(surf, cx, cy, r, col):
    for i in range(6):
        a = math.radians(i*60)
        px = cx + int(r*0.55*math.cos(a)); py = cy + int(r*0.55*math.sin(a))
        aa_circle(surf, col, (px,py), r//3)
    aa_circle(surf, (255,245,180), (cx,cy), r//4)
    aa_circle(surf, (0,0,0), (cx,cy), r//4, )

def _butterfly(surf, cx, cy, r, col):
    s2 = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
    for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
        rx = r*3//4; ry = r//2
        pygame.draw.ellipse(s2, col,
            (r + dx*rx//2 - rx//2 + 2, r + dy*ry//2 - ry//2 + 2, rx, ry))
    surf.blit(s2, (cx - r - 2, cy - r - 2))
    aa_circle(surf, (60,60,60), (cx,cy), 4)

def _diamond(surf, cx, cy, r, col):
    pts = [(cx, cy-r),(cx+r,cy),(cx,cy+r),(cx-r,cy)]
    pygame.gfxdraw.aapolygon(surf, pts, col)
    pygame.gfxdraw.filled_polygon(surf, pts, col)
    inner = [(cx,cy-r//2),(cx+r//2,cy),(cx,cy+r//2),(cx-r//2,cy)]
    hi = tuple(min(255,x+80) for x in col)
    pygame.gfxdraw.filled_polygon(surf, inner, (*hi, 180))

def _pinwheel(surf, cx, cy, r, col):
    for i in range(4):
        a = math.radians(i*90)
        pts = [
            (cx, cy),
            (cx + int(r*math.cos(a)), cy + int(r*math.sin(a))),
            (cx + int(r*0.7*math.cos(a+math.radians(70))),
             cy + int(r*0.7*math.sin(a+math.radians(70)))),
        ]
        pygame.gfxdraw.filled_polygon(surf, pts, col)
        pygame.gfxdraw.aapolygon(surf, pts, col)
    aa_circle(surf, (0,0,0), (cx,cy), 4)


# ─────────────────────────────────────────────────────────────────────────────
# UI Widget: Button
# ─────────────────────────────────────────────────────────────────────────────
class Button:
    def __init__(self, rect, text, font, color=None, text_color=None, radius=10):
        self.rect       = pygame.Rect(rect)
        self.text       = text
        self.font       = font
        self.color      = color or C["accent"]
        self.text_color = text_color or C["bg"]
        self.radius     = radius
        self._hover     = False

    def draw(self, surf, mx, my):
        self._hover = self.rect.collidepoint(mx, my)
        col = tuple(min(255, x+25) for x in self.color) if self._hover else self.color
        draw_rounded_rect(surf, col, self.rect, self.radius)
        draw_text(surf, self.text, self.font, self.text_color,
                  self.rect.centerx, self.rect.centery)

    def clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN and
                event.button == 1 and
                self.rect.collidepoint(event.pos))


class TextInput:
    def __init__(self, rect, font, placeholder="", max_len=20):
        self.rect        = pygame.Rect(rect)
        self.font        = font
        self.placeholder = placeholder
        self.max_len     = max_len
        self.text        = ""
        self.active      = False
        self._cursor_t   = 0.0

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(ev.pos)
        if ev.type == pygame.KEYDOWN and self.active:
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key not in (pygame.K_RETURN, pygame.K_ESCAPE):
                if len(self.text) < self.max_len:
                    self.text += ev.unicode

    def draw(self, surf, dt):
        self._cursor_t = (self._cursor_t + dt) % 1.0
        bdr  = C["accent"] if self.active else C["border"]
        draw_rounded_rect(surf, C["panel2"], self.rect, 8, 2, bdr)
        disp = self.text
        if not disp and not self.active:
            disp = self.placeholder
            col  = C["grey"]
        else:
            col = C["white"]
        # Show cursor
        if self.active and self._cursor_t < 0.55:
            disp += "|"
        draw_text(surf, disp, self.font, col,
                  self.rect.x + 14, self.rect.centery, anchor="left")


# ─────────────────────────────────────────────────────────────────────────────
# Particle system (decorative background)
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    __slots__ = ("x","y","vx","vy","r","col","life","max_life")
    def __init__(self):
        self.reset()
    def reset(self):
        self.x    = random.uniform(0, W)
        self.y    = random.uniform(0, H)
        self.vx   = random.uniform(-0.3, 0.3)
        self.vy   = random.uniform(-0.6, -0.1)
        self.r    = random.randint(2, 6)
        cols      = list(CENTRE_COLOURS.values()) + list(MOTIF_COLOURS.values())
        self.col  = random.choice(cols)
        self.max_life = random.randint(120, 300)
        self.life = self.max_life
    def update(self):
        self.x   += self.vx; self.y += self.vy
        self.life -= 1
        if self.life <= 0 or self.y < -10:
            self.reset()
            self.y = H + 5
    def draw(self, surf):
        a   = int(255 * self.life / self.max_life)
        col = (*self.col, a)
        s2  = pygame.Surface((self.r*2+2, self.r*2+2), pygame.SRCALPHA)
        aa_circle(s2, col, (self.r+1, self.r+1), self.r)
        surf.blit(s2, (int(self.x)-self.r, int(self.y)-self.r))

PARTICLES = [Particle() for _ in range(60)]


# ─────────────────────────────────────────────────────────────────────────────
# Screens
# ─────────────────────────────────────────────────────────────────────────────
SCR_FRONT  = "front"
SCR_LOBBY  = "lobby"
SCR_WAIT   = "wait"
SCR_GAME   = "game"
SCR_SCORES = "scores"
SCR_OVER   = "gameover"
SCR_CONNECT= "connect"


class GameClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Chettinad Tiles")
        self.screen = pygame.display.set_mode((W, H))
        self.clock  = pygame.time.Clock()

        # Fonts
        self.fnt_xs  = pygame.font.SysFont("Segoe UI", 13)
        self.fnt_sm  = pygame.font.SysFont("Segoe UI", 16)
        self.fnt_md  = pygame.font.SysFont("Segoe UI", 20)
        self.fnt_lg  = pygame.font.SysFont("Segoe UI", 28, bold=True)
        self.fnt_xl  = pygame.font.SysFont("Segoe UI", 46, bold=True)
        self.fnt_xxl = pygame.font.SysFont("Segoe UI", 64, bold=True)

        self.net     = NetworkClient()
        self.screen_id = SCR_FRONT

        # Game state
        self.player_id   = -1
        self.my_name     = ""
        self.lobby_code  = ""
        self.players_info: list[dict] = []    # public player dicts from server
        self.goals:       list[Goal]  = []
        self.my_inventory: list[Tile] = []
        self.my_storage:  list[Tile]  = []
        self.my_storage_cap = 4
        self.my_floor = [[None]*4 for _ in range(4)]
        self.round    = 0
        self.selected_tile: Tile | None = None
        self.placements: list[dict]  = []     # {tid, row, col}
        self.store_tids: list[int]   = []
        self.round_results: dict     = {}
        self.final_data:   dict      = {}
        self.msg_log: list[str]      = []     # bottom message log
        self.is_host  = False
        self.game_over= False
        self.placement_done = False
        self.server_url = SERVER_URL
        self.connecting = False

        # Build front-page UI
        self._build_front()

    # ── screen builders ───────────────────────────────────────────────────
    def _build_front(self):
        mx, my = W//2, H//2
        self.inp_name    = TextInput((mx-160, 330, 320, 48), self.fnt_md, "Your Name…", 18)
        self.inp_code    = TextInput((mx-160, 460, 220, 48), self.fnt_md, "Lobby Code", 6)
        self.btn_create  = Button((mx-160, 560, 150, 46), "Create Lobby", self.fnt_md,
                                   color=C["accent"])
        self.btn_join    = Button((mx+10,  560, 150, 46), "Join Lobby",   self.fnt_md,
                                   color=C["accent2"], text_color=C["white"])
        self.btn_local   = Button((mx-80,  630, 160, 36), "Play Locally", self.fnt_sm,
                                   color=C["panel2"], text_color=C["grey"])
        self.inp_server  = TextInput((mx-300, H-80, 600, 36), self.fnt_sm,
                                     f"Server: {SERVER_URL}", 100)
        self.inp_server.text = SERVER_URL

    def _build_wait(self):
        self.btn_start = Button((W//2-100, H-120, 200, 48), "START GAME",
                                 self.fnt_lg, color=C["accent"])
        self.btn_copy  = Button((W//2+140, 200, 130, 38), "Copy Code",
                                 self.fnt_sm, color=C["panel2"], text_color=C["ltgrey"])

    # ── network handling ──────────────────────────────────────────────────
    def _process_net(self):
        while True:
            msg = self.net.recv()
            if msg is None:
                break
            t = msg.get("type")

            if t == "_connected":
                self.connecting = False
                self._log("Connected to server!")
            elif t == "_error":
                self.connecting = False
                self._log(f"Connection error: {msg.get('msg')}", error=True)
                self.screen_id = SCR_FRONT

            elif t == "lobby_created":
                self.player_id  = msg["player_id"]
                self.my_name    = msg["name"]
                self.lobby_code = msg["code"]
                self.is_host    = True
                self.players_info = [{"pid": 0, "name": self.my_name, "total_score": 0}]
                self._build_wait()
                self.screen_id = SCR_WAIT

            elif t == "lobby_joined":
                self.player_id    = msg["player_id"]
                self.my_name      = msg["name"]
                self.lobby_code   = msg["code"]
                self.players_info = msg["players"]
                self.is_host      = False
                self._build_wait()
                self.screen_id = SCR_WAIT

            elif t == "lobby_update":
                self.players_info = msg["players"]
                if "msg" in msg:
                    self._log(msg["msg"])

            elif t == "error":
                self._log(msg.get("msg","Server error"), error=True)
                self.screen_id = SCR_FRONT

            elif t == "game_started":
                self.players_info = msg["players"]
                self.goals        = [Goal.from_dict(g) for g in msg["goals"]]
                self.screen_id    = SCR_GAME
                self._log("Game started!")

            elif t == "round_started":
                self.round           = msg["round"]
                self.goals           = [Goal.from_dict(g) for g in msg["goals"]]
                self.my_inventory    = [Tile.from_dict(d) for d in msg["inventory"]]
                self.my_storage      = [Tile.from_dict(d) for d in msg["storage"]]
                self.my_storage_cap  = msg["storage_cap"]
                self.players_info    = msg["players"]
                self.my_floor        = self._find_my_floor(msg["players"])
                self.placements      = []
                self.store_tids      = []
                self.selected_tile   = None
                self.placement_done  = False
                self._log(f"Round {self.round} started! Place your tiles.")

            elif t == "player_placed":
                self.players_info = msg["players"]
                pname = next((p["name"] for p in msg["players"]
                              if p["pid"] == msg["pid"]), "?")
                self._log(f"{pname} placed their tiles.")

            elif t == "round_scores":
                self.round_results = msg
                self.players_info  = msg["players"]
                self.screen_id     = SCR_SCORES

            elif t == "game_over":
                self.final_data   = msg
                self.players_info = msg["players"]
                self.game_over    = True
                self.screen_id    = SCR_OVER

    def _find_my_floor(self, players):
        for p in players:
            if p["pid"] == self.player_id:
                return floor_from_list(p["floor"])
        return [[None]*4 for _ in range(4)]

    def _log(self, text, error=False):
        col = "(!) " if error else "→ "
        self.msg_log.append(col + text)
        if len(self.msg_log) > 6:
            self.msg_log.pop(0)

    # ── main loop ─────────────────────────────────────────────────────────
    def run(self):
        dt = 0.016
        while True:
            events = pygame.event.get()
            mx, my = pygame.mouse.get_pos()

            for ev in events:
                if ev.type == pygame.QUIT:
                    self.net.disconnect()
                    pygame.quit(); sys.exit()
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    if self.screen_id not in (SCR_FRONT, SCR_OVER):
                        pass  # could add pause menu

            self._process_net()
            self.screen.fill(C["bg"])

            if self.screen_id == SCR_FRONT:
                self._draw_front(events, mx, my, dt)
            elif self.screen_id == SCR_WAIT:
                self._draw_wait(events, mx, my)
            elif self.screen_id == SCR_GAME:
                self._draw_game(events, mx, my)
            elif self.screen_id == SCR_SCORES:
                self._draw_scores(events, mx, my)
            elif self.screen_id == SCR_OVER:
                self._draw_gameover(events, mx, my)

            pygame.display.flip()
            dt = self.clock.tick(FPS) / 1000.0

    # ─────────────────────────────────────────────────────────────────────
    # FRONT PAGE
    # ─────────────────────────────────────────────────────────────────────
    def _draw_front(self, events, mx, my, dt):
        # Particle background
        for p in PARTICLES:
            p.update(); p.draw(self.screen)

        # Decorative tile strip at top
        self._draw_deco_strip()

        # Title
        draw_text(self.screen, "CHETTINAD", self.fnt_xxl, C["accent"],  W//2, 100)
        draw_text(self.screen, "TILES",     self.fnt_xxl, C["accent2"], W//2, 160)
        draw_text(self.screen, "Athangudi Tiles Board Game  ·  Online Multiplayer",
                  self.fnt_sm, C["grey"], W//2, 210)

        # Panel
        panel = pygame.Rect(W//2-200, 295, 400, 400)
        draw_rounded_rect(self.screen, C["panel"], panel, 16, 2, C["border"])

        draw_text(self.screen, "Enter your name", self.fnt_sm, C["ltgrey"], W//2, 314)
        self.inp_name.draw(self.screen, dt)

        draw_text(self.screen, "─── Join or Create a Lobby ───", self.fnt_sm, C["grey"], W//2, 418)
        self.inp_code.draw(self.screen, dt)

        self.btn_create.draw(self.screen, mx, my)
        self.btn_join.draw(self.screen, mx, my)
        self.btn_local.draw(self.screen, mx, my)

        # Server URL line
        draw_text(self.screen, "Server URL:", self.fnt_xs, C["grey"], W//2-310, H-62, anchor="left")
        self.inp_server.draw(self.screen, dt)

        # Message log
        for i, line in enumerate(self.msg_log[-3:]):
            col = C["red"] if line.startswith("(!)") else C["grey"]
            draw_text(self.screen, line, self.fnt_xs, col, 20, H-75 + i*18, anchor="left")

        # Connecting spinner
        if self.connecting:
            t = time.time()
            dots = "." * (int(t*3) % 4)
            draw_text(self.screen, f"Connecting{dots}", self.fnt_sm, C["accent"], W//2, H//2)

        # Events
        for ev in events:
            self.inp_name.handle_event(ev)
            self.inp_code.handle_event(ev)
            self.inp_server.handle_event(ev)

            if self.btn_create.clicked(ev):
                self._do_create()
            if self.btn_join.clicked(ev):
                self._do_join()
            if self.btn_local.clicked(ev):
                self.server_url = LOCAL_URL
                self.inp_server.text = LOCAL_URL
                self._do_create()

    def _draw_deco_strip(self):
        """Small decorative tiles across the top."""
        y = 0
        size = 38
        for i, m in enumerate(MOTIFS * 8):
            c_name = CENTRES[i % len(CENTRES)]
            tile = Tile(m, c_name, -1)
            s = render_tile(tile, size)
            self.screen.blit(s, (i*(size+2), y))

    def _do_create(self):
        name = self.inp_name.text.strip() or "Player"
        url  = self.inp_server.text.strip() or SERVER_URL
        self.server_url = url
        self.connecting = True
        self.net.connect(url)
        # Wait briefly then send after connection
        pygame.time.set_timer(pygame.USEREVENT + 1, 800, loops=1)
        self._pending_action = ("create", name)

    def _do_join(self):
        name = self.inp_name.text.strip() or "Player"
        code = self.inp_code.text.strip().upper()
        if not code:
            self._log("Enter a lobby code to join!", error=True)
            return
        url  = self.inp_server.text.strip() or SERVER_URL
        self.server_url = url
        self.connecting = True
        self.net.connect(url)
        pygame.time.set_timer(pygame.USEREVENT + 1, 800, loops=1)
        self._pending_action = ("join", name, code)

    # ─────────────────────────────────────────────────────────────────────
    # WAIT / LOBBY SCREEN
    # ─────────────────────────────────────────────────────────────────────
    def _draw_wait(self, events, mx, my):
        # Process pending timer
        for ev in events:
            if ev.type == pygame.USEREVENT + 1:
                if hasattr(self, "_pending_action") and self.net.connected:
                    action = self._pending_action
                    if action[0] == "create":
                        self.net.send({"type": "create_lobby", "name": action[1]})
                    elif action[0] == "join":
                        self.net.send({"type": "join_lobby",
                                       "name": action[1], "code": action[2]})
                elif hasattr(self, "_pending_action") and not self.net.connected:
                    self._log("Could not connect to server.", error=True)
                    self.screen_id = SCR_FRONT
                    self.connecting = False

        # Draw
        draw_text(self.screen, "LOBBY", self.fnt_xl, C["accent"], W//2, 60)

        # Code display
        code_rect = pygame.Rect(W//2-180, 110, 360, 80)
        draw_rounded_rect(self.screen, C["panel"], code_rect, 16, 2, C["border"])
        draw_text(self.screen, "Lobby Code", self.fnt_sm, C["grey"], W//2, 130)
        draw_text(self.screen, self.lobby_code, self.fnt_xl, C["gold"], W//2, 165)

        # Players list
        draw_text(self.screen, f"Players  ({len(self.players_info)} / 6)", self.fnt_md, C["ltgrey"],
                  W//2, 218)
        for i, p in enumerate(self.players_info):
            y = 245 + i*52
            pr = pygame.Rect(W//2-220, y, 440, 44)
            draw_rounded_rect(self.screen, C["panel2"], pr, 10, 1, C["border"])
            host_tag = " 👑 HOST" if p["pid"] == 0 else ""
            me_tag   = " (YOU)"  if p["pid"] == self.player_id else ""
            draw_text(self.screen, f"Player {p['pid']+1}: {p['name']}{host_tag}{me_tag}",
                      self.fnt_md, C["white"], pr.centerx, pr.centery)

        # Copy button
        self.btn_copy.draw(self.screen, mx, my)
        for ev in events:
            if self.btn_copy.clicked(ev):
                try:
                    pygame.scrap.init()
                    pygame.scrap.put(pygame.SCRAP_TEXT, self.lobby_code.encode())
                    self._log("Code copied!")
                except Exception:
                    self._log(f"Code: {self.lobby_code}")

        # Start button (host only)
        if self.is_host:
            self.btn_start.draw(self.screen, mx, my)
            for ev in events:
                if self.btn_start.clicked(ev):
                    if len(self.players_info) >= 2:
                        self.net.send({"type": "start_game"})
                    else:
                        self._log("Need at least 2 players!", error=True)
        else:
            draw_text(self.screen, "Waiting for host to start…",
                      self.fnt_md, C["grey"], W//2, H-100)

        # Share instructions
        draw_text(self.screen, "Share the code with friends → they enter it and click Join Lobby",
                  self.fnt_sm, C["grey"], W//2, H-55)

        # Message log
        for i, line in enumerate(self.msg_log[-3:]):
            col = C["red"] if line.startswith("(!)") else C["grey"]
            draw_text(self.screen, line, self.fnt_xs, col, 20, H-38 + i*16, anchor="left")

    # ─────────────────────────────────────────────────────────────────────
    # GAME SCREEN
    # ─────────────────────────────────────────────────────────────────────
    def _draw_game(self, events, mx, my):
        # Layout zones
        FLOOR_X, FLOOR_Y = 40, 80
        INV_X,   INV_Y   = 40, 490
        STOR_X,  STOR_Y  = 40, 610
        GOAL_X,  GOAL_Y  = 680, 60
        OTHER_X, OTHER_Y = 870, 60
        LOG_Y            = H - 100

        # ── Header ──
        hdr = pygame.Rect(0, 0, W, 50)
        draw_rounded_rect(self.screen, C["panel"], hdr, 0)
        draw_text(self.screen, f"CHETTINAD TILES", self.fnt_lg, C["accent"], 200, 25)
        draw_text(self.screen, f"Round {self.round} / 4", self.fnt_md, C["ltgrey"], 430, 25)
        draw_text(self.screen, f"Lobby: {self.lobby_code}", self.fnt_sm, C["grey"], 600, 25, anchor="left")

        # ── My Floor ──
        draw_text(self.screen, "YOUR FLOOR", self.fnt_sm, C["accent"], FLOOR_X, FLOOR_Y - 18, anchor="left")
        self._draw_floor(self.my_floor, FLOOR_X, FLOOR_Y, events, mx, my)

        # ── Inventory ──
        draw_text(self.screen, f"HAND  ({len(self.my_inventory)} tiles)", self.fnt_sm,
                  C["ltgrey"], INV_X, INV_Y - 18, anchor="left")
        self._draw_inventory(events, mx, my, INV_X, INV_Y)

        # ── Storage ──
        draw_text(self.screen, f"STORAGE  ({len(self.my_storage)}/{self.my_storage_cap})",
                  self.fnt_sm, C["ltgrey"], STOR_X, STOR_Y - 18, anchor="left")
        self._draw_storage(events, mx, my, STOR_X, STOR_Y)

        # ── Goals ──
        self._draw_goals(GOAL_X, GOAL_Y)

        # ── Other Players (mini) ──
        self._draw_other_players(OTHER_X, OTHER_Y)

        # ── Scores side bar ──
        self._draw_scorebar(1140, 60)

        # ── Action buttons ──
        self._draw_action_buttons(events, mx, my)

        # ── Message log ──
        for i, line in enumerate(self.msg_log[-4:]):
            col = C["red"] if line.startswith("(!)") else C["grey"]
            draw_text(self.screen, line, self.fnt_xs, col, 20, LOG_Y + i * 16, anchor="left")

        # ── Waiting indicator ──
        if self.placement_done:
            draw_text(self.screen, "✓  Tiles placed — waiting for other players…",
                      self.fnt_md, C["green"], W//2, H - 30)

    def _draw_floor(self, floor_grid, ox, oy, events, mx, my):
        for r in range(4):
            for c in range(4):
                x = ox + c * (TILE_SZ + GAP)
                y = oy + r * (TILE_SZ + GAP)
                tile = floor_grid[r][c]
                if tile:
                    sel = False
                    surf = render_tile(tile, TILE_SZ, sel)
                    self.screen.blit(surf, (x, y))
                else:
                    draw_rounded_rect(self.screen, C["slot_bg"],
                                      pygame.Rect(x, y, TILE_SZ, TILE_SZ), 6, 1, C["slot_bdr"])
                    # Highlight empty slots if tile selected
                    if self.selected_tile and not self.placement_done:
                        draw_rounded_rect(self.screen, (*C["accent"][:3], 60),
                                          pygame.Rect(x, y, TILE_SZ, TILE_SZ), 6)
                        pygame.draw.rect(self.screen, C["accent"],
                                         pygame.Rect(x, y, TILE_SZ, TILE_SZ), 2, border_radius=6)
                        # Handle click
                        for ev in events:
                            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and
                                    pygame.Rect(x, y, TILE_SZ, TILE_SZ).collidepoint(mx, my)):
                                self._place_tile_at(r, c)

    def _place_tile_at(self, r, c):
        t = self.selected_tile
        if t and self.my_floor[r][c] is None:
            # Remove from inventory or storage
            if t in self.my_inventory:
                self.my_inventory.remove(t)
            elif t in self.my_storage:
                self.my_storage.remove(t)
            self.my_floor[r][c] = t
            self.placements.append({"tid": t.tid, "row": r, "col": c})
            self.selected_tile = None
            self._log(f"Placed {t.centre} {t.motif} tile.")

    def _draw_inventory(self, events, mx, my, ox, oy):
        for i, tile in enumerate(self.my_inventory):
            x = ox + i * (TILE_SZ + GAP + 2)
            sel = (tile is self.selected_tile)
            if sel:
                glow_rect(self.screen, C["accent"], pygame.Rect(x, oy, TILE_SZ, TILE_SZ))
            surf = render_tile(tile, TILE_SZ, sel)
            self.screen.blit(surf, (x, oy))
            draw_text(self.screen, tile.centre[:3], self.fnt_xs, C["grey"],
                      x + TILE_SZ//2, oy + TILE_SZ + 8)
            # Click to select
            if not self.placement_done:
                for ev in events:
                    if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and
                            pygame.Rect(x, oy, TILE_SZ, TILE_SZ).collidepoint(mx, my)):
                        self.selected_tile = tile if self.selected_tile is not tile else None

    def _draw_storage(self, events, mx, my, ox, oy):
        for i in range(self.my_storage_cap):
            x = ox + i * (TILE_SZ + GAP + 2)
            draw_rounded_rect(self.screen, C["slot_bg"],
                              pygame.Rect(x, oy, TILE_SZ, TILE_SZ), 6, 1, C["slot_bdr"])
            if i < len(self.my_storage):
                tile = self.my_storage[i]
                sel  = (tile is self.selected_tile)
                surf = render_tile(tile, TILE_SZ, sel)
                self.screen.blit(surf, (x, oy))
                if not self.placement_done:
                    for ev in events:
                        if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and
                                pygame.Rect(x, oy, TILE_SZ, TILE_SZ).collidepoint(mx, my)):
                            self.selected_tile = tile if self.selected_tile is not tile else None

        draw_text(self.screen, f"(Lose 1 slot after each round)", self.fnt_xs, C["grey"],
                  ox, oy + TILE_SZ + 10, anchor="left")

    def _draw_goals(self, ox, oy):
        draw_text(self.screen, "GOALS", self.fnt_sm, C["accent2"], ox, oy - 20, anchor="left")
        goal_names = ["G1", "G2", "G3"]
        for gi, goal in enumerate(self.goals):
            gx = ox + gi * 55
            for ti, motif in enumerate(goal.motifs):
                gy = oy + ti * 42
                mc = MOTIF_COLOURS[motif]
                draw_rounded_rect(self.screen, (*mc, 180), pygame.Rect(gx, gy, 48, 36), 6)
                draw_text(self.screen, motif[:4], self.fnt_xs, C["white"], gx+24, gy+18)
            draw_text(self.screen, goal_names[gi], self.fnt_xs, C["grey"],
                      gx + 24, oy + 3*42 + 6)

    def _draw_other_players(self, ox, oy):
        draw_text(self.screen, "OTHER PLAYERS", self.fnt_sm, C["ltgrey"], ox, oy - 20, anchor="left")
        others = [p for p in self.players_info if p["pid"] != self.player_id]
        for i, p in enumerate(others[:4]):
            y = oy + i * 88
            pr = pygame.Rect(ox, y, 240, 80)
            draw_rounded_rect(self.screen, C["panel2"], pr, 8, 1, C["border"])
            draw_text(self.screen, f"{p['name']}", self.fnt_sm, C["white"], ox + 8, y + 14, anchor="left")
            draw_text(self.screen, f"Score: {p['total_score']}", self.fnt_xs, C["grey"],
                      ox + 8, y + 34, anchor="left")
            # Mini floor
            f_data = p.get("floor")
            if f_data:
                fl = floor_from_list(f_data)
                ms = 14
                for r in range(4):
                    for c in range(4):
                        fx = ox + 130 + c*(ms+1)
                        fy = y + 6  + r*(ms+1)
                        draw_rounded_rect(self.screen, C["slot_bg"],
                                          pygame.Rect(fx, fy, ms, ms), 2)
                        if fl[r][c]:
                            mc = MOTIF_COLOURS[fl[r][c].motif]
                            draw_rounded_rect(self.screen, mc,
                                              pygame.Rect(fx+2, fy+2, ms-4, ms-4), 2)

    def _draw_scorebar(self, ox, oy):
        draw_text(self.screen, "SCORES", self.fnt_sm, C["accent"], ox, oy - 20, anchor="left")
        for i, p in enumerate(self.players_info):
            y = oy + i * 36
            col = C["accent"] if p["pid"] == self.player_id else C["white"]
            draw_text(self.screen, f"{p['name'][:10]}: {p['total_score']}",
                      self.fnt_sm, col, ox, y, anchor="left")

    def _draw_action_buttons(self, events, mx, my):
        # Store selected tile
        if (self.selected_tile and
                self.selected_tile in self.my_inventory and
                len(self.my_storage) < self.my_storage_cap and
                not self.placement_done):
            btn_store = Button((W-300, INV_Y := 490, 120, 40), "→ Store",
                                self.fnt_sm, color=C["panel2"], text_color=C["ltgrey"])
            btn_store.rect = pygame.Rect(W-160, 490, 120, 40)
            btn_store.draw(self.screen, mx, my)
            for ev in events:
                if btn_store.clicked(ev):
                    t = self.selected_tile
                    if t in self.my_inventory and len(self.my_storage) < self.my_storage_cap:
                        self.my_inventory.remove(t)
                        self.my_storage.append(t)
                        self.store_tids.append(t.tid)
                        self.selected_tile = None

        # Deselect
        if self.selected_tile:
            draw_text(self.screen, "Right-click or press ESC to deselect",
                      self.fnt_xs, C["grey"], W//2, H - 115)
            for ev in events:
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
                    self.selected_tile = None
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    self.selected_tile = None

        # Done placing button
        if not self.placement_done:
            btn_done = Button((W-210, H-70, 180, 48), "Done Placing",
                               self.fnt_md, color=C["accent"])
            btn_done.draw(self.screen, mx, my)
            for ev in events:
                if btn_done.clicked(ev):
                    self._submit_placements()

    def _submit_placements(self):
        """Send placements to server; force remaining hand tiles to storage/floor."""
        # Force remaining inventory
        for tile in list(self.my_inventory):
            if len(self.my_storage) < self.my_storage_cap:
                self.my_storage.append(tile)
                self.store_tids.append(tile.tid)
                self.my_inventory.remove(tile)
            else:
                # Force onto floor
                for r in range(4):
                    for c in range(4):
                        if self.my_floor[r][c] is None:
                            self.my_floor[r][c] = tile
                            self.placements.append({"tid": tile.tid, "row": r, "col": c})
                            self.my_inventory.remove(tile)
                            break
                    else:
                        continue
                    break

        self.net.send({
            "type":       "place_tiles",
            "placements": self.placements,
            "store_tids": self.store_tids,
        })
        self.placement_done = True
        self.selected_tile  = None
        self._log("Tiles submitted! Waiting for others…")

    # ─────────────────────────────────────────────────────────────────────
    # SCORES SCREEN
    # ─────────────────────────────────────────────────────────────────────
    def _draw_scores(self, events, mx, my):
        draw_text(self.screen, f"ROUND {self.round_results.get('round','?')} SCORES",
                  self.fnt_xl, C["accent"], W//2, 50)

        cols_x = [80, 260, 380, 480, 580, 680, 810]
        hdrs   = ["Player", "a) Motifs", "b) 3-seq", "c) 4-seq", "d) Goals", "e) Edges", "TOTAL"]
        for i, h in enumerate(hdrs):
            draw_text(self.screen, h, self.fnt_sm, C["accent2"], cols_x[i], 110, anchor="left")

        results = self.round_results.get("round_results", {})
        for ri, (pid_str, bd) in enumerate(results.items()):
            y   = 145 + ri*48
            pid = int(pid_str)
            p   = next((pp for pp in self.players_info if pp["pid"] == pid), {})
            vals = [p.get("name","?"), bd["a"], bd["b"], bd["c"], bd["d"], bd.get("e",0), bd["total"]]
            col = C["gold"] if pid == self.player_id else C["white"]
            for ci, v in enumerate(vals):
                draw_text(self.screen, str(v), self.fnt_md, col, cols_x[ci], y, anchor="left")

        # Cumulative
        draw_text(self.screen, "── Cumulative Scores ──", self.fnt_md, C["grey"], W//2, 380)
        for i, p in enumerate(sorted(self.players_info, key=lambda x: x["total_score"], reverse=True)):
            col = C["gold"] if p["pid"] == self.player_id else C["white"]
            draw_text(self.screen, f"{p['name']}: {p['total_score']} pts",
                      self.fnt_lg, col, W//2, 415 + i*44)

        # Floors
        y_fl = 590
        for i, p in enumerate(self.players_info[:4]):
            ox = 60 + i * 290
            draw_text(self.screen, p["name"][:10], self.fnt_sm, C["ltgrey"],
                      ox, y_fl - 18, anchor="left")
            fl_data = p.get("floor")
            if fl_data:
                fl = floor_from_list(fl_data)
                ms = 22
                for r in range(4):
                    for c in range(4):
                        fx = ox + c*(ms+2); fy = y_fl + r*(ms+2)
                        draw_rounded_rect(self.screen, C["slot_bg"], pygame.Rect(fx,fy,ms,ms), 3)
                        if fl[r][c]:
                            mc = MOTIF_COLOURS[fl[r][c].motif]
                            draw_rounded_rect(self.screen, mc, pygame.Rect(fx+3,fy+3,ms-6,ms-6), 2)

        btn_next = Button((W//2-120, H-65, 240, 50), "Ready for Next Round",
                           self.fnt_md, color=C["accent"])
        btn_next.draw(self.screen, mx, my)
        for ev in events:
            if btn_next.clicked(ev):
                self.net.send({"type": "ready_next_round"})
                self.screen_id = SCR_GAME
                self.placement_done = False

    # ─────────────────────────────────────────────────────────────────────
    # GAME OVER SCREEN
    # ─────────────────────────────────────────────────────────────────────
    def _draw_gameover(self, events, mx, my):
        # Particles in celebration colours
        for p in PARTICLES:
            p.update(); p.draw(self.screen)

        draw_text(self.screen, "GAME OVER", self.fnt_xxl, C["accent"], W//2, 80)

        winner_name = self.final_data.get("winner_name", "?")
        draw_text(self.screen, f"🏆  {winner_name} wins!", self.fnt_xl, C["gold"], W//2, 160)

        sorted_p = sorted(self.players_info, key=lambda x: x["total_score"], reverse=True)
        medals   = ["🥇", "🥈", "🥉", "4th", "5th", "6th"]
        for i, p in enumerate(sorted_p):
            col = C["gold"] if i==0 else (C["ltgrey"] if i==1 else C["grey"])
            draw_text(self.screen, f"{medals[i]}  {p['name']}: {p['total_score']} pts",
                      self.fnt_lg, col, W//2, 230 + i*52)

        # Per-player history from final_data round_results
        draw_text(self.screen, "Final Round Scoring", self.fnt_md, C["grey"], W//2, 530)
        res = self.final_data.get("round_results", {})
        for pid_str, bd in res.items():
            pid  = int(pid_str)
            p    = next((pp for pp in self.players_info if pp["pid"] == pid), {})
            col  = C["gold"] if pid == self.player_id else C["grey"]
            line = (f"{p.get('name','?')}: "
                    f"a={bd['a']} b={bd['b']} c={bd['c']} d={bd['d']} "
                    f"e={bd.get('e',0)} → {bd['total']} pts")
            draw_text(self.screen, line, self.fnt_sm, col, W//2, 560 + pid*22)

        btn_again = Button((W//2-160, H-80, 320, 52), "Return to Menu",
                            self.fnt_lg, color=C["accent"])
        btn_again.draw(self.screen, mx, my)
        for ev in events:
            if btn_again.clicked(ev):
                self.net.disconnect()
                self.__init__()   # full reset


# ─────────────────────────────────────────────────────────────────────────────
# Handle USEREVENT for delayed connection
# ─────────────────────────────────────────────────────────────────────────────
_orig_run = GameClient.run

def _patched_run(self):
    dt = 0.016
    while True:
        events = pygame.event.get()
        mx, my = pygame.mouse.get_pos()

        for ev in events:
            if ev.type == pygame.QUIT:
                self.net.disconnect()
                pygame.quit(); sys.exit()
            # Handle delayed connect callback
            if ev.type == pygame.USEREVENT + 1:
                if hasattr(self, "_pending_action"):
                    if self.net.connected:
                        action = self._pending_action
                        if action[0] == "create":
                            self.net.send({"type": "create_lobby", "name": action[1]})
                        elif action[0] == "join":
                            self.net.send({"type": "join_lobby",
                                           "name": action[1], "code": action[2]})
                        del self._pending_action
                    else:
                        # Not connected yet; retry once more after 800ms
                        pygame.time.set_timer(pygame.USEREVENT + 1, 800, loops=1)

        self._process_net()
        self.screen.fill(C["bg"])

        if self.screen_id == SCR_FRONT:
            self._draw_front(events, mx, my, dt)
        elif self.screen_id == SCR_WAIT:
            self._draw_wait(events, mx, my)
        elif self.screen_id == SCR_GAME:
            self._draw_game(events, mx, my)
        elif self.screen_id == SCR_SCORES:
            self._draw_scores(events, mx, my)
        elif self.screen_id == SCR_OVER:
            self._draw_gameover(events, mx, my)

        pygame.display.flip()
        dt = self.clock.tick(FPS) / 1000.0

GameClient.run = _patched_run


# ─────────────────────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    client = GameClient()
    client.run()
