"""
main.py – Chettinad Tiles: Athangudi Mansion Board Game
UNO Mobile Style UI/UX Edition (Multiplayer Online & Local)

Featuring:
- Stadium Felt Tabletop with realistic curved rim and Athangudi palace ambiance
- Dynamic Opponent Stadium Seating (2 to 6 players) with animated Avatars & Status
- Interactive Mini-Floors with Click-to-Inspect full Floor zoom
- Real-time UNO-style Emotes with comic speech bubbles
- Central Arena with 3D Goal Stand (G1, G2, G3) and Supply Tile Deck
- Animated UNO Card-Tray Hand with smooth tile lift on hover & pulse selection
- Athangudi Cement 4×4 Floor with ghost placement preview & undo
- Storage Vault Pedestals
- 3D Beveled Glossy Action Buttons (Done Placing, Store, Undo, Emotes, Rules)
- Illustrated In-Game Rulebook Modal
- UNO Podium Round-Score & Game-Over Screens
"""
from __future__ import annotations
import sys, os, math, random, string, time
from typing import Optional, List, Dict, Tuple
import pygame
import pygame.gfxdraw

from network import NetworkClient, SERVER_URL, LOCAL_URL
from game_logic import (
    Tile, Goal, floor_from_list, supply_from_list,
    MOTIFS, CENTRES, MOTIF_COLOURS, CENTRE_COLOURS
)

# ─────────────────────────────────────────────────────────────────────────────
# Window & Engine Timing
# ─────────────────────────────────────────────────────────────────────────────
W, H = 1280, 800
FPS  = 60

# ─────────────────────────────────────────────────────────────────────────────
# Color Palette (UNO Mobile meets Chettinad Heritage)
# ─────────────────────────────────────────────────────────────────────────────
PAL = {
    # Environment & Table
    "bg_dark":       (10,  14,  20),
    "table_wood":    (68,  34,  16),
    "table_wood_hi": (108, 56,  28),
    "table_gold":    (218, 172, 62),
    "felt_emerald":  (16,  54,  44),
    "felt_dark":     (10,  36,  30),
    "felt_stitch":   (26,  78,  64),
    
    # UI Elements & Cards
    "panel":         (24,  22,  34),
    "panel_border":  (62,  52,  80),
    "card_bg":       (32,  28,  44),
    "card_bg_hi":    (44,  38,  60),
    "white":         (255, 255, 255),
    "cream":         (252, 245, 226),
    "gold":          (255, 208, 48),
    "gold_glow":     (255, 225, 90),
    "text_muted":    (160, 155, 175),
    "text_dark":     (30,  28,  36),
    
    # UNO Mobile Signature Accents
    "uno_red":       (235, 45,  55),
    "uno_green":     (35,  190, 80),
    "uno_blue":      (30,  135, 245),
    "uno_yellow":    (255, 205, 30),
    "uno_purple":    (155, 75,  225),
    "uno_orange":    (245, 125, 30),
    
    # Athangudi Cement & Tiles
    "cement_slot":   (38,  35,  48),
    "cement_bdr":    (72,  65,  85),
    "cement_brass":  (190, 145, 55),
    "tile_face":     (246, 240, 224),
    "tile_border":   (175, 155, 130),
}

# Avatar color rings for up to 6 players
PLAYER_COLORS = [
    (30,  140, 245),  # 1: Blue (Player/Host)
    (235, 50,  60),   # 2: Red
    (35,  195, 80),   # 3: Green
    (255, 195, 30),   # 4: Yellow/Amber
    (170, 75,  235),  # 5: Purple
    (245, 120, 180),  # 6: Pink
]

# ─────────────────────────────────────────────────────────────────────────────
# Utility Drawing Helpers
# ─────────────────────────────────────────────────────────────────────────────
def aa_circle(surf: pygame.Surface, color: Tuple[int, ...], pos: Tuple[int, int], r: int):
    """Draw anti-aliased filled circle."""
    x, y = int(pos[0]), int(pos[1])
    r = int(r)
    if r <= 0: return
    if len(color) == 4 and color[3] < 255:
        s = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
        pygame.gfxdraw.aacircle(s, r+1, r+1, r, color)
        pygame.gfxdraw.filled_circle(s, r+1, r+1, r, color)
        surf.blit(s, (x - r - 1, y - r - 1))
    else:
        col3 = color[:3]
        pygame.gfxdraw.aacircle(surf, x, y, r, col3)
        pygame.gfxdraw.filled_circle(surf, x, y, r, col3)


def draw_rounded_rect(surf: pygame.Surface, color: Tuple[int, ...], rect: pygame.Rect,
                      radius: int = 12, border: int = 0, border_color: Optional[Tuple[int, ...]] = None):
    """Draw a smooth rounded rectangle with optional border."""
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border > 0 and border_color:
        pygame.draw.rect(surf, border_color, rect, border, border_radius=radius)


def draw_text(surf: pygame.Surface, text: str, font: pygame.font.Font, color: Tuple[int, ...],
              cx: int, cy: int, anchor: str = "center") -> pygame.Rect:
    """Render text with anchor positioning."""
    ren = font.render(str(text), True, color[:3])
    r = ren.get_rect()
    if anchor == "center":    r.center = (cx, cy)
    elif anchor == "left":    r.midleft = (cx, cy)
    elif anchor == "right":   r.midright = (cx, cy)
    elif anchor == "topleft": r.topleft = (cx, cy)
    surf.blit(ren, r)
    return r


def draw_glow_rect(surf: pygame.Surface, color: Tuple[int, ...], rect: pygame.Rect,
                   blur: int = 8, alpha: int = 90, radius: int = 12):
    """Render a soft luminous glow behind a rectangle."""
    glow_surf = pygame.Surface((rect.w + blur*2, rect.h + blur*2), pygame.SRCALPHA)
    for i in range(blur, 0, -2):
        a = int(alpha * (blur - i + 1) / blur)
        col = (*color[:3], a)
        pygame.draw.rect(glow_surf, col, (blur-i, blur-i, rect.w + i*2, rect.h + i*2),
                         border_radius=radius + 2)
    surf.blit(glow_surf, (rect.x - blur, rect.y - blur))


# ─────────────────────────────────────────────────────────────────────────────
# Athangudi Tile Surface Renderer
# ─────────────────────────────────────────────────────────────────────────────
_tile_surf_cache: Dict[Tuple, pygame.Surface] = {}

def render_athangudi_tile(tile: Tile, size: int = 76, selected: bool = False,
                         ghost: bool = False, alpha: int = 255) -> pygame.Surface:
    """Renders a gorgeous Athangudi ceramic floor tile with lacquer finish."""
    cache_key = (tile.motif, tile.centre, size, selected, ghost)
    if cache_key in _tile_surf_cache and alpha == 255:
        return _tile_surf_cache[cache_key].copy()

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    
    # Tile base
    base_col = (*PAL["tile_face"], 160 if ghost else 255)
    draw_rounded_rect(surf, base_col, pygame.Rect(0, 0, size, size), radius=8)

    mc = MOTIF_COLOURS.get(tile.motif, (100, 160, 80))
    cc = CENTRE_COLOURS.get(tile.centre, (240, 180, 50))
    hs = size // 2
    cs = max(5, int(size * 0.22))  # Corner petal radius

    # 4 Corner Partial Motifs (meeting points that connect 4 tiles into full motifs!)
    for qr, qc in ((0, 0), (0, 1), (1, 0), (1, 1)):
        cx = qc * hs + hs // 2
        cy = qr * hs + hs // 2
        # Outer petal
        p_col = (*mc, 140 if ghost else 255)
        aa_circle(surf, p_col, (cx, cy), cs)
        # Inner highlight
        hi_mc = tuple(min(255, c + 50) for c in mc)
        aa_circle(surf, (*hi_mc, 180 if ghost else 255), (cx - cs//4, cy - cs//4), max(2, cs//3))
        # Delicate dark border
        pygame.gfxdraw.aacircle(surf, cx, cy, cs, (40, 35, 30))

    # Centrepiece (Center of the Athangudi tile)
    cr = max(6, int(size * 0.20))
    _draw_tile_centrepiece(surf, tile.centre, hs, hs, cr, cc, ghost)

    # Lacquer bevel & border
    bdr_col = PAL["gold"] if selected else PAL["tile_border"]
    bdr_w   = 3 if selected else 1
    pygame.draw.rect(surf, bdr_col, (0, 0, size, size), bdr_w, border_radius=8)

    # Glossy top reflection sheen
    sheen = pygame.Surface((size - 4, size // 3), pygame.SRCALPHA)
    sheen.fill((255, 255, 255, 35 if not ghost else 15))
    surf.blit(sheen, (2, 2))

    if selected:
        draw_glow_rect(surf, PAL["gold"], pygame.Rect(0, 0, size, size), blur=6, alpha=140, radius=8)

    if alpha < 255:
        surf.set_alpha(alpha)
    else:
        _tile_surf_cache[cache_key] = surf.copy()

    return surf


def _draw_tile_centrepiece(surf: pygame.Surface, name: str, cx: int, cy: int,
                          r: int, color: Tuple[int, ...], ghost: bool):
    a = 150 if ghost else 255
    col = (*color[:3], a)
    
    if name == "Star":
        # 8-ray Athangudi radiant star
        pts = []
        for i in range(16):
            ang = math.radians(i * 22.5 - 90)
            rad = r if (i % 2 == 0) else int(r * 0.44)
            pts.append((int(cx + rad * math.cos(ang)), int(cy + rad * math.sin(ang))))
        pygame.gfxdraw.filled_polygon(surf, pts, col)
        pygame.gfxdraw.aapolygon(surf, pts, (30, 25, 20, a))
        aa_circle(surf, (255, 255, 220, a), (cx, cy), max(2, r // 4))

    elif name == "Flower":
        # 6-petal radiant Athangudi lotus
        for i in range(6):
            ang = math.radians(i * 60)
            px = int(cx + (r * 0.52) * math.cos(ang))
            py = int(cy + (r * 0.52) * math.sin(ang))
            aa_circle(surf, col, (px, py), max(3, int(r * 0.42)))
        aa_circle(surf, (255, 240, 160, a), (cx, cy), max(3, r // 3))
        aa_circle(surf, (40, 35, 30, a), (cx, cy), max(2, r // 4))

    elif name == "Butterfly":
        # 4-wing Athangudi medallion
        wing_w = int(r * 0.75)
        wing_h = int(r * 0.55)
        s2 = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            wx = r + 4 + dx * (wing_w // 2) - wing_w // 2
            wy = r + 4 + dy * (wing_h // 2) - wing_h // 2
            pygame.draw.ellipse(s2, col, (wx, wy, wing_w, wing_h))
            pygame.draw.ellipse(s2, (40, 35, 30, a), (wx, wy, wing_w, wing_h), 1)
        surf.blit(s2, (cx - r - 4, cy - r - 4))
        aa_circle(surf, (50, 45, 40, a), (cx, cy), 3)

    elif name == "Diamond":
        # Faceted gemstone rhombus
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.gfxdraw.filled_polygon(surf, pts, col)
        pygame.gfxdraw.aapolygon(surf, pts, (30, 25, 20, a))
        inner = [(cx, cy - r//2), (cx + r//2, cy), (cx, cy + r//2), (cx - r//2, cy)]
        hi = tuple(min(255, c + 70) for c in color[:3])
        pygame.gfxdraw.filled_polygon(surf, inner, (*hi, a))

    elif name == "Pinwheel":
        # 4-blade sun wheel
        for i in range(4):
            ang = math.radians(i * 90)
            pts = [
                (cx, cy),
                (int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang))),
                (int(cx + r * 0.72 * math.cos(ang + math.radians(65))),
                 int(cy + r * 0.72 * math.sin(ang + math.radians(65)))),
            ]
            pygame.gfxdraw.filled_polygon(surf, pts, col)
            pygame.gfxdraw.aapolygon(surf, pts, (30, 25, 20, a))
        aa_circle(surf, (40, 35, 30, a), (cx, cy), 3)


# ─────────────────────────────────────────────────────────────────────────────
# UI Widget: UNO Mobile 3D Beveled Button
# ─────────────────────────────────────────────────────────────────────────────
class UnoButton:
    """3D glossy rounded pill button in signature mobile game style."""
    def __init__(self, rect: Tuple[int, int, int, int], text: str, font: pygame.font.Font,
                 bg_color: Tuple[int, int, int] = PAL["uno_green"],
                 text_color: Tuple[int, int, int] = PAL["white"],
                 radius: int = 14, icon: str = ""):
        self.rect       = pygame.Rect(rect)
        self.text       = text
        self.font       = font
        self.bg_color   = bg_color
        self.text_color = text_color
        self.radius     = radius
        self.icon       = icon
        self.is_hovered = False
        self.is_pressed = False
        self.enabled    = True

    def draw(self, surf: pygame.Surface, mx: int, my: int, pulse: bool = False):
        self.is_hovered = self.rect.collidepoint(mx, my) and self.enabled
        
        # Lift animation on hover
        y_offset = -2 if (self.is_hovered and not self.is_pressed) else (2 if self.is_pressed else 0)
        draw_r = self.rect.move(0, y_offset)

        # Pulse glow when recommended / ready
        if pulse and self.enabled:
            pulse_a = int(80 + 40 * math.sin(time.time() * 6))
            draw_glow_rect(surf, self.bg_color, draw_r, blur=10, alpha=pulse_a, radius=self.radius)

        # Bottom 3D shadow bevel
        bevel_col = tuple(max(0, c - 60) for c in self.bg_color)
        shadow_r = draw_r.move(0, 4)
        draw_rounded_rect(surf, bevel_col, shadow_r, radius=self.radius)

        # Main face color (brighten on hover)
        face_col = self.bg_color
        if not self.enabled:
            face_col = (70, 68, 80)
        elif self.is_hovered:
            face_col = tuple(min(255, c + 25) for c in self.bg_color)

        draw_rounded_rect(surf, face_col, draw_r, radius=self.radius)

        # Top gloss reflection
        if self.enabled:
            gloss_r = pygame.Rect(draw_r.x + 3, draw_r.y + 2, draw_r.w - 6, draw_r.h // 2 - 2)
            gloss_surf = pygame.Surface((gloss_r.w, gloss_r.h), pygame.SRCALPHA)
            gloss_surf.fill((255, 255, 255, 45))
            surf.blit(gloss_surf, gloss_r.topleft)

        # Outline border
        bdr_col = (255, 255, 255, 120) if self.enabled else (90, 85, 100)
        pygame.draw.rect(surf, bdr_col, draw_r, 1, border_radius=self.radius)

        # Button Label
        full_text = f"{self.icon} {self.text}".strip() if self.icon else self.text
        txt_col = self.text_color if self.enabled else (130, 125, 140)
        draw_text(surf, full_text, self.font, txt_col, draw_r.centerx, draw_r.centery)

    def handle_event(self, ev: pygame.event.Event) -> bool:
        if not self.enabled: return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos):
                self.is_pressed = True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self.is_pressed and self.rect.collidepoint(ev.pos):
                self.is_pressed = False
                return True
            self.is_pressed = False
        return False


class TextInput:
    """Glossy input box with placeholder and caret animation."""
    def __init__(self, rect: Tuple[int, int, int, int], font: pygame.font.Font,
                 placeholder: str = "", max_len: int = 24):
        self.rect        = pygame.Rect(rect)
        self.font        = font
        self.placeholder = placeholder
        self.max_len     = max_len
        self.text        = ""
        self.active      = False
        self._caret_time = 0.0

    def handle_event(self, ev: pygame.event.Event):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(ev.pos)
        elif ev.type == pygame.KEYDOWN and self.active:
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.active = False
            elif len(self.text) < self.max_len and ev.unicode.isprintable():
                self.text += ev.unicode

    def draw(self, surf: pygame.Surface, dt: float):
        self._caret_time = (self._caret_time + dt) % 1.0
        bg_col = (36, 32, 48) if not self.active else (48, 42, 64)
        bdr_col = PAL["gold"] if self.active else PAL["panel_border"]
        
        if self.active:
            draw_glow_rect(surf, PAL["gold"], self.rect, blur=6, alpha=80, radius=8)
            
        draw_rounded_rect(surf, bg_col, self.rect, radius=8, border=2, border_color=bdr_col)
        
        disp = self.text
        if not disp and not self.active:
            draw_text(surf, self.placeholder, self.font, PAL["text_muted"],
                      self.rect.x + 14, self.rect.centery, anchor="left")
        else:
            if self.active and self._caret_time < 0.5:
                disp += "|"
            draw_text(surf, disp, self.font, PAL["white"],
                      self.rect.x + 14, self.rect.centery, anchor="left")


# ─────────────────────────────────────────────────────────────────────────────
# Ambient Table Particles
# ─────────────────────────────────────────────────────────────────────────────
class GoldParticle:
    __slots__ = ("x", "y", "vx", "vy", "size", "alpha", "life", "max_life")
    def __init__(self):
        self.reset()
    def reset(self):
        self.x = random.uniform(80, W - 80)
        self.y = random.uniform(80, H - 80)
        self.vx = random.uniform(-0.25, 0.25)
        self.vy = random.uniform(-0.45, -0.15)
        self.size = random.randint(2, 5)
        self.max_life = random.randint(120, 280)
        self.life = self.max_life
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if self.life <= 0 or self.y < 50:
            self.reset()
            self.y = H - 80
    def draw(self, surf: pygame.Surface):
        prog = self.life / self.max_life
        a = int(180 * math.sin(prog * math.pi))
        aa_circle(surf, (255, 220, 80, a), (int(self.x), int(self.y)), self.size)

AMBIENT_PARTICLES = [GoldParticle() for _ in range(45)]


# ─────────────────────────────────────────────────────────────────────────────
# Real-time Emotes Popup Definition
# ─────────────────────────────────────────────────────────────────────────────
EMOTE_LIST = [
    ("🤔", "Thinking..."),
    ("👏", "Nice Move!"),
    ("🍀", "Good Luck!"),
    ("😅", "Oops!"),
    ("✨", "Magic!"),
    ("🏆", "GG!"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main Game Client Class (UNO Mobile Edition)
# ─────────────────────────────────────────────────────────────────────────────
class GameClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Chettinad Tiles – Online Multiplayer")
        self.screen = pygame.display.set_mode((W, H))
        self.clock  = pygame.time.Clock()

        # Rich typography
        self.fnt_badge = pygame.font.SysFont("Segoe UI", 12, bold=True)
        self.fnt_sm    = pygame.font.SysFont("Segoe UI", 15, bold=False)
        self.fnt_md    = pygame.font.SysFont("Segoe UI", 18, bold=True)
        self.fnt_lg    = pygame.font.SysFont("Segoe UI", 24, bold=True)
        self.fnt_xl    = pygame.font.SysFont("Segoe UI", 36, bold=True)
        self.fnt_title = pygame.font.SysFont("Segoe UI", 56, bold=True)

        self.net = NetworkClient()
        self.state = "front"   # front, wait, game, scores, gameover

        # Network Game State
        self.player_id      = -1
        self.my_name        = ""
        self.lobby_code     = ""
        self.is_host        = False
        self.players_info:  List[dict] = []
        self.goals:         List[Goal] = []
        self.round          = 0
        
        # Local Player Inventory & Board
        self.my_floor       = [[None]*4 for _ in range(4)]
        self.my_inventory:  List[Tile] = []
        self.my_storage:    List[Tile] = []
        self.my_storage_cap = 4
        
        # Interactive Selection & Placement Tracking
        self.selected_tile:      Optional[Tile] = None
        self.selected_from:      str = ""       # "hand" or "storage"
        self.placements_this_rd: List[dict]     = []   # uncommitted {tid, row, col}
        self.store_tids_this_rd: List[int]      = []   # uncommitted tids in storage
        self.placement_done     = False
        
        # UNO Popups & Modals
        self.show_emotes_menu    = False
        self.show_rules_modal    = False
        self.inspect_player_pid: Optional[int] = None
        self.player_emotes:      Dict[int, dict] = {}  # pid -> {emoji, text, expiry}
        self.toast_msg:          str = ""
        self.toast_expiry:       float = 0.0

        # Build Title / Lobby UI
        self._build_front_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Building & Front Page
    # ─────────────────────────────────────────────────────────────────────────
    def _build_front_ui(self):
        cx, cy = W // 2, H // 2
        self.inp_name   = TextInput((cx - 160, 310, 320, 48), self.fnt_md, "Your Player Name…", 16)
        self.inp_code   = TextInput((cx - 160, 420, 220, 48), self.fnt_md, "Lobby Code", 6)
        self.btn_create = UnoButton((cx - 160, 500, 150, 50), "Host Game", self.fnt_md,
                                    bg_color=PAL["uno_green"])
        self.btn_join   = UnoButton((cx + 10,  500, 150, 50), "Join Lobby", self.fnt_md,
                                    bg_color=PAL["uno_blue"])
        self.btn_local  = UnoButton((cx - 100, 570, 200, 40), "Play Locally (LAN)", self.fnt_sm,
                                    bg_color=PAL["panel_border"])
        self.inp_server = TextInput((cx - 280, H - 65, 560, 36), self.fnt_sm,
                                    f"Server: {SERVER_URL}", 90)
        self.inp_server.text = SERVER_URL

        # Lobby wait buttons
        self.btn_start = UnoButton((W // 2 - 120, H - 120, 240, 54), "START GAME", self.fnt_lg,
                                   bg_color=PAL["uno_green"])
        self.btn_copy  = UnoButton((W // 2 + 130, 195, 120, 38), "Copy Code", self.fnt_sm,
                                   bg_color=PAL["uno_purple"])

        # In-game buttons (Right-hand control dock)
        self.btn_done_placing = UnoButton((1010, 570, 210, 56), "DONE PLACING", self.fnt_lg,
                                          bg_color=PAL["uno_green"])
        self.btn_store_tile   = UnoButton((1010, 640, 210, 46), "-> TO STORAGE", self.fnt_md,
                                          bg_color=PAL["uno_purple"])
        self.btn_undo         = UnoButton((1010, 700, 210, 42), "UNDO PLACED", self.fnt_sm,
                                          bg_color=PAL["panel_border"])
        
        # Header quick buttons
        self.btn_toggle_emotes = UnoButton((W - 130, 14, 110, 36), "EMOTES", self.fnt_sm,
                                           bg_color=PAL["uno_yellow"], text_color=PAL["text_dark"])
        self.btn_toggle_rules  = UnoButton((W - 250, 14, 105, 36), "RULES", self.fnt_sm,
                                           bg_color=PAL["uno_blue"])

    def show_toast(self, text: str, duration: float = 3.5):
        self.toast_msg = text
        self.toast_expiry = time.time() + duration

    # ─────────────────────────────────────────────────────────────────────────
    # Network Messaging
    # ─────────────────────────────────────────────────────────────────────────
    def _poll_network(self):
        while True:
            msg = self.net.recv()
            if msg is None: break
            mtype = msg.get("type")

            if mtype == "_connected":
                self.show_toast("Connected to Game Server! 🌐")
            elif mtype == "_error":
                self.show_toast(f"Connection error: {msg.get('msg')}")
                self.state = "front"

            elif mtype == "lobby_created":
                self.player_id      = msg["player_id"]
                self.my_name        = msg["name"]
                self.lobby_code     = msg["code"]
                self.is_host        = True
                self.players_info   = [{"pid": 0, "name": self.my_name, "total_score": 0}]
                self.state          = "wait"
                self.show_toast(f"Lobby {self.lobby_code} created! Share the code.")

            elif mtype == "lobby_joined":
                self.player_id      = msg["player_id"]
                self.my_name        = msg["name"]
                self.lobby_code     = msg["code"]
                self.players_info   = msg["players"]
                self.is_host        = False
                self.state          = "wait"
                self.show_toast(f"Joined Lobby {self.lobby_code}!")

            elif mtype == "lobby_update":
                self.players_info = msg["players"]
                if "msg" in msg:
                    self.show_toast(msg["msg"])

            elif mtype == "error":
                self.show_toast(f"(!) {msg.get('msg', 'Error')}")

            elif mtype == "game_started":
                self.players_info = msg["players"]
                self.goals        = [Goal.from_dict(g) for g in msg["goals"]]
                self.state        = "game"
                self.show_toast("Match Started! Pick & Pass Tiles.")

            elif mtype == "round_started":
                self.round               = msg["round"]
                self.goals               = [Goal.from_dict(g) for g in msg["goals"]]
                self.my_inventory        = [Tile.from_dict(d) for d in msg["inventory"]]
                self.my_storage          = [Tile.from_dict(d) for d in msg["storage"]]
                self.my_storage_cap      = msg["storage_cap"]
                self.players_info        = msg["players"]
                self.my_floor            = self._get_my_floor(msg["players"])
                self.placements_this_rd  = []
                self.store_tids_this_rd  = []
                self.selected_tile       = None
                self.placement_done      = False
                self.state               = "game"
                self.show_toast(f"Round {self.round} begins! Place tiles on your floor.")

            elif mtype == "player_placed":
                self.players_info = msg["players"]
                pname = next((p["name"] for p in msg["players"] if p["pid"] == msg["pid"]), "?")
                self.show_toast(f"✓ {pname} placed their tiles!")

            elif mtype == "player_emote":
                pid   = msg["pid"]
                emoji = msg["emoji"]
                text  = msg["text"]
                self.player_emotes[pid] = {
                    "emoji": emoji,
                    "text":  text,
                    "expiry": time.time() + 4.0
                }

            elif mtype == "round_scores":
                self.round_data   = msg
                self.players_info = msg["players"]
                self.state        = "scores"

            elif mtype == "game_over":
                self.final_data   = msg
                self.players_info = msg["players"]
                self.state        = "gameover"

    def _get_my_floor(self, players: List[dict]):
        for p in players:
            if p["pid"] == self.player_id:
                return floor_from_list(p["floor"])
        return [[None]*4 for _ in range(4)]

    # ─────────────────────────────────────────────────────────────────────────
    # Main Game Loop
    # ─────────────────────────────────────────────────────────────────────────
    def run(self):
        dt = 0.016
        while True:
            events = pygame.event.get()
            mx, my = pygame.mouse.get_pos()

            for ev in events:
                if ev.type == pygame.QUIT:
                    self.net.disconnect()
                    pygame.quit(); sys.exit()
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    # Close modals or deselect tile
                    if self.show_rules_modal:     self.show_rules_modal = False
                    elif self.show_emotes_menu:   self.show_emotes_menu = False
                    elif self.inspect_player_pid: self.inspect_player_pid = None
                    elif self.selected_tile:      self.selected_tile = None

            self._poll_network()
            self.screen.fill(PAL["bg_dark"])

            if self.state == "front":
                self._draw_front_screen(events, mx, my, dt)
            elif self.state == "wait":
                self._draw_lobby_wait_screen(events, mx, my)
            elif self.state == "game":
                self._draw_uno_game_screen(events, mx, my, dt)
            elif self.state == "scores":
                self._draw_scores_podium(events, mx, my)
            elif self.state == "gameover":
                self._draw_game_over_screen(events, mx, my)

            # Global Toast Message
            if time.time() < self.toast_expiry and self.toast_msg:
                self._draw_toast()

            pygame.display.flip()
            dt = self.clock.tick(FPS) / 1000.0

    # ─────────────────────────────────────────────────────────────────────────
    # SCREEN 1: FRONT TITLE & LOBBY BROWSER
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_front_screen(self, events: List[pygame.event.Event], mx: int, my: int, dt: float):
        for p in AMBIENT_PARTICLES:
            p.update(); p.draw(self.screen)

        # Title Logo Banner
        draw_text(self.screen, "CHETTINAD TILES", self.fnt_title, PAL["gold"], W // 2, 110)
        draw_text(self.screen, "ATHANGUDI MANSION EDITION  •  ONLINE MULTIPLAYER",
                  self.fnt_sm, PAL["gold_glow"], W // 2, 160)

        # Card container
        panel_rect = pygame.Rect(W // 2 - 200, 230, 400, 430)
        draw_glow_rect(self.screen, PAL["table_gold"], panel_rect, blur=12, alpha=60)
        draw_rounded_rect(self.screen, PAL["panel"], panel_rect, radius=16,
                          border=2, border_color=PAL["panel_border"])

        draw_text(self.screen, "ENTER YOUR NAME", self.fnt_badge, PAL["gold"], W // 2, 280)
        self.inp_name.draw(self.screen, dt)

        draw_text(self.screen, "JOIN OR HOST LOBBY", self.fnt_badge, PAL["text_muted"], W // 2, 390)
        self.inp_code.draw(self.screen, dt)

        self.btn_create.draw(self.screen, mx, my, pulse=True)
        self.btn_join.draw(self.screen, mx, my)
        self.btn_local.draw(self.screen, mx, my)

        # Server URL bar
        draw_text(self.screen, "SERVER ADDRESS:", self.fnt_badge, PAL["text_muted"], W // 2, H - 85)
        self.inp_server.draw(self.screen, dt)

        for ev in events:
            self.inp_name.handle_event(ev)
            self.inp_code.handle_event(ev)
            self.inp_server.handle_event(ev)

            if self.btn_create.handle_event(ev):
                self._connect_and_act("create")
            elif self.btn_join.handle_event(ev):
                self._connect_and_act("join")
            elif self.btn_local.handle_event(ev):
                self.inp_server.text = LOCAL_URL
                self._connect_and_act("create")

    def _connect_and_act(self, action: str):
        name = self.inp_name.text.strip() or f"Artisan_{random.randint(10,99)}"
        url  = self.inp_server.text.strip() or SERVER_URL
        self.my_name = name
        self.show_toast("Connecting to server...")
        self.net.connect(url)
        
        # Action queue
        def do_send():
            time.sleep(0.4)
            if action == "create":
                self.net.send({"type": "create_lobby", "name": name})
            elif action == "join":
                code = self.inp_code.text.strip().upper()
                if not code:
                    self.show_toast("Please enter a 6-character Lobby Code!")
                    return
                self.net.send({"type": "join_lobby", "name": name, "code": code})
                
        import threading
        threading.Thread(target=do_send, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # SCREEN 2: LOBBY WAITING ROOM (UNO Style Seats)
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_lobby_wait_screen(self, events: List[pygame.event.Event], mx: int, my: int):
        for p in AMBIENT_PARTICLES:
            p.update(); p.draw(self.screen)

        draw_text(self.screen, "LOBBY ROOM", self.fnt_xl, PAL["gold"], W // 2, 60)

        # Code Card
        card_r = pygame.Rect(W // 2 - 180, 110, 360, 85)
        draw_glow_rect(self.screen, PAL["gold"], card_r, blur=10, alpha=80)
        draw_rounded_rect(self.screen, PAL["panel"], card_r, radius=14,
                          border=2, border_color=PAL["table_gold"])
        draw_text(self.screen, "ROOM CODE", self.fnt_badge, PAL["text_muted"], W // 2, 135)
        draw_text(self.screen, self.lobby_code, self.fnt_title, PAL["cream"], W // 2 - 30, 165)
        self.btn_copy.draw(self.screen, mx, my)

        # 6 Stadium Seats
        draw_text(self.screen, f"PLAYERS SEATED  ({len(self.players_info)} / 6)",
                  self.fnt_md, PAL["white"], W // 2, 235)

        for i in range(6):
            col_idx = i % 3
            row_idx = i // 3
            sx = W // 2 - 280 + col_idx * 190
            sy = 270 + row_idx * 130
            seat_r = pygame.Rect(sx, sy, 175, 110)

            if i < len(self.players_info):
                pdata = self.players_info[i]
                p_col = PLAYER_COLORS[i % len(PLAYER_COLORS)]
                draw_rounded_rect(self.screen, PAL["card_bg"], seat_r, radius=12,
                                  border=2, border_color=p_col)
                # Avatar
                aa_circle(self.screen, p_col, (seat_r.centerx, sy + 38), 24)
                draw_text(self.screen, pdata["name"][:2].upper(), self.fnt_md, PAL["white"],
                          seat_r.centerx, sy + 38)
                if pdata.get("pid") == 0:
                    draw_text(self.screen, "👑", self.fnt_sm, PAL["gold"], seat_r.centerx + 16, sy + 18)
                
                # Name
                name_disp = pdata["name"] + (" (YOU)" if pdata["pid"] == self.player_id else "")
                draw_text(self.screen, name_disp[:14], self.fnt_sm, PAL["white"], seat_r.centerx, sy + 76)
                draw_text(self.screen, "READY", self.fnt_badge, PAL["uno_green"], seat_r.centerx, sy + 94)
            else:
                # Empty seat
                draw_rounded_rect(self.screen, (22, 20, 30), seat_r, radius=12,
                                  border=1, border_color=PAL["panel_border"])
                aa_circle(self.screen, (40, 38, 52), (seat_r.centerx, sy + 38), 22)
                draw_text(self.screen, "+", self.fnt_lg, PAL["text_muted"], seat_r.centerx, sy + 38)
                draw_text(self.screen, "Waiting...", self.fnt_sm, PAL["text_muted"], seat_r.centerx, sy + 78)

        # Host start button
        if self.is_host:
            can_start = len(self.players_info) >= 2
            self.btn_start.enabled = can_start
            self.btn_start.draw(self.screen, mx, my, pulse=can_start)
        else:
            draw_text(self.screen, "Waiting for Host to start match…",
                      self.fnt_lg, PAL["gold"], W // 2, H - 90)

        for ev in events:
            if self.btn_copy.handle_event(ev):
                try:
                    pygame.scrap.init()
                    pygame.scrap.put(pygame.SCRAP_TEXT, self.lobby_code.encode())
                    self.show_toast("Code copied to clipboard! 📋")
                except Exception:
                    self.show_toast(f"Lobby Code: {self.lobby_code}")
            if self.is_host and self.btn_start.handle_event(ev):
                self.net.send({"type": "start_game"})

    # ─────────────────────────────────────────────────────────────────────────
    # SCREEN 3: UNO MOBILE STYLE IN-GAME PLAY AREA
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_uno_game_screen(self, events: List[pygame.event.Event], mx: int, my: int, dt: float):
        # 1. Render the Oval Felt Table Stadium
        self._draw_stadium_table()

        # 2. Opponent Avatars arranged along table arc
        self._draw_opponent_stadium(mx, my)

        # 3. Center Table: The 3 Goal Cards & Supply Tile Deck
        self._draw_center_arena(mx, my)

        # 4. Player Zone (Bottom): 4x4 Floor, Hand Card Tray, Storage Pedestals
        self._draw_player_floor_grid(events, mx, my)
        self._draw_storage_vault(events, mx, my)
        self._draw_player_hand_tray(events, mx, my)

        # 5. Right Action Controls
        self._draw_action_controls(events, mx, my)

        # 6. Top Header Bar
        self._draw_top_hud(events, mx, my)

        # 7. Modals / Overlays (Rules, Emotes, Inspect Player)
        if self.show_rules_modal:
            self._draw_rules_modal(events, mx, my)
        elif self.show_emotes_menu:
            self._draw_emotes_menu(events, mx, my)
        elif self.inspect_player_pid is not None:
            self._draw_inspect_modal(events, mx, my)

    # ── Table & Environment ──────────────────────────────────────────────────
    def _draw_stadium_table(self):
        """Draws the massive curved gaming table with teakwood rim and emerald felt."""
        # Ambient table glow
        table_rect = pygame.Rect(40, 60, W - 80, H - 100)
        
        # Wood border rim
        pygame.draw.ellipse(self.screen, PAL["table_wood"], table_rect)
        pygame.draw.ellipse(self.screen, PAL["table_wood_hi"], table_rect, 4)
        
        # Gold brass inlay ring
        inner_gold = table_rect.inflate(-20, -20)
        pygame.draw.ellipse(self.screen, PAL["table_gold"], inner_gold, 3)

        # Emerald felt interior
        felt_rect = table_rect.inflate(-30, -30)
        pygame.draw.ellipse(self.screen, PAL["felt_emerald"], felt_rect)
        
        # Subtle felt stitch circle
        stitch_rect = felt_rect.inflate(-40, -40)
        pygame.draw.ellipse(self.screen, PAL["felt_stitch"], stitch_rect, 1)

    # ── Opponents Stadium Seating ────────────────────────────────────────────
    def _draw_opponent_stadium(self, mx: int, my: int):
        """Dynamically arranges opponent pods along the stadium perimeter."""
        opponents = [p for p in self.players_info if p["pid"] != self.player_id]
        if not opponents: return

        # Pre-calculated seat anchors along the stadium arc (X, Y)
        seat_positions = []
        n = len(opponents)
        if n == 1:
            seat_positions = [(W // 2, 115)]
        elif n == 2:
            seat_positions = [(W // 2 - 250, 115), (W // 2 + 250, 115)]
        elif n == 3:
            seat_positions = [(200, 160), (W // 2, 105), (W - 200, 160)]
        elif n == 4:
            seat_positions = [(170, 190), (430, 105), (850, 105), (W - 170, 190)]
        else:
            seat_positions = [(160, 210), (390, 110), (W // 2, 95), (890, 110), (W - 160, 210)]

        for i, opp in enumerate(opponents[:5]):
            ox, oy = seat_positions[i]
            pid = opp["pid"]
            p_col = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
            
            # Pod Card
            card_r = pygame.Rect(ox - 85, oy - 38, 170, 76)
            is_hover = card_r.collidepoint(mx, my)
            
            if is_hover:
                draw_glow_rect(self.screen, p_col, card_r, blur=8, alpha=100)

            draw_rounded_rect(self.screen, PAL["panel"], card_r, radius=14,
                              border=2, border_color=p_col if not is_hover else PAL["gold"])

            # Circular Avatar
            avatar_center = (ox - 48, oy)
            aa_circle(self.screen, p_col, avatar_center, 24)
            draw_text(self.screen, opp["name"][:2].upper(), self.fnt_md, PAL["white"], *avatar_center)
            
            if pid == 0:
                draw_text(self.screen, "HOST", self.fnt_badge, PAL["gold"], avatar_center[0] + 16, avatar_center[1] - 18)

            # Name & Score
            draw_text(self.screen, opp["name"][:10], self.fnt_sm, PAL["white"], ox + 18, oy - 14)
            draw_text(self.screen, f"{opp.get('total_score', 0)} PTS", self.fnt_badge, PAL["gold"], ox + 18, oy + 4)

            # Status pill (Placed or Thinking)
            f_data = opp.get("floor", [])
            tile_count = sum(1 for row in f_data for cell in row if cell)
            has_placed = (tile_count >= self.round * 4)  # rough check or from server flag
            status_text = "READY" if has_placed else "THINKING..."
            status_col  = PAL["uno_green"] if has_placed else PAL["uno_yellow"]
            draw_text(self.screen, status_text, self.fnt_badge, status_col, ox + 18, oy + 22)

            # Mini 4x4 Floor preview button
            mini_r = pygame.Rect(card_r.right + 6, oy - 24, 48, 48)
            draw_rounded_rect(self.screen, PAL["cement_slot"], mini_r, radius=6,
                              border=1, border_color=PAL["cement_bdr"])
            fl_data = opp.get("floor")
            if fl_data:
                for r in range(4):
                    for c in range(4):
                        cell = fl_data[r][c]
                        if cell:
                            motif_name = cell.get("motif") if isinstance(cell, dict) else getattr(cell, "motif", "")
                            mc = MOTIF_COLOURS.get(motif_name, (120, 120, 120))
                            mx_p = mini_r.x + 3 + c * 11
                            my_p = mini_r.y + 3 + r * 11
                            pygame.draw.rect(self.screen, mc, (mx_p, my_p, 9, 9), border_radius=2)

            # Hover tooltip to inspect
            if is_hover or mini_r.collidepoint(mx, my):
                draw_text(self.screen, "Click to view full floor", self.fnt_badge, PAL["cream"],
                          ox, card_r.bottom + 12)
                if pygame.mouse.get_pressed()[0]:
                    self.inspect_player_pid = pid

            # Active Emote Bubble
            if pid in self.player_emotes:
                em = self.player_emotes[pid]
                if time.time() < em["expiry"]:
                    self._draw_speech_bubble(ox, card_r.top - 24, em["emoji"], em["text"])

    def _draw_speech_bubble(self, cx: int, cy: int, emoji: str, text: str):
        """Draws an animated comic speech bubble above an avatar."""
        bub_w = max(110, len(text) * 9 + 36)
        bub_r = pygame.Rect(cx - bub_w // 2, cy - 14, bub_w, 32)
        draw_glow_rect(self.screen, (255, 255, 255), bub_r, blur=6, alpha=80)
        draw_rounded_rect(self.screen, PAL["cream"], bub_r, radius=12,
                          border=2, border_color=(40, 35, 45))
        # Bubble pointer
        pts = [(cx - 6, bub_r.bottom), (cx + 6, bub_r.bottom), (cx, bub_r.bottom + 8)]
        pygame.draw.polygon(self.screen, PAL["cream"], pts)
        draw_text(self.screen, text, self.fnt_sm, PAL["text_dark"], bub_r.centerx, bub_r.centery)

    # ── Center Table Arena (Goals & Supply Deck) ─────────────────────────────
    def _draw_center_arena(self, mx: int, my: int):
        """Draws the 3 Goal Pedestals and Supply Pile in the center of the stadium table."""
        # 1. The 3 Goal Stands
        gw, gh = 72, 145
        start_gx = W // 2 - 125
        gy = 205

        draw_text(self.screen, "MATCH 3 GOALS (+2 PTS EACH)", self.fnt_badge, PAL["gold"], W // 2, gy - 16)

        for gi, goal in enumerate(self.goals):
            gx = start_gx + gi * 90
            goal_r = pygame.Rect(gx, gy, gw, gh)
            is_hover = goal_r.collidepoint(mx, my)

            # Tablet backing
            draw_rounded_rect(self.screen, PAL["card_bg"], goal_r, radius=10,
                              border=2, border_color=PAL["table_gold"] if not is_hover else PAL["gold"])

            # Goal label pill
            pill_r = pygame.Rect(gx + 6, gy + 5, gw - 12, 20)
            draw_rounded_rect(self.screen, PAL["felt_dark"], pill_r, radius=6)
            draw_text(self.screen, f"GOAL {gi+1}", self.fnt_badge, PAL["gold"], pill_r.centerx, pill_r.centery)

            # 3 Motifs stacked vertically
            for ti, motif in enumerate(goal.motifs):
                my_pos = gy + 32 + ti * 36
                mc = MOTIF_COLOURS.get(motif, (100, 100, 100))
                slot_r = pygame.Rect(gx + 12, my_pos, gw - 24, 30)
                draw_rounded_rect(self.screen, (*mc, 200), slot_r, radius=6)
                pygame.draw.rect(self.screen, (255, 255, 255), slot_r, 1, border_radius=6)
                draw_text(self.screen, motif[:4].upper(), self.fnt_badge, PAL["white"],
                          slot_r.centerx, slot_r.centery)

            # Tooltip on hover
            if is_hover:
                tip = f"Goal {gi+1}: Form {goal.motifs[0]} -> {goal.motifs[1]} -> {goal.motifs[2]} (H/V/Diag/L/Wrap)"
                draw_text(self.screen, tip, self.fnt_sm, PAL["cream"], W // 2, gy + gh + 16)

        # 2. Supply Pile (Draw Deck) on Left
        deck_r = pygame.Rect(W // 2 - 270, 225, 78, 95)
        # Isometric stacked shadow layers
        for layer in range(3, 0, -1):
            pygame.draw.rect(self.screen, (30, 26, 38), deck_r.move(layer * 2, layer * 2), border_radius=8)
        draw_rounded_rect(self.screen, PAL["panel"], deck_r, radius=8, border=2, border_color=PAL["table_gold"])
        draw_text(self.screen, "SUPPLY", self.fnt_badge, PAL["gold"], deck_r.centerx, deck_r.y + 18)
        tile_icon_r = pygame.Rect(deck_r.centerx - 14, deck_r.y + 36, 28, 28)
        draw_rounded_rect(self.screen, PAL["tile_face"], tile_icon_r, radius=4, border=1, border_color=PAL["tile_border"])
        aa_circle(self.screen, PAL["table_gold"], tile_icon_r.center, 6)
        draw_text(self.screen, "DECK", self.fnt_badge, PAL["text_muted"], deck_r.centerx, deck_r.y + 76)

        # 3. Dynamic Center Phase Banner
        banner_r = pygame.Rect(W // 2 - 170, 375, 340, 36)
        draw_rounded_rect(self.screen, PAL["panel"], banner_r, radius=18,
                          border=2, border_color=PAL["felt_stitch"])
        phase_str = f"ROUND {self.round} OF 4  •  PLACEMENT PHASE"
        draw_text(self.screen, phase_str, self.fnt_badge, PAL["cream"], banner_r.centerx, banner_r.centery)

    # ── Player Floor (Cement 4x4 Grid) ───────────────────────────────────────
    def _draw_player_floor_grid(self, events: List[pygame.event.Event], mx: int, my: int):
        """Draws the player's 4x4 Athangudi cement floor with ghost placement preview."""
        ox, oy = 55, 435
        cell_sz = 72
        gap = 5
        grid_w = cell_sz * 4 + gap * 3
        
        # Floor frame & title
        floor_frame = pygame.Rect(ox - 10, oy - 32, grid_w + 20, grid_w + 42)
        draw_rounded_rect(self.screen, PAL["panel"], floor_frame, radius=14,
                          border=2, border_color=PAL["cement_brass"])
        draw_text(self.screen, "YOUR 4×4 MANSION FLOOR", self.fnt_sm, PAL["gold"],
                  floor_frame.centerx, oy - 16)

        for r in range(4):
            for c in range(4):
                cx = ox + c * (cell_sz + gap)
                cy = oy + r * (cell_sz + gap)
                cell_r = pygame.Rect(cx, cy, cell_sz, cell_sz)
                tile = self.my_floor[r][c]

                if tile:
                    # Render placed tile
                    surf = render_athangudi_tile(tile, size=cell_sz)
                    self.screen.blit(surf, (cx, cy))
                    
                    # If clicked an uncommitted tile placed this round -> pick back up!
                    if not self.placement_done:
                        for ev in events:
                            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and cell_r.collidepoint(mx, my):
                                for pm in list(self.placements_this_rd):
                                    if pm["row"] == r and pm["col"] == c and pm["tid"] == tile.tid:
                                        self.my_floor[r][c] = None
                                        self.placements_this_rd.remove(pm)
                                        self.my_inventory.append(tile)
                                        self.show_toast("Tile returned to hand.")
                                        break
                else:
                    # Empty cement mortar slot
                    draw_rounded_rect(self.screen, PAL["cement_slot"], cell_r, radius=8,
                                      border=1, border_color=PAL["cement_bdr"])

                    # Ghost hover preview when tile is selected
                    if self.selected_tile and not self.placement_done:
                        if cell_r.collidepoint(mx, my):
                            # Draw translucent ghost tile preview!
                            ghost_surf = render_athangudi_tile(self.selected_tile, size=cell_sz, ghost=True)
                            self.screen.blit(ghost_surf, (cx, cy))
                            draw_rounded_rect(self.screen, (0, 0, 0, 0), cell_r, radius=8,
                                              border=2, border_color=PAL["gold"])
                            
                            # Click to place!
                            for ev in events:
                                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                                    self._place_selected_tile(r, c)
                        else:
                            # Subtle green helper border indicating valid target
                            pygame.draw.rect(self.screen, PAL["uno_green"], cell_r, 1, border_radius=8)

    def _place_selected_tile(self, r: int, c: int):
        t = self.selected_tile
        if not t: return
        self.my_floor[r][c] = t
        if self.selected_from == "hand" and t in self.my_inventory:
            self.my_inventory.remove(t)
        elif self.selected_from == "storage" and t in self.my_storage:
            self.my_storage.remove(t)
            
        self.placements_this_rd.append({"tid": t.tid, "row": r, "col": c})
        self.selected_tile = None
        self.selected_from = ""
        self.show_toast(f"Placed {t.centre} {t.motif} tile! ✓")

    # ── Storage Vault Pedestals ──────────────────────────────────────────────
    def _draw_storage_vault(self, events: List[pygame.event.Event], mx: int, my: int):
        """Draws the storage pedestal slots beside the hand tray."""
        ox, oy = 390, 435
        draw_text(self.screen, f"STORAGE VAULT ({len(self.my_storage)}/{self.my_storage_cap} SLOTS)",
                  self.fnt_sm, PAL["white"], ox, oy - 14, anchor="left")
        draw_text(self.screen, "(Discards 1 slot each round)", self.fnt_badge, PAL["text_muted"],
                  ox + 220, oy - 14, anchor="left")

        slot_sz = 68
        for i in range(self.my_storage_cap):
            sx = ox + i * (slot_sz + 12)
            sy = oy + 6
            ped_r = pygame.Rect(sx, sy, slot_sz, slot_sz)

            # Ornate pedestal slot
            draw_rounded_rect(self.screen, PAL["card_bg"], ped_r, radius=10,
                              border=2, border_color=PAL["felt_stitch"])

            if i < len(self.my_storage):
                tile = self.my_storage[i]
                is_sel = (self.selected_tile == tile)
                surf = render_athangudi_tile(tile, size=slot_sz, selected=is_sel)
                self.screen.blit(surf, (sx, sy))

                # Click to select from storage
                if not self.placement_done:
                    for ev in events:
                        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and ped_r.collidepoint(mx, my):
                            if self.selected_tile == tile:
                                self.selected_tile = None
                                self.selected_from = ""
                            else:
                                self.selected_tile = tile
                                self.selected_from = "storage"
            else:
                draw_text(self.screen, f"Slot {i+1}", self.fnt_badge, PAL["text_muted"],
                          ped_r.centerx, ped_r.centery)

    # ── Player Hand Card Tray (UNO Style Fan) ────────────────────────────────
    def _draw_player_hand_tray(self, events: List[pygame.event.Event], mx: int, my: int):
        """Draws the curved wooden card tray at the bottom with smooth tile lift animation."""
        tray_x, tray_y = 390, 560
        tray_w, tray_h = 590, 190

        # Card Tray Base with Gold Trim
        tray_r = pygame.Rect(tray_x, tray_y, tray_w, tray_h)
        draw_glow_rect(self.screen, PAL["table_wood"], tray_r, blur=8, alpha=70)
        draw_rounded_rect(self.screen, PAL["table_wood"], tray_r, radius=18,
                          border=2, border_color=PAL["table_gold"])
        
        # Inner velvet lining
        inner_r = tray_r.inflate(-12, -12)
        draw_rounded_rect(self.screen, PAL["card_bg"], inner_r, radius=14)

        # Header Pill
        header_text = f"YOUR HAND ({len(self.my_inventory)} TILES)"
        draw_text(self.screen, header_text, self.fnt_sm, PAL["gold"], tray_r.centerx, tray_y + 20)

        tile_sz = 80
        spacing = 96
        total_w = len(self.my_inventory) * spacing
        start_x = tray_r.centerx - total_w // 2 + 8

        for i, tile in enumerate(self.my_inventory):
            tx = start_x + i * spacing
            ty = tray_y + 45
            tile_r = pygame.Rect(tx, ty, tile_sz, tile_sz)
            
            is_hover = tile_r.collidepoint(mx, my) and not self.placement_done
            is_sel   = (self.selected_tile == tile)

            # UNO Mobile Card Lift: slides up 16px when hovered or selected!
            lift = -16 if (is_hover or is_sel) else 0
            draw_ty = ty + lift

            if is_hover or is_sel:
                draw_glow_rect(self.screen, PAL["gold"], pygame.Rect(tx, draw_ty, tile_sz, tile_sz),
                               blur=10, alpha=140, radius=8)

            surf = render_athangudi_tile(tile, size=tile_sz, selected=is_sel)
            self.screen.blit(surf, (tx, draw_ty))

            # Tile labels below
            draw_text(self.screen, tile.centre, self.fnt_badge, PAL["cream"], tx + tile_sz // 2, ty + tile_sz + 10)
            draw_text(self.screen, tile.motif, self.fnt_badge, PAL["text_muted"], tx + tile_sz // 2, ty + tile_sz + 24)

            # Click handler
            if not self.placement_done:
                for ev in events:
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and tile_r.move(0, lift).collidepoint(mx, my):
                        if self.selected_tile == tile:
                            self.selected_tile = None
                            self.selected_from = ""
                        else:
                            self.selected_tile = tile
                            self.selected_from = "hand"

    # ── Action Controls & Buttons ────────────────────────────────────────────
    def _draw_action_controls(self, events: List[pygame.event.Event], mx: int, my: int):
        """Draws the right-hand action dock with UNO Mobile 3D buttons."""
        can_place = len(self.placements_this_rd) >= 1 or (len(self.my_inventory) == 0 and len(self.my_storage) > 0)
        self.btn_done_placing.enabled = not self.placement_done
        self.btn_done_placing.draw(self.screen, mx, my, pulse=can_place and not self.placement_done)

        # Store Button
        can_store = (self.selected_tile is not None and
                     self.selected_from == "hand" and
                     len(self.my_storage) < self.my_storage_cap and
                     not self.placement_done)
        self.btn_store_tile.enabled = can_store
        self.btn_store_tile.draw(self.screen, mx, my)

        # Undo Button
        can_undo = len(self.placements_this_rd) > 0 and not self.placement_done
        self.btn_undo.enabled = can_undo
        self.btn_undo.draw(self.screen, mx, my)

        # Event handling
        for ev in events:
            if self.btn_done_placing.handle_event(ev):
                self._submit_placements()

            elif self.btn_store_tile.handle_event(ev):
                t = self.selected_tile
                if t and self.selected_from == "hand":
                    self.my_inventory.remove(t)
                    self.my_storage.append(t)
                    self.store_tids_this_rd.append(t.tid)
                    self.selected_tile = None
                    self.selected_from = ""
                    self.show_toast(f"Stored {t.centre} tile in vault. 📥")

            elif self.btn_undo.handle_event(ev):
                # Pick up all uncommitted placements this round
                for pm in list(self.placements_this_rd):
                    r, c, tid = pm["row"], pm["col"], pm["tid"]
                    t = self.my_floor[r][c]
                    if t:
                        self.my_floor[r][c] = None
                        self.my_inventory.append(t)
                self.placements_this_rd.clear()
                self.selected_tile = None
                self.show_toast("Undid this round's placements. ↺")

    def _submit_placements(self):
        """Finalizes tile placements and sends them to the server."""
        # Auto-place or store any remaining tiles in hand if mandatory
        for tile in list(self.my_inventory):
            if len(self.my_storage) < self.my_storage_cap:
                self.my_storage.append(tile)
                self.store_tids_this_rd.append(tile.tid)
                self.my_inventory.remove(tile)
            else:
                # Force onto first vacant floor cell
                placed = False
                for r in range(4):
                    for c in range(4):
                        if self.my_floor[r][c] is None and not placed:
                            self.my_floor[r][c] = tile
                            self.placements_this_rd.append({"tid": tile.tid, "row": r, "col": c})
                            self.my_inventory.remove(tile)
                            placed = True

        self.net.send({
            "type":       "place_tiles",
            "placements": self.placements_this_rd,
            "store_tids": self.store_tids_this_rd,
        })
        self.placement_done = True
        self.selected_tile  = None
        self.show_toast("Placements submitted! Waiting for opponents… ✓")

    # ── Top HUD ──────────────────────────────────────────────────────────────
    def _draw_top_hud(self, events: List[pygame.event.Event], mx: int, my: int):
        """Top navigation bar with room info, rules, and emotes trigger."""
        bar_r = pygame.Rect(0, 0, W, 50)
        draw_rounded_rect(self.screen, PAL["panel"], bar_r, radius=0,
                          border=1, border_color=PAL["panel_border"])

        # Lobby Pill
        pill_r = pygame.Rect(20, 10, 180, 30)
        draw_rounded_rect(self.screen, PAL["card_bg"], pill_r, radius=15)
        draw_text(self.screen, f"ROOM: {self.lobby_code}", self.fnt_sm, PAL["gold"],
                  pill_r.centerx, pill_r.centery)

        # Center Title
        draw_text(self.screen, "CHETTINAD TILES", self.fnt_lg, PAL["cream"], W // 2, 25)

        # Right buttons
        self.btn_toggle_rules.draw(self.screen, mx, my)
        self.btn_toggle_emotes.draw(self.screen, mx, my)

        for ev in events:
            if self.btn_toggle_rules.handle_event(ev):
                self.show_rules_modal = not self.show_rules_modal
                self.show_emotes_menu = False
            elif self.btn_toggle_emotes.handle_event(ev):
                self.show_emotes_menu = not self.show_emotes_menu
                self.show_rules_modal = False

    # ─────────────────────────────────────────────────────────────────────────
    # MODAL 1: UNO REACTION / EMOTES MENU
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_emotes_menu(self, events: List[pygame.event.Event], mx: int, my: int):
        menu_r = pygame.Rect(W - 250, 60, 230, 240)
        draw_glow_rect(self.screen, PAL["gold"], menu_r, blur=10, alpha=80)
        draw_rounded_rect(self.screen, PAL["panel"], menu_r, radius=14,
                          border=2, border_color=PAL["table_gold"])
        draw_text(self.screen, "QUICK REACTION", self.fnt_badge, PAL["gold"], menu_r.centerx, menu_r.y + 18)

        for i, (emoji, text) in enumerate(EMOTE_LIST):
            btn_r = pygame.Rect(menu_r.x + 12, menu_r.y + 36 + i * 32, menu_r.w - 24, 28)
            is_hover = btn_r.collidepoint(mx, my)
            draw_rounded_rect(self.screen, PAL["card_bg_hi"] if is_hover else PAL["card_bg"],
                              btn_r, radius=6)
            draw_text(self.screen, f"{emoji} {text}", self.fnt_sm,
                      PAL["white"] if not is_hover else PAL["gold"],
                      btn_r.x + 10, btn_r.centery, anchor="left")

            for ev in events:
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and btn_r.collidepoint(mx, my):
                    self.net.send({"type": "emote", "emoji": emoji, "text": text})
                    # Show on my own screen too
                    self.player_emotes[self.player_id] = {
                        "emoji": emoji, "text": text, "expiry": time.time() + 4.0
                    }
                    self.show_emotes_menu = False

    # ─────────────────────────────────────────────────────────────────────────
    # MODAL 2: OPPONENT FULL FLOOR INSPECT MODAL
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_inspect_modal(self, events: List[pygame.event.Event], mx: int, my: int):
        """Enlarged pop-up view of an opponent's 4x4 floor and scores."""
        # Dark dim backdrop
        dim_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, 160))
        self.screen.blit(dim_surf, (0, 0))

        opp = next((p for p in self.players_info if p["pid"] == self.inspect_player_pid), None)
        if not opp:
            self.inspect_player_pid = None
            return

        modal_w, modal_h = 500, 540
        modal_r = pygame.Rect(W // 2 - modal_w // 2, H // 2 - modal_h // 2, modal_w, modal_h)
        draw_glow_rect(self.screen, PAL["gold"], modal_r, blur=14, alpha=100)
        draw_rounded_rect(self.screen, PAL["panel"], modal_r, radius=16,
                          border=2, border_color=PAL["table_gold"])

        # Header
        draw_text(self.screen, f"INSPECTING: {opp['name'].upper()}", self.fnt_lg, PAL["gold"],
                  modal_r.centerx, modal_r.y + 32)
        draw_text(self.screen, f"Total Score: ⭐ {opp.get('total_score', 0)} pts", self.fnt_md, PAL["cream"],
                  modal_r.centerx, modal_r.y + 60)

        # 4x4 Floor Enlarged
        f_data = opp.get("floor")
        if f_data:
            fl = floor_from_list(f_data)
            ox = modal_r.centerx - 146
            oy = modal_r.y + 90
            csz = 68
            gap = 6
            for r in range(4):
                for c in range(4):
                    cell_r = pygame.Rect(ox + c * (csz + gap), oy + r * (csz + gap), csz, csz)
                    draw_rounded_rect(self.screen, PAL["cement_slot"], cell_r, radius=6,
                                      border=1, border_color=PAL["cement_bdr"])
                    if fl[r][c]:
                        s = render_athangudi_tile(fl[r][c], size=csz)
                        self.screen.blit(s, cell_r.topleft)

        # Close button
        btn_close = UnoButton((modal_r.centerx - 80, modal_r.bottom - 60, 160, 44),
                              "CLOSE", self.fnt_md, bg_color=PAL["uno_red"])
        btn_close.draw(self.screen, mx, my)
        for ev in events:
            if btn_close.handle_event(ev):
                self.inspect_player_pid = None

    # ─────────────────────────────────────────────────────────────────────────
    # MODAL 3: ILLUSTRATED IN-GAME RULEBOOK
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_rules_modal(self, events: List[pygame.event.Event], mx: int, my: int):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        self.screen.blit(dim, (0, 0))

        mw, mh = 780, 620
        mr = pygame.Rect(W // 2 - mw // 2, H // 2 - mh // 2, mw, mh)
        draw_glow_rect(self.screen, PAL["gold"], mr, blur=12, alpha=90)
        draw_rounded_rect(self.screen, PAL["panel"], mr, radius=16,
                          border=2, border_color=PAL["table_gold"])

        draw_text(self.screen, "CHETTINAD TILES: RULES & SCORING", self.fnt_xl, PAL["gold"], mr.centerx, mr.y + 40)

        rules = [
            ("a) Completed Motifs (+1 pt each)",
             "Formed when 4 matching corner motifs meet at a shared junction of 2×2 tiles!"),
            ("b) 3 Centrepieces in a Row (+1 pt each)",
             "3 identical centrepieces in a line (horizontal, vertical, or diagonal)."),
            ("c) 4 Centrepieces in a Row (+2 pts each)",
             "4 identical centrepieces spanning an entire row, column, or main diagonal."),
            ("d) Completed Goals (+2 pts each)",
             "Match the 3 motifs of Goal 1, 2, or 3 in a Row, Col, Diag, L-Shape, or Wrapped!"),
            ("e) Edge Half-Motifs (+1 pt each - End Game Only)",
             "Two matching corner motifs along the outer perimeter edges scored after Round 4."),
        ]

        for i, (title, desc) in enumerate(rules):
            ry = mr.y + 85 + i * 88
            card_r = pygame.Rect(mr.x + 30, ry, mr.w - 60, 74)
            draw_rounded_rect(self.screen, PAL["card_bg"], card_r, radius=10,
                              border=1, border_color=PAL["panel_border"])
            draw_text(self.screen, title, self.fnt_md, PAL["gold"], card_r.x + 16, ry + 22, anchor="left")
            draw_text(self.screen, desc, self.fnt_sm, PAL["cream"], card_r.x + 16, ry + 48, anchor="left")

        btn_close = UnoButton((mr.centerx - 80, mr.bottom - 60, 160, 44),
                              "CLOSE", self.fnt_md, bg_color=PAL["uno_green"])
        btn_close.draw(self.screen, mx, my)
        for ev in events:
            if btn_close.handle_event(ev):
                self.show_rules_modal = False

    # ─────────────────────────────────────────────────────────────────────────
    # SCREEN 4: ROUND SCORES PODIUM
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_scores_podium(self, events: List[pygame.event.Event], mx: int, my: int):
        for p in AMBIENT_PARTICLES:
            p.update(); p.draw(self.screen)

        rd_num = self.round_data.get("round", self.round)
        draw_text(self.screen, f"ROUND {rd_num} SCORING PODIUM", self.fnt_xl, PAL["gold"], W // 2, 50)

        # Leaderboard Table Card
        table_r = pygame.Rect(W // 2 - 460, 95, 920, 450)
        draw_glow_rect(self.screen, PAL["gold"], table_r, blur=10, alpha=70)
        draw_rounded_rect(self.screen, PAL["panel"], table_r, radius=16,
                          border=2, border_color=PAL["table_gold"])

        cols_x = [60, 240, 360, 470, 580, 680, 800]
        hdrs   = ["PLAYER", "a) MOTIFS", "b) 3-SEQ", "c) 4-SEQ", "d) GOALS", "e) EDGES", "TOTAL"]
        for i, h in enumerate(hdrs):
            draw_text(self.screen, h, self.fnt_badge, PAL["gold"], table_r.x + cols_x[i], table_r.y + 24, anchor="left")

        res_dict = self.round_data.get("round_results", {})
        sorted_pids = sorted(res_dict.keys(), key=lambda pid: res_dict[pid]["cumulative"], reverse=True)

        for ri, pid_str in enumerate(sorted_pids):
            bd  = res_dict[pid_str]
            pid = int(pid_str)
            p   = next((pp for pp in self.players_info if pp["pid"] == pid), {})
            y   = table_r.y + 60 + ri * 54
            
            row_r = pygame.Rect(table_r.x + 16, y - 6, table_r.w - 32, 44)
            is_me = (pid == self.player_id)
            draw_rounded_rect(self.screen, PAL["card_bg_hi"] if is_me else PAL["card_bg"],
                              row_r, radius=8, border=1 if is_me else 0,
                              border_color=PAL["gold"])

            medal = ["🥇", "🥈", "🥉"][ri] if ri < 3 else f"#{ri+1}"
            p_name_disp = f"{medal} {p.get('name', 'Artisan')}"
            vals = [p_name_disp, bd["a"], bd["b"], bd["c"], bd["d"], bd.get("e", 0), f"+{bd['total']}  (⭐ {bd['cumulative']})"]
            
            for ci, v in enumerate(vals):
                col = PAL["gold"] if is_me else PAL["white"]
                draw_text(self.screen, str(v), self.fnt_md if ci == 6 else self.fnt_sm,
                          col, table_r.x + cols_x[ci], y + 16, anchor="left")

        # Ready Button
        btn_next = UnoButton((W // 2 - 140, H - 100, 280, 54),
                             "READY FOR NEXT ROUND", self.fnt_lg,
                             bg_color=PAL["uno_green"], icon="▶")
        btn_next.draw(self.screen, mx, my, pulse=True)
        for ev in events:
            if btn_next.handle_event(ev):
                self.net.send({"type": "ready_next_round"})
                self.show_toast("Waiting for other players to click Ready… ✓")

    # ─────────────────────────────────────────────────────────────────────────
    # SCREEN 5: GAME OVER & TROPHY CEREMONY
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_game_over_screen(self, events: List[pygame.event.Event], mx: int, my: int):
        for p in AMBIENT_PARTICLES:
            p.update(); p.draw(self.screen)

        draw_text(self.screen, "CHAMPIONSHIP RESULTS", self.fnt_xl, PAL["gold"], W // 2, 70)

        winner_name = self.final_data.get("winner_name", "Master Artisan")
        draw_text(self.screen, f"🏆  {winner_name.upper()} WINS!  🏆", self.fnt_title, PAL["cream"], W // 2, 140)

        sorted_players = sorted(self.players_info, key=lambda x: x.get("total_score", 0), reverse=True)
        medals = ["🥇", "🥈", "🥉", "4th", "5th", "6th"]

        podium_r = pygame.Rect(W // 2 - 320, 210, 640, 380)
        draw_glow_rect(self.screen, PAL["gold"], podium_r, blur=12, alpha=80)
        draw_rounded_rect(self.screen, PAL["panel"], podium_r, radius=16,
                          border=2, border_color=PAL["table_gold"])

        for i, p in enumerate(sorted_players[:6]):
            py = podium_r.y + 30 + i * 56
            row_r = pygame.Rect(podium_r.x + 20, py, podium_r.w - 40, 48)
            is_me = (p["pid"] == self.player_id)
            draw_rounded_rect(self.screen, PAL["card_bg_hi"] if is_me else PAL["card_bg"],
                              row_r, radius=10, border=1 if is_me else 0, border_color=PAL["gold"])

            draw_text(self.screen, medals[i], self.fnt_lg, PAL["gold"], row_r.x + 24, row_r.centery)
            draw_text(self.screen, p["name"], self.fnt_md, PAL["white"], row_r.x + 70, row_r.centery, anchor="left")
            draw_text(self.screen, f"⭐ {p.get('total_score', 0)} Points", self.fnt_lg, PAL["gold"],
                      row_r.right - 24, row_r.centery, anchor="right")

        btn_home = UnoButton((W // 2 - 130, H - 90, 260, 52),
                             "MAIN MENU", self.fnt_lg, bg_color=PAL["uno_blue"], icon="🏠")
        btn_home.draw(self.screen, mx, my)
        for ev in events:
            if btn_home.handle_event(ev):
                self.net.disconnect()
                self.__init__()

    # ── Toast Overlay ────────────────────────────────────────────────────────
    def _draw_toast(self):
        toast_w = max(240, len(self.toast_msg) * 11 + 40)
        toast_r = pygame.Rect(W // 2 - toast_w // 2, H - 75, toast_w, 42)
        draw_glow_rect(self.screen, PAL["gold"], toast_r, blur=6, alpha=80)
        draw_rounded_rect(self.screen, (24, 20, 32), toast_r, radius=21,
                          border=2, border_color=PAL["table_gold"])
        draw_text(self.screen, self.toast_msg, self.fnt_sm, PAL["cream"],
                  toast_r.centerx, toast_r.centery)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    game_client = GameClient()
    game_client.run()
