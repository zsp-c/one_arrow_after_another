# -*- coding: utf-8 -*-
"""一箭又一箭 —— Pygame 版小游戏。

运行:  python main.py
调试:  python main.py --auto    # 不开窗口，自动把 4 关通关一遍，验证流程
       python main.py --shots   # 不开窗口，把各个界面截图存到 _shots/
"""

import ctypes
import math
import os
import random
import sys

import pygame

# Windows 控制台默认 GBK，--auto 输出的中文容易乱码，这里统一改成 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from game_logic import (
    DELTA, DIR_TO_NAME, DOWN, LEFT, RIGHT, UP,
    LevelState, find_solution,
)
from levels import LEVELS

# ---------------------------------------------------------------- 分辨率与缩放
#
# 所有布局都按 1000x700 这个"设计基准尺寸"来写，启动时再统一乘以 SCALE。
#
# 为什么要这么做：在 Windows 的 125% / 150% 显示缩放下，如果进程不是 DPI 感知的，
# 系统会先把窗口按逻辑像素渲染、再位图拉伸到物理像素贴到屏幕上，画面就会整体发虚。
# 所以启动时先声明 DPI 感知，再按显示器真实可用空间挑一个倍率把界面整体放大，
# 这样每个像素都是 1:1 映射到物理像素，文字和箭头边缘才是锐利的。

BASE_W, BASE_H = 1000, 700
BASE_MARGIN = 26
BASE_PANEL_W = 286
BASE_HEADER_H = 72
BASE_CARD_W, BASE_CARD_H = 480, 320
BASE_CARD_CY = 344
FPS = 60

SCALE = 1.0
WIDTH, HEIGHT = BASE_W, BASE_H
MARGIN, PANEL_W, HEADER_H = BASE_MARGIN, BASE_PANEL_W, BASE_HEADER_H
CARD_W, CARD_H = BASE_CARD_W, BASE_CARD_H
BOARD_COL = HEADER_RECT = BOARD_AREA = PANEL_RECT = CARD_RECT = pygame.Rect(0, 0, 1, 1)


def px(value):
    """把设计基准尺寸换算成当前缩放倍率下的像素值。"""
    return int(round(value * SCALE))


def enable_high_dpi():
    """声明进程 DPI 感知。必须在 pygame.init() 之前调用，否则窗口会被系统拉伸而发虚。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # PER_MONITOR_AWARE_V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def screen_work_area():
    """显示器可用区域（物理像素，已扣掉任务栏）。"""
    if sys.platform == "win32":
        try:
            from ctypes import wintypes
            rect = wintypes.RECT()
            SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                w, h = rect.right - rect.left, rect.bottom - rect.top
                if w >= 800 and h >= 600:
                    return w, h
        except Exception:
            pass
    try:
        w, h = pygame.display.get_desktop_sizes()[0]
        if w >= 800 and h >= 600:
            return int(w * 0.94), int(h * 0.88)
    except Exception:
        pass
    return BASE_W, BASE_H


def compute_scale(explicit=None):
    """挑一个缩放倍率：窗口尽量大，但必须放得进屏幕（还要留出标题栏）。"""
    if explicit:
        return max(0.8, min(float(explicit), 3.0))
    work_w, work_h = screen_work_area()
    scale = min((work_w - 20) / float(BASE_W), (work_h - 48) / float(BASE_H))
    scale = math.floor(scale * 20) / 20.0        # 取到 0.05 的整数倍，倍率好看一点
    return max(0.8, min(scale, 2.0))


def init_ui(scale):
    """按缩放倍率算出全部布局常量。"""
    global SCALE, WIDTH, HEIGHT, MARGIN, PANEL_W, HEADER_H
    global CARD_W, CARD_H, BOARD_COL, HEADER_RECT, BOARD_AREA, PANEL_RECT, CARD_RECT

    SCALE = scale
    WIDTH, HEIGHT = px(BASE_W), px(BASE_H)
    MARGIN, PANEL_W, HEADER_H = px(BASE_MARGIN), px(BASE_PANEL_W), px(BASE_HEADER_H)

    BOARD_COL = pygame.Rect(MARGIN, MARGIN,
                            WIDTH - PANEL_W - MARGIN * 3, HEIGHT - MARGIN * 2)
    HEADER_RECT = pygame.Rect(BOARD_COL.x, BOARD_COL.y, BOARD_COL.w, HEADER_H)
    BOARD_AREA = pygame.Rect(BOARD_COL.x, BOARD_COL.y + HEADER_H,
                             BOARD_COL.w, BOARD_COL.h - HEADER_H)
    PANEL_RECT = pygame.Rect(BOARD_COL.right + MARGIN, MARGIN, PANEL_W, BOARD_COL.h)

    CARD_W, CARD_H = px(BASE_CARD_W), px(BASE_CARD_H)
    CARD_RECT = pygame.Rect(0, 0, CARD_W, CARD_H)
    CARD_RECT.center = (WIDTH // 2, px(BASE_CARD_CY))

# ---------------------------------------------------------------- 配色

BG = (22, 24, 32)
BOARD_COL_BG = (30, 33, 44)
CELL = (43, 47, 62)
CELL_EDGE = (56, 61, 80)
CELL_HOVER = (58, 64, 84)
PANEL_BG = (33, 36, 47)
PANEL_EDGE = (52, 57, 74)
TEXT = (232, 236, 246)
TEXT_DIM = (146, 155, 175)
TEXT_FAINT = (100, 108, 128)
ACCENT = (86, 156, 255)
ACCENT_HOVER = (116, 178, 255)
GREEN = (104, 214, 138)
RED = (245, 92, 92)
RED_DIM = (150, 62, 62)
GOLD = (255, 202, 87)
SHADOW = (12, 13, 18)

DIR_COLOR = {
    UP: (92, 196, 255),
    DOWN: (255, 146, 92),
    LEFT: (128, 218, 148),
    RIGHT: (188, 152, 255),
}
DIR_COLOR_DARK = {
    UP: (44, 104, 150),
    DOWN: (146, 78, 44),
    LEFT: (62, 118, 74),
    RIGHT: (98, 76, 150),
}

# ---------------------------------------------------------------- 字体

_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"),
    (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simhei.ttf"),
    (r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simsun.ttc"),
    (r"C:\Windows\Fonts\Deng.ttf", r"C:\Windows\Fonts\Dengb.ttf"),
    ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
     "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
]
_FONT_CACHE = {}


def _pick_font_file(bold):
    for regular, bold_file in _FONT_CANDIDATES:
        path = bold_file if bold else regular
        if os.path.exists(path):
            return path
    return None


def get_font(size, bold=False):
    """取一个支持中文的字体；找不到中文字体时退回系统默认字体。

    size 传的是设计基准字号，这里统一乘上 SCALE —— 所有文字因此自动跟随缩放。
    """
    key = (size, bold)
    font = _FONT_CACHE.get(key)
    if font is not None:
        return font

    pixel_size = px(size)
    path = _pick_font_file(bold)
    if path:
        font = pygame.font.Font(path, pixel_size)
        if bold and os.path.basename(path).lower() in ("msyh.ttc", "simsun.ttc", "deng.ttf"):
            font.set_bold(True)          # 该文件本身没有粗体，用合成粗体
    else:
        font = pygame.font.SysFont("microsoftyahei,simhei,simsun,arial",
                                   pixel_size, bold=bold)

    _FONT_CACHE[key] = font
    return font


def draw_text(surface, text, size, color, pos, anchor="topleft", bold=False, alpha=255):
    image = get_font(size, bold).render(text, True, color)
    if alpha < 255:
        image.set_alpha(alpha)
    rect = image.get_rect(**{anchor: pos})
    surface.blit(image, rect)
    return rect


def text_width(text, size, bold=False):
    return get_font(size, bold).size(text)[0]


# ---------------------------------------------------------------- 绘图小工具

try:
    import pygame.gfxdraw as _gfx
except Exception:                                    # pragma: no cover
    _gfx = None


def _fill_poly(surface, points, color):
    """填充多边形；有 gfxdraw 时用抗锯齿版本，边缘更干净。"""
    if _gfx is not None and len(color) == 3:
        ipts = [(int(round(x)), int(round(y))) for x, y in points]
        try:
            _gfx.filled_polygon(surface, ipts, color)
            _gfx.aapolygon(surface, ipts, color)
            return
        except Exception:
            pass
    pygame.draw.polygon(surface, color, points)


def _stroke_poly(surface, points, color, width=2):
    pygame.draw.polygon(surface, color, points, width)


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def ease_out(t):
    return 1.0 - (1.0 - max(0.0, min(1.0, t))) ** 3


def arrow_points(cx, cy, length, direction):
    """返回一支指向 direction 的箭头多边形顶点（默认形状朝右，再旋转）。"""
    half = length / 2.0
    head = length * 0.40
    head_half = length * 0.34
    shaft_half = length * 0.145
    local = [
        (half, 0.0),
        (half - head, -head_half),
        (half - head, -shaft_half),
        (-half, -shaft_half),
        (-half, shaft_half),
        (half - head, shaft_half),
        (half - head, head_half),
    ]
    points = []
    for x, y in local:
        if direction == RIGHT:
            px, py = x, y
        elif direction == DOWN:                 # 屏幕坐标顺时针旋转 90°
            px, py = -y, x
        elif direction == LEFT:
            px, py = -x, -y
        else:                                   # UP
            px, py = y, -x
        points.append((cx + px, cy + py))
    return points


def draw_arrow(surface, cx, cy, length, direction, color, alpha=255, outline=None):
    points = arrow_points(cx, cy, length, direction)
    edge = max(1, px(2))
    if alpha >= 255:
        _fill_poly(surface, points, color)
        if outline:
            _stroke_poly(surface, points, outline, edge)
        return

    margin = edge + 2
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    w = int(max(xs) - min(xs)) + margin * 2
    h = int(max(ys) - min(ys)) + margin * 2
    temp = pygame.Surface((w, h), pygame.SRCALPHA)
    local = [(x - min(xs) + margin, y - min(ys) + margin) for x, y in points]
    _fill_poly(temp, local, color + (alpha,))
    if outline:
        _stroke_poly(temp, local, outline + (alpha,), edge)
    surface.blit(temp, (min(xs) - margin, min(ys) - margin))


# ---------------------------------------------------------------- 棋盘视图

class BoardView:
    """负责网格坐标 <-> 屏幕像素坐标的换算。"""

    def __init__(self, area, rows, cols):
        self.rows, self.cols = rows, cols
        self.cell = max(36, min(area.w // cols, area.h // rows))
        w, h = self.cell * cols, self.cell * rows
        self.rect = pygame.Rect(area.x + (area.w - w) // 2,
                                area.y + (area.h - h) // 2, w, h)
        self.pad = max(4, self.cell // 12)
        self.arrow_len = self.cell * 0.60

    def cell_rect(self, r, c):
        return pygame.Rect(self.rect.x + c * self.cell + self.pad,
                           self.rect.y + r * self.cell + self.pad,
                           self.cell - 2 * self.pad, self.cell - 2 * self.pad)

    def center(self, pos):
        return self.cell_rect(pos[0], pos[1]).center

    def cell_at(self, point):
        if not self.rect.collidepoint(point):
            return None
        c = (point[0] - self.rect.x) // self.cell
        r = (point[1] - self.rect.y) // self.cell
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return (r, c)
        return None

    def exit_point(self, pos, direction):
        """箭头飞出棋盘时的终点（棋盘外一点）。"""
        cx, cy = self.center(pos)
        margin = self.cell * 1.25
        if direction == RIGHT:
            return (self.rect.right + margin, cy)
        if direction == LEFT:
            return (self.rect.left - margin, cy)
        if direction == UP:
            return (cx, self.rect.top - margin)
        return (cx, self.rect.bottom + margin)


# ---------------------------------------------------------------- 动画

class Animation:
    def __init__(self, duration):
        self.t = 0.0
        self.duration = float(duration)
        self.done = False

    @property
    def progress(self):
        return min(1.0, self.t / self.duration) if self.duration > 0 else 1.0

    def update(self, dt):
        self.t += dt
        if self.t >= self.duration:
            self.done = True

    def draw(self, surface):
        raise NotImplementedError


class FlyOutAnim(Animation):
    """箭头飞出棋盘的动画：加速飞走 + 拖尾 + 淡出。"""

    def __init__(self, view, pos, direction, color, duration=0.42):
        super().__init__(duration)
        self.view = view
        self.start = view.center(pos)
        self.target = view.exit_point(pos, direction)
        self.direction = direction
        self.color = color

    def _at(self, eased):
        return (self.start[0] + (self.target[0] - self.start[0]) * eased,
                self.start[1] + (self.target[1] - self.start[1]) * eased)

    def draw(self, surface):
        u = self.progress
        eased = u * u                                   # 越飞越快
        alpha = 255 if u < 0.55 else int(255 * (1.0 - (u - 0.55) / 0.45))
        length = self.view.arrow_len
        outline = DIR_COLOR_DARK[self.direction]

        for k, ghost_alpha in ((3, 26), (2, 48), (1, 78)):
            gx, gy = self._at(max(0.0, eased - 0.05 * k))
            draw_arrow(surface, gx, gy, length, self.direction,
                       self.color, alpha=min(ghost_alpha, alpha))

        x, y = self._at(eased)
        draw_arrow(surface, x, y, length, self.direction, self.color,
                   alpha=alpha, outline=outline if alpha > 200 else None)


class ShakeAnim(Animation):
    """箭头撞到别的箭头：朝前顶一下再弹回来，同时闪红。"""

    def __init__(self, view, pos, direction, color, duration=0.42):
        super().__init__(duration)
        self.view = view
        self.pos = pos
        self.base = view.center(pos)
        self.direction = direction
        self.color = color

    def draw(self, surface):
        u = self.progress
        bump = math.sin(math.pi * u)                    # 先冲出去再退回来
        offset = self.view.cell * 0.26 * bump
        dr, dc = DELTA[self.direction]
        cx = self.base[0] + dc * offset
        cy = self.base[1] + dr * offset
        color = lerp_color(self.color, RED, bump)
        draw_arrow(surface, cx, cy, self.view.arrow_len, self.direction,
                   color, outline=(255, 255, 255) if bump > 0.5 else (60, 20, 20))


class BlockerHighlight(Animation):
    """把挡住去路的那支箭头框出来，让玩家知道是谁挡的。"""

    def __init__(self, view, pos, duration=0.85):
        super().__init__(duration)
        self.view = view
        self.pos = pos

    def draw(self, surface):
        u = self.progress
        pulse = 0.5 - 0.5 * math.cos(u * math.pi * 4)    # 闪两下
        grow = px(6 * pulse) + px(4)
        rect = self.view.cell_rect(*self.pos).inflate(grow, grow)
        color = lerp_color((120, 92, 30), GOLD, pulse)
        pygame.draw.rect(surface, color, rect, width=max(2, px(4)),
                         border_radius=px(14))


class HintPulse(Animation):
    """提示：把一支可以点掉的箭头用脉冲圆环圈出来，并画出它的前进路线。

    这个动画**不锁输入**（busy() 只认飞出和撞击），玩家可以立刻照着点。
    """

    def __init__(self, view, pos, cells, duration=3.0):
        super().__init__(duration)
        self.view = view
        self.pos = pos
        self.cells = cells

    def draw(self, surface):
        u = self.progress
        alpha = 255 if u < 0.75 else int(255 * (1.0 - (u - 0.75) / 0.25))
        if alpha <= 0:
            return

        # 顺带把这条路画成绿点，让玩家看清"为什么它能飞出去"
        radius = max(px(5), int(self.view.cell * 0.11))
        for cell in self.cells:
            pygame.draw.circle(surface, GREEN, self.view.cell_rect(*cell).center, radius)

        pulse = 0.5 - 0.5 * math.cos(self.t * 7.0)
        rect = self.view.cell_rect(*self.pos).inflate(px(10) + px(10) * pulse,
                                                      px(10) + px(10) * pulse)
        layer = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        color = lerp_color(GREEN, (240, 255, 245), pulse * 0.7)
        pygame.draw.rect(layer, color + (alpha,), layer.get_rect(),
                         width=max(2, px(4)), border_radius=px(16))
        surface.blit(layer, rect.topleft)


class FloatText(Animation):
    """一边飘一边淡出的提示文字。

    rise 是飘动的位移（负数表示向下飘）：靠近棋盘上边缘的格子要把字放到下方，
    否则文字会飘出棋盘、压到顶部的关卡标题上。
    """

    def __init__(self, text, center, color, duration=0.9, size=26, rise=None):
        super().__init__(duration)
        self.text = text
        self.center = center
        self.color = color
        self.size = size
        self.rise = px(54) if rise is None else rise

    def draw(self, surface):
        u = self.progress
        alpha = int(255 * (1.0 - u * u))
        if alpha <= 0:
            return
        image = get_font(self.size, True).render(self.text, True, self.color)
        image.set_alpha(alpha)
        rect = image.get_rect(center=(self.center[0],
                                      self.center[1] - self.rise * ease_out(u)))
        # 垫一层半透明底色，压在其他箭头上时也能看清
        pad_x, pad_y = px(10), px(5)
        back = pygame.Surface((rect.w + pad_x * 2, rect.h + pad_y * 2), pygame.SRCALPHA)
        pygame.draw.rect(back, (12, 14, 20, int(185 * alpha / 255.0)),
                         back.get_rect(), border_radius=px(8))
        surface.blit(back, (rect.x - pad_x, rect.y - pad_y))
        surface.blit(image, rect)


class SparkBurst(Animation):
    """箭头飞出时朝前方溅开的小火花。"""

    def __init__(self, view, pos, direction, color, duration=0.45):
        super().__init__(duration)
        cx, cy = view.center(pos)
        dr, dc = DELTA[direction]
        angle = math.atan2(dr, dc)
        self.color = color
        self.base_radius = max(2.0, view.cell * 0.055)
        self.parts = []
        for _ in range(16):
            a = angle + random.uniform(-0.7, 0.7)
            speed = random.uniform(0.4, 1.15) * view.cell * 3.0
            self.parts.append((cx, cy, math.cos(a) * speed, math.sin(a) * speed,
                               random.uniform(0.5, 1.0)))

    def draw(self, surface):
        u = self.progress
        color = lerp_color(self.color, BG, u)
        for x, y, vx, vy, scale in self.parts:
            radius = max(1, int(self.base_radius * scale * (1.0 - u)))
            pygame.draw.circle(surface, color, (int(x + vx * u), int(y + vy * u)), radius)


# ---------------------------------------------------------------- 按钮

class Button:
    def __init__(self, rect, label, callback, size=22, style="primary", enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.size = size
        self.style = style
        self.enabled = enabled
        self.hover = False
        self.armed = False

    def _colors(self):
        if self.style == "primary":
            base, edge, text = ACCENT, ACCENT_HOVER, (255, 255, 255)
        elif self.style == "ghost":
            base, edge, text = (44, 49, 63), (72, 79, 98), TEXT
        elif self.style == "danger":
            base, edge, text = (86, 42, 46), RED, (255, 220, 220)
        else:
            base, edge, text = CELL, CELL_EDGE, TEXT
        if not self.enabled:
            return base, edge, TEXT_FAINT
        if self.hover:
            base = lerp_color(base, (255, 255, 255), 0.14)
        return base, edge, text

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.armed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_armed = self.armed
            self.armed = False
            if was_armed and self.rect.collidepoint(event.pos):
                self.callback()
                return True
        return False

    def update(self, mouse_pos):
        self.hover = self.enabled and self.rect.collidepoint(mouse_pos)

    def draw(self, surface):
        base, edge, text = self._colors()
        rect = self.rect.copy()
        if self.armed and self.hover:
            rect.y += px(2)
        pygame.draw.rect(surface, base, rect, border_radius=px(12))
        pygame.draw.rect(surface, edge, rect, width=max(1, px(2)), border_radius=px(12))
        label = self.label() if callable(self.label) else self.label
        draw_text(surface, label, self.size, text, rect.center, anchor="center", bold=True)


# ---------------------------------------------------------------- 游戏状态

STATE_START = "start"
STATE_PLAY = "play"
STATE_WIN = "win"
STATE_OVER = "over"

class Game:
    def __init__(self):
        self.screen = pygame.display.get_surface()
        self.state = STATE_START
        self.level = None
        self.view = None
        self.anims = []
        self.buttons = []
        self.hint_button = None
        self.hover_pos = None
        self.pending = None            # "win" / "over"，等动画放完再切界面
        self.overlay_t = 0.0
        self.time = 0.0
        self.stars = [(random.uniform(0, WIDTH), random.uniform(0, HEIGHT),
                       random.uniform(0.4, 1.4), random.uniform(0.15, 0.5))
                      for _ in range(70)]
        self.build_buttons()

    # -------------------------------------------------- 状态切换

    def build_buttons(self):
        self.buttons = []
        self.hint_button = None
        cx = WIDTH // 2
        if self.state == STATE_START:
            self.buttons.append(Button((cx - px(110), px(386), px(220), px(56)),
                                       "开始游戏", self.start_from_scratch, size=26))
            total = len(LEVELS)
            gap, bw = px(12), px(104)
            x0 = cx - (total * bw + (total - 1) * gap) // 2
            for i in range(total):
                self.buttons.append(Button((x0 + i * (bw + gap), px(470), bw, px(46)),
                                           "第 %d 关" % (i + 1),
                                           lambda idx=i: self.start_level(idx),
                                           size=19, style="ghost"))
        elif self.state == STATE_PLAY:
            x, w = PANEL_RECT.x + px(22), PANEL_W - px(44)
            self.hint_button = Button((x, PANEL_RECT.bottom - px(214), w, px(48)),
                                      self.hint_label, self.use_hint, size=20)
            self.buttons.append(self.hint_button)
            self.buttons.append(Button((x, PANEL_RECT.bottom - px(156), w, px(48)),
                                       "重新开始本关", self.restart_level, size=20,
                                       style="ghost"))
            self.buttons.append(Button((x, PANEL_RECT.bottom - px(98), w, px(48)),
                                       "返回主菜单", self.go_menu, size=20, style="ghost"))
        elif self.state == STATE_WIN:
            last = self.level.index >= len(LEVELS) - 1
            label = "回到主菜单" if last else "进入下一关"
            callback = self.go_menu if last else self.next_level
            by = CARD_RECT.bottom - px(70)
            self.buttons.append(Button((cx - px(190), by, px(190), px(52)),
                                       label, callback, size=21))
            self.buttons.append(Button((cx + px(10), by, px(180), px(52)), "重玩本关",
                                       self.restart_level, size=21, style="ghost"))
        elif self.state == STATE_OVER:
            by = CARD_RECT.bottom - px(70)
            self.buttons.append(Button((cx - px(190), by, px(190), px(52)),
                                       "重新开始本关", self.restart_level, size=21))
            self.buttons.append(Button((cx + px(10), by, px(180), px(52)), "返回主菜单",
                                       self.go_menu, size=21, style="ghost"))

    def set_state(self, state):
        if self.state == state:
            return
        self.state = state
        self.overlay_t = 0.0
        self.build_buttons()

    def start_from_scratch(self):
        self.start_level(0)

    def start_level(self, index):
        self.level = LevelState(index)
        self.view = BoardView(BOARD_AREA, self.level.rows, self.level.cols)
        self.anims = []
        self.hover_pos = None
        self.pending = None
        self.set_state(STATE_PLAY)

    def restart_level(self):
        if self.level is None:
            self.go_menu()
            return
        self.level.reset()
        self.anims = []
        self.hover_pos = None
        self.pending = None
        self.set_state(STATE_PLAY)

    def next_level(self):
        self.start_level(min(self.level.index + 1, len(LEVELS) - 1))

    def go_menu(self):
        self.anims = []
        self.pending = None
        self.set_state(STATE_START)

    # -------------------------------------------------- 输入

    def busy(self):
        """有会挡住输入的动画在放（飞出 / 撞击），此时不接受点击。"""
        return any(isinstance(a, (FlyOutAnim, ShakeAnim)) for a in self.anims)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == STATE_PLAY:
                    self.go_menu()
                elif self.state in (STATE_WIN, STATE_OVER):
                    self.go_menu()
                return
            if event.key == pygame.K_r:
                if self.state in (STATE_PLAY, STATE_WIN, STATE_OVER):
                    self.restart_level()
                return
            if event.key == pygame.K_h:
                self.use_hint()
                return
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                if self.state == STATE_START:
                    self.start_from_scratch()
                elif self.state == STATE_WIN:
                    self.next_level() if self.level.index < len(LEVELS) - 1 else self.go_menu()
                elif self.state == STATE_OVER:
                    self.restart_level()
                return

        for button in self.buttons:
            if button.handle_event(event):
                return

        if self.state == STATE_PLAY:
            if event.type == pygame.MOUSEMOTION:
                self.hover_pos = self.view.cell_at(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cell = self.view.cell_at(event.pos)
                if cell is not None:
                    self.click_cell(cell)

    def make_float_text(self, text, cell, color, size=24):
        """在某个格子旁边生成飘字；格子太靠上就把字改放到下方，避免飘出棋盘。"""
        rect = self.view.cell_rect(*cell)
        above = rect.top - px(46) >= BOARD_AREA.top
        y = rect.top - px(34) if above else rect.bottom + px(34)
        return FloatText(text, (rect.centerx, y), color, size=size,
                         rise=px(30) if above else -px(30))

    def hint_label(self):
        if self.level is None:
            return "自动提示"
        if self.level.hints_left <= 0:
            return "自动提示（已用完）"
        return "自动提示（剩 %d 次）" % self.level.hints_left

    def use_hint(self):
        """花一次提示机会：自动找出一支能飞出棋盘的箭头，并直接替玩家点掉它。

        因为选中的箭头一定是"前方畅通"的，这一步不会消耗失误次数。
        """
        if self.state != STATE_PLAY or self.level is None:
            return
        if self.busy() or self.pending is not None:
            return

        pos = self.level.use_hint()
        if pos is None:
            return

        path = self.level.path_of(pos)
        self.click_cell(pos)                 # 自动点掉，走的是和手动点击完全相同的那条路径

        if pos in self.level.arrows:         # 兜底：万一没点掉，把这次机会还回去
            self.level.hints_left += 1
            return

        # 圈出刚刚自动飞掉的那一支，并把它畅通的路线画出来解释原因。
        # 插到列表最前面，让它画在飞出动画的下层，不挡住箭头。
        self.anims.insert(0, HintPulse(self.view, pos, path, duration=1.1))
        self.anims.append(self.make_float_text("提示：这一支能飞出", pos, GREEN, size=22))

    def click_cell(self, cell):
        if self.busy() or self.pending is not None or self.level is None:
            return
        if self.state != STATE_PLAY:
            return

        result = self.level.click(cell)
        if result.kind == "empty":
            return

        # 棋盘一变动，之前圈出来的提示标记就作废了
        self.anims = [a for a in self.anims if not isinstance(a, HintPulse)]

        if result.kind == "out":
            color = DIR_COLOR[result.direction]
            self.anims.append(FlyOutAnim(self.view, result.pos, result.direction, color))
            self.anims.append(SparkBurst(self.view, result.pos, result.direction, color))
            if self.level.is_cleared:
                self.pending = "win"
        else:
            color = DIR_COLOR[result.direction]
            self.anims.append(ShakeAnim(self.view, result.pos, result.direction, color))
            self.anims.append(BlockerHighlight(self.view, result.blocker))
            self.anims.append(self.make_float_text("被挡住了！", result.pos, RED, size=24))
            if self.level.is_failed:
                self.pending = "over"

    # -------------------------------------------------- 更新

    def update(self, dt):
        self.time += dt
        if self.state in (STATE_WIN, STATE_OVER):
            self.overlay_t = min(1.0, self.overlay_t + dt / 0.26)
        else:
            self.overlay_t = 0.0

        for anim in self.anims:
            anim.update(dt)
        self.anims = [a for a in self.anims if not a.done]

        if self.pending is not None and not self.busy():
            target = STATE_WIN if self.pending == "win" else STATE_OVER
            self.pending = None
            self.set_state(target)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.update(mouse_pos)
        # 提示按钮：没有次数、或者动画正在播放时置灰
        if self.state == STATE_PLAY and self.hint_button is not None:
            self.hint_button.enabled = (self.level.hints_left > 0
                                        and not self.busy()
                                        and self.pending is None)

        if self.state == STATE_PLAY and self.view is not None:
            if self.busy():
                self.hover_pos = None

    # -------------------------------------------------- 绘制

    def draw(self):
        self.screen.fill(BG)
        if self.state == STATE_START:
            self.draw_start()
        else:
            self.draw_play_screen()
            if self.state == STATE_WIN:
                self.draw_result_card(win=True)
            elif self.state == STATE_OVER:
                self.draw_result_card(win=False)

        for button in self.buttons:
            button.draw(self.screen)

    # -------- 开始界面

    def draw_start(self):
        for x, y, r, a in self.stars:
            tw = 0.5 + 0.5 * math.sin(self.time * 1.5 + x)
            color = lerp_color(BG, (150, 180, 255), a * tw)
            pygame.draw.circle(self.screen, color, (int(x), int(y)),
                               max(1, px(r)))

        draw_text(self.screen, "一 箭 又 一 箭", 68, TEXT, (WIDTH // 2, px(150)),
                  anchor="center", bold=True)
        draw_text(self.screen, "点掉挡路的，放走能走的", 22, TEXT_DIM,
                  (WIDTH // 2, px(214)), anchor="center")

        # 演示用的一排箭头
        demo = [RIGHT, UP, DOWN, LEFT]
        for i, direction in enumerate(demo):
            cx = WIDTH // 2 - px(132) + i * px(88)
            bob = math.sin(self.time * 2.0 + i * 0.8) * px(6)
            draw_arrow(self.screen, cx, px(306) + bob, px(54), direction,
                       DIR_COLOR[direction], outline=DIR_COLOR_DARK[direction])

        rules = [
            "点击箭头：前方同一直线上没有别的箭头，它就飞出棋盘",
            "前方被挡住：箭头会被弹回来，并消耗一次失误机会",
            "失误用完就闯关失败；清空全部箭头即可进入下一关",
            "卡住了就点「自动提示」（每关 2 次），直接帮你飞掉一支能走的",
        ]
        for i, line in enumerate(rules):
            draw_text(self.screen, line, 19, TEXT_DIM, (WIDTH // 2, px(548) + i * px(30)),
                      anchor="center")

    # -------- 游戏界面

    def draw_play_screen(self):
        draw_text(self.screen, "一箭又一箭", 30, TEXT, (HEADER_RECT.x + px(4), HEADER_RECT.y),
                  bold=True)
        subtitle = "第 %d 关 / 共 %d 关" % (self.level.index + 1, len(LEVELS))
        draw_text(self.screen, subtitle, 20, TEXT_DIM,
                  (HEADER_RECT.x + px(4), HEADER_RECT.y + px(42)))
        name_w = text_width(self.level.name, 22, bold=True)
        draw_text(self.screen, self.level.name, 22, ACCENT,
                  (HEADER_RECT.right - name_w - px(4), HEADER_RECT.y + px(40)), bold=True)

        pygame.draw.rect(self.screen, BOARD_COL_BG, BOARD_AREA, border_radius=px(20))

        self.draw_cells()
        self.draw_hover()
        self.draw_path_preview()
        self.draw_arrows()
        for anim in self.anims:
            anim.draw(self.screen)
        self.draw_panel()

    def draw_cells(self):
        radius = max(px(6), self.view.cell // 8)
        for r in range(self.level.rows):
            for c in range(self.level.cols):
                rect = self.view.cell_rect(r, c)
                pygame.draw.rect(self.screen, CELL, rect, border_radius=radius)
                pygame.draw.rect(self.screen, CELL_EDGE, rect,
                                 width=max(1, px(1)), border_radius=radius)

    def draw_arrows(self):
        shaking = {a.pos for a in self.anims if isinstance(a, ShakeAnim)}
        length = self.view.arrow_len
        for (r, c), direction in self.level.arrows.items():
            if (r, c) in shaking:
                continue
            cx, cy = self.view.center((r, c))
            draw_arrow(self.screen, cx, cy, length, direction,
                       DIR_COLOR[direction], outline=DIR_COLOR_DARK[direction])

    def draw_hover(self):
        if self.state != STATE_PLAY or self.hover_pos is None:
            return
        if self.hover_pos not in self.level.arrows:
            return
        rect = self.view.cell_rect(*self.hover_pos).inflate(px(4), px(4))
        pygame.draw.rect(self.screen, CELL_HOVER, rect, border_radius=px(14))
        pygame.draw.rect(self.screen, (120, 136, 170), rect,
                         width=max(1, px(2)), border_radius=px(14))

    def draw_path_preview(self):
        """鼠标悬停时，把这一箭的前进路线画出来：能飞绿色，被挡红色。"""
        if self.state != STATE_PLAY or self.hover_pos is None or self.busy():
            return
        pos = self.hover_pos
        direction = self.level.arrows.get(pos)
        if direction is None:
            return

        blocker = self.level.blocker_of(pos)
        cells = self.level.path_of(pos)
        radius = max(px(5), int(self.view.cell * 0.11))
        reached_blocker = False

        for cell in cells:
            rect = self.view.cell_rect(*cell)
            if blocker is None:
                color = GREEN
            elif cell == blocker:
                color = RED
                reached_blocker = True
            elif reached_blocker:
                color = lerp_color(CELL, (120, 128, 148), 0.55)  # 被挡住之后的格子无关紧要
            else:
                color = GOLD
            pygame.draw.circle(self.screen, color, rect.center, radius)
            pygame.draw.circle(self.screen, lerp_color(color, (255, 255, 255), 0.45),
                               rect.center, radius, max(1, px(2)))

        if blocker is not None:
            rect = self.view.cell_rect(*blocker).inflate(px(2), px(2))
            pygame.draw.rect(self.screen, RED_DIM, rect,
                             width=max(2, px(3)), border_radius=px(14))
        else:
            self.draw_exit_marker(pos, direction)

    def draw_exit_marker(self, pos, direction):
        """前方畅通时，在棋盘对应边上画一条绿色出口。"""
        cell_rect = self.view.cell_rect(*pos)
        board = self.view.rect
        thickness = max(3, px(6))
        inset = px(2)
        if direction == RIGHT:
            rect = pygame.Rect(board.right - thickness - inset, cell_rect.top,
                               thickness, cell_rect.height)
        elif direction == LEFT:
            rect = pygame.Rect(board.left + inset, cell_rect.top,
                               thickness, cell_rect.height)
        elif direction == UP:
            rect = pygame.Rect(cell_rect.left, board.top + inset,
                               cell_rect.width, thickness)
        else:
            rect = pygame.Rect(cell_rect.left, board.bottom - thickness - inset,
                               cell_rect.width, thickness)
        pygame.draw.rect(self.screen, GREEN, rect, border_radius=px(3))

    def draw_panel(self):
        pygame.draw.rect(self.screen, PANEL_BG, PANEL_RECT, border_radius=px(20))
        pygame.draw.rect(self.screen, PANEL_EDGE, PANEL_RECT,
                         width=max(1, px(2)), border_radius=px(20))

        x = PANEL_RECT.x + px(22)
        w = PANEL_W - px(44)
        y = PANEL_RECT.y + px(22)

        def label(text, yy):
            draw_text(self.screen, text, 18, TEXT_FAINT, (x, yy))

        def divider(yy):
            pygame.draw.line(self.screen, PANEL_EDGE, (x, yy), (x + w, yy), max(1, px(1)))

        label("剩余箭头", y)
        draw_text(self.screen, str(self.level.remaining), 40, TEXT, (x + w, y - px(8)),
                  anchor="topright", bold=True)
        y += px(52)

        label("本关箭头总数", y)
        draw_text(self.screen, "%d 支 · 已飞出 %d 支" % (self.level.total, self.level.cleared),
                  18, TEXT_DIM, (x, y + px(22)))
        y += px(54)
        divider(y)
        y += px(18)

        label("剩余失误", y)
        y += px(30)
        max_mistakes = self.level.max_mistakes
        left = self.level.mistakes_left
        dot_r = px(13)
        for i in range(max_mistakes):
            cx = x + dot_r + i * (dot_r * 2 + px(12))
            cy = y + dot_r
            if i < left:
                pygame.draw.circle(self.screen, RED, (cx, cy), dot_r)
                pygame.draw.circle(self.screen, (255, 170, 170), (cx, cy), dot_r,
                                   max(1, px(2)))
            else:
                pygame.draw.circle(self.screen, (70, 74, 90), (cx, cy), dot_r,
                                   max(1, px(2)))
        draw_text(self.screen, "%d / %d" % (left, max_mistakes), 26, TEXT,
                  (x + w, y - px(2)), anchor="topright", bold=True)
        y += dot_r * 2 + px(16)

        label("已失误次数", y)
        draw_text(self.screen, "%d 次" % self.level.mistakes_used, 18, TEXT_DIM,
                  (x + w, y), anchor="topright")
        y += px(30)
        divider(y)
        y += px(18)

        label("本关提示", y)
        y += px(26)
        for line in wrap_text(self.level.tip, 18, w):
            draw_text(self.screen, line, 18, TEXT_DIM, (x, y))
            y += px(26)

        # 清空进度条
        bar_y = PANEL_RECT.bottom - px(256)
        label("清空进度", bar_y - px(28))
        draw_text(self.screen, "%d / %d" % (self.level.cleared, self.level.total), 18,
                  TEXT_DIM, (x + w, bar_y - px(28)), anchor="topright")
        bar = pygame.Rect(x, bar_y, w, px(12))
        pygame.draw.rect(self.screen, (26, 28, 38), bar, border_radius=px(6))
        done = self.level.cleared / float(self.level.total)
        if done > 0:
            fill = pygame.Rect(bar.x, bar.y, max(px(12), int(bar.w * done)), bar.h)
            pygame.draw.rect(self.screen, GREEN, fill, border_radius=px(6))
        pygame.draw.rect(self.screen, PANEL_EDGE, bar,
                         width=max(1, px(1)), border_radius=px(6))

        footer = "H 自动提示 · R 重开 · Esc 返回"
        draw_text(self.screen, footer, 16, TEXT_FAINT,
                  (PANEL_RECT.centerx, PANEL_RECT.bottom - px(24)), anchor="center")

    # -------- 通关 / 失败卡片

    def draw_result_card(self, win):
        fade = ease_out(self.overlay_t)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((8, 9, 13, int(180 * fade)))
        self.screen.blit(veil, (0, 0))

        scale = 0.90 + 0.10 * fade
        w, h = int(CARD_W * scale), int(CARD_H * scale)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = CARD_RECT.center

        shadow = rect.move(0, px(10))
        pygame.draw.rect(self.screen, SHADOW, shadow, border_radius=px(24))
        pygame.draw.rect(self.screen, (40, 44, 58), rect, border_radius=px(24))
        accent = GREEN if win else RED
        pygame.draw.rect(self.screen, accent, rect,
                         width=max(2, px(3)), border_radius=px(24))

        last_level = self.level.index >= len(LEVELS) - 1
        if win:
            title = "全部通关！" if last_level else "关卡完成！"
            color = GOLD if last_level else GREEN
        else:
            title = "挑战失败"
            color = RED

        draw_text(self.screen, title, 42, color, (rect.centerx, rect.top + px(54)),
                  anchor="center", bold=True)
        draw_text(self.screen, "第 %d 关 · %s" % (self.level.index + 1, self.level.name),
                  20, TEXT_DIM, (rect.centerx, rect.top + px(100)), anchor="center")

        if win:
            line1 = "本关 %d 支箭头全部飞出棋盘" % self.level.total
            line2 = ("失误 %d 次，剩余 %d 次" % (self.level.mistakes_used,
                                                self.level.mistakes_left))
        else:
            line1 = "失误次数已经用完"
            line2 = "本关还剩 %d 支箭头没有飞出" % self.level.remaining

        draw_text(self.screen, line1, 21, TEXT, (rect.centerx, rect.top + px(148)),
                  anchor="center")
        draw_text(self.screen, line2, 21, TEXT, (rect.centerx, rect.top + px(180)),
                  anchor="center")
        if win and last_level:
            draw_text(self.screen, "你已经完成了全部 %d 关，厉害！" % len(LEVELS),
                      19, GOLD, (rect.centerx, rect.top + px(214)), anchor="center")


def wrap_text(text, size, max_width):
    """按像素宽度给中文折行。"""
    lines, current = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        if text_width(current + ch, size) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------- 主循环

def start_display(explicit_scale=None, caption="一箭又一箭"):
    """统一的启动流程：声明 DPI 感知 -> 初始化 -> 按屏幕算出缩放 -> 建窗口。"""
    enable_high_dpi()
    pygame.init()
    pygame.display.set_caption(caption)
    init_ui(compute_scale(explicit_scale))
    return pygame.display.set_mode((WIDTH, HEIGHT))


def run():
    screen = start_display()
    clock = pygame.time.Clock()
    game = Game()
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle_event(event)
        game.update(dt)
        game.draw()
        pygame.display.flip()
    pygame.quit()


# ---------------------------------------------------------------- 调试模式

def _step(game, seconds):
    for _ in range(int(seconds * 60)):
        game.update(1.0 / 60)


def run_auto(scale=None):
    """不弹窗口，按求解器给出的顺序把每一关自动打通，验证整条流程。"""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    start_display(scale)
    game = Game()

    print("自动试玩（缩放 %.2fx，窗口 %dx%d）：" % (SCALE, WIDTH, HEIGHT))
    ok = True
    for index in range(len(LEVELS)):
        game.start_level(index)
        order = find_solution(index)
        if order is None:
            print("  第 %d 关 无解" % (index + 1))
            ok = False
            continue

        for cell in order:
            guard = 0
            while game.busy() and guard < 600:
                _step(game, 1.0 / 60)
                guard += 1
            game.click_cell(cell)

        guard = 0
        while game.state != STATE_WIN and guard < 600:
            _step(game, 1.0 / 60)
            guard += 1

        state = game.level
        passed = (game.state == STATE_WIN and state.is_cleared
                  and state.mistakes_used == 0)
        ok &= passed
        print("  第 %d 关 %-6s 点击 %2d 次全部飞出，失误 %d 次，界面状态 = %s  %s"
              % (index + 1, LEVELS[index]["name"], len(order), state.mistakes_used,
                 game.state, "通过" if passed else "失败"))

    # 再验一次"失误耗尽 -> 失败界面"
    game.start_level(0)
    blocked = None
    for cell in sorted(game.level.arrows):
        if game.level.blocker_of(cell):
            blocked = cell
            break
    for _ in range(game.level.max_mistakes):
        guard = 0
        while game.busy() and guard < 600:
            _step(game, 1.0 / 60)
            guard += 1
        game.click_cell(blocked)
    guard = 0
    while game.state != STATE_OVER and guard < 600:
        _step(game, 1.0 / 60)
        guard += 1
    over_ok = game.state == STATE_OVER
    ok &= over_ok
    print("  失误耗尽 -> 失败界面：%s" % ("通过" if over_ok else "失败"))

    # 自动提示：走真实的界面路径点两次，每次都应自动飞出一支且不消耗失误；第三次不再给
    game.start_level(2)
    hint_ok = True
    for i in range(game.level.max_hints):
        guard = 0
        while game.busy() and guard < 600:
            _step(game, 1.0 / 60)
            guard += 1

        before_hints = game.level.hints_left
        before_arrows = game.level.remaining
        before_mistakes = game.level.mistakes_left
        game.use_hint()

        flew = any(isinstance(a, FlyOutAnim) for a in game.anims)
        if (not flew
                or game.level.hints_left != before_hints - 1
                or game.level.remaining != before_arrows - 1
                or game.level.mistakes_left != before_mistakes):
            hint_ok = False
            break
    game.use_hint()                       # 第 max_hints+1 次：不该再给
    if game.level.hints_left != 0:
        hint_ok = False
    ok &= hint_ok
    print("  自动提示（用 %d 次，每次都自动飞出一支、失误不变；第 %d 次不再给）：%s"
          % (game.level.max_hints, game.level.max_hints + 1,
             "通过" if hint_ok else "失败"))

    game.restart_level()
    restart_ok = (game.state == STATE_PLAY and game.level.remaining == game.level.total
                  and game.level.mistakes_left == game.level.max_mistakes
                  and game.level.hints_left == game.level.max_hints)
    ok &= restart_ok
    print("  重新开始恢复初始状态：%s" % ("通过" if restart_ok else "失败"))

    pygame.quit()
    print("\n自动试玩结果：%s" % ("全部通过" if ok else "存在失败项"))
    return 0 if ok else 1


def run_shots(scale=None):
    """把各个界面渲染成 PNG，方便快速检查排版。"""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    start_display(scale, caption="一箭又一箭（截图）")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shots")
    os.makedirs(out_dir, exist_ok=True)
    game = Game()
    print("截图尺寸 %dx%d（缩放 %.2fx）" % (WIDTH, HEIGHT, SCALE))

    def shot(name):
        for button in game.buttons:
            button.update((-1, -1))
        game.draw()
        pygame.image.save(game.screen, os.path.join(out_dir, name))
        print("  已保存", name)

    game.state = STATE_START
    game.build_buttons()
    shot("01_开始界面.png")

    game.start_level(0)
    game.hover_pos = (3, 1)                 # 悬停一个被挡住的箭头，展示路径预览
    shot("02_第1关_被挡住.png")

    game.hover_pos = (1, 1)                 # 悬停一个能飞出的箭头
    shot("03_第1关_可飞出.png")

    game.start_level(3)
    game.hover_pos = (6, 6)
    shot("04_第4关_棋盘较大.png")

    game.start_level(1)
    game.hover_pos = None
    game.click_cell(find_solution(1)[0])
    _step(game, 0.16)                       # 抓一帧飞出动画
    shot("05_飞出动画.png")

    game.start_level(1)
    blocked = next(c for c in sorted(game.level.arrows) if game.level.blocker_of(c))
    game.hover_pos = None
    game.click_cell(blocked)
    _step(game, 0.18)                       # 抓一帧撞击动画
    shot("06_撞击反馈.png")

    game.start_level(3)
    game.hover_pos = None
    game.use_hint()
    _step(game, 0.20)                       # 抓一帧：自动点掉的那一支正在飞出
    shot("09_自动提示.png")

    game.start_level(1)
    for cell in find_solution(1):
        game.click_cell(cell)
        _step(game, 0.5)
    _step(game, 0.5)
    shot("07_通关界面.png")

    game.start_level(0)
    blocked = next(c for c in sorted(game.level.arrows) if game.level.blocker_of(c))
    for _ in range(game.level.max_mistakes):
        game.click_cell(blocked)
        _step(game, 0.6)
    _step(game, 0.5)
    shot("08_失败界面.png")

    pygame.quit()
    print("\n截图目录：%s" % out_dir)
    return 0


def parse_scale_arg(argv):
    """支持 --scale=1.4 / --scale 1.4，用来强制指定缩放倍率。"""
    for i, arg in enumerate(argv):
        if arg.startswith("--scale="):
            return float(arg.split("=", 1)[1])
        if arg == "--scale" and i + 1 < len(argv):
            return float(argv[i + 1])
    return None


def main():
    scale = parse_scale_arg(sys.argv)
    if "--auto" in sys.argv:
        return run_auto(scale)
    if "--shots" in sys.argv:
        return run_shots(scale)
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
