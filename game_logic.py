# -*- coding: utf-8 -*-
"""游戏核心逻辑：方向、路径判定、关卡状态、求解器。

这个模块**不导入 pygame**，可以脱离图形界面单独运行（check_levels.py 就靠它做验证）。
"""

from dataclasses import dataclass

from levels import LEVELS

# ---------------------------------------------------------------- 方向

UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"

# 方向 -> (行增量, 列增量)。屏幕坐标里行号向下增大。
DELTA = {
    UP: (-1, 0),
    DOWN: (1, 0),
    LEFT: (0, -1),
    RIGHT: (0, 1),
}

# 每关默认的提示次数，可以在关卡数据里用 "hints" 字段单独覆盖。
HINTS_PER_LEVEL = 2

CHAR_TO_DIR = {"^": UP, "v": DOWN, "<": LEFT, ">": RIGHT}
DIR_TO_CHAR = {v: k for k, v in CHAR_TO_DIR.items()}
DIR_TO_NAME = {UP: "上", DOWN: "下", LEFT: "左", RIGHT: "右"}


# ---------------------------------------------------------------- 关卡解析

def parse_level(level_defn):
    """把字符画解析成 (行数, 列数, {(r, c): 方向})。"""
    grid = level_defn["map"]
    rows = len(grid)
    cols = len(grid[0])
    arrows = {}
    for r, line in enumerate(grid):
        if len(line) != cols:
            raise ValueError("第 %d 行长度不一致：%r" % (r, line))
        for c, ch in enumerate(line):
            if ch in CHAR_TO_DIR:
                arrows[(r, c)] = CHAR_TO_DIR[ch]
            elif ch != ".":
                raise ValueError("无法识别的字符 %r（第 %d 行第 %d 列）" % (ch, r, c))
    return rows, cols, arrows


# ---------------------------------------------------------------- 路径判定

def path_cells(rows, cols, pos, direction):
    """箭头前进方向上、棋盘以内的所有格子（不含自己），按由近到远排列。"""
    dr, dc = DELTA[direction]
    r, c = pos[0] + dr, pos[1] + dc
    cells = []
    while 0 <= r < rows and 0 <= c < cols:
        cells.append((r, c))
        r += dr
        c += dc
    return cells


def find_blocker(arrows, rows, cols, pos, direction):
    """返回挡在这个箭头前方的第一个箭头坐标；前方畅通则返回 None。"""
    for cell in path_cells(rows, cols, pos, direction):
        if cell in arrows:
            return cell
    return None


# ---------------------------------------------------------------- 点击结果

@dataclass
class ClickResult:
    """一次点击的结果。

    kind:
        "empty"   —— 点到空格子，不消耗失误
        "out"     —— 前方畅通，箭头飞出棋盘
        "blocked" —— 前方有箭头阻挡，消耗一次失误
    """

    kind: str
    pos: tuple = None
    direction: str = None
    blocker: tuple = None


# ---------------------------------------------------------------- 关卡状态

class LevelState:
    """单个关卡的可变状态：剩余箭头、剩余失误次数。"""

    def __init__(self, index):
        if not 0 <= index < len(LEVELS):
            raise IndexError("关卡下标越界: %r" % (index,))
        self.index = index
        self.defn = LEVELS[index]
        self.name = self.defn["name"]
        self.tip = self.defn.get("tip", "")
        self.rows, self.cols, self._initial = parse_level(self.defn)
        self.total = len(self._initial)
        self.max_mistakes = self.defn["mistakes"]
        self.max_hints = self.defn.get("hints", HINTS_PER_LEVEL)
        self.reset()

    # -------- 生命周期

    def reset(self):
        """恢复到关卡初始状态（重新开始用）。"""
        self.arrows = dict(self._initial)
        self.mistakes_left = self.max_mistakes
        self.mistakes_used = 0
        self.hints_left = self.max_hints
        self.cleared = 0

    # -------- 查询

    @property
    def remaining(self):
        return len(self.arrows)

    @property
    def is_cleared(self):
        return not self.arrows

    @property
    def is_failed(self):
        return self.mistakes_left <= 0

    def blocker_of(self, pos):
        direction = self.arrows.get(pos)
        if direction is None:
            return None
        return find_blocker(self.arrows, self.rows, self.cols, pos, direction)

    def path_of(self, pos):
        direction = self.arrows.get(pos)
        if direction is None:
            return []
        return path_cells(self.rows, self.cols, pos, direction)

    # -------- 操作

    def find_hint(self):
        """找出一支当前就能飞出棋盘的箭头，返回它的坐标；一支都没有则返回 None。

        注意：按本关规则，移除箭头只会解开阻挡、永远不会制造阻挡，
        所以任何一支"前方畅通"的箭头点掉都不会让关卡变成死局 —— 提示给哪一支都是安全的。
        这里按行列顺序取第一支，保证同一局面下提示结果稳定可复现。
        """
        for pos in sorted(self.arrows):
            if self.blocker_of(pos) is None:
                return pos
        return None

    def use_hint(self):
        """消耗一次提示机会并返回被提示的箭头坐标；没有机会或没有可点的箭头则返回 None。"""
        if self.hints_left <= 0:
            return None
        pos = self.find_hint()
        if pos is None:
            return None
        self.hints_left -= 1
        return pos

    def click(self, pos):
        """点击一个格子，返回 ClickResult。这里是唯一的规则入口。"""
        direction = self.arrows.get(pos)
        if direction is None:
            return ClickResult("empty", pos=pos)

        blocker = find_blocker(self.arrows, self.rows, self.cols, pos, direction)
        if blocker is None:
            del self.arrows[pos]
            self.cleared += 1
            return ClickResult("out", pos=pos, direction=direction)

        self.mistakes_left -= 1
        self.mistakes_used += 1
        return ClickResult("blocked", pos=pos, direction=direction, blocker=blocker)


# ---------------------------------------------------------------- 求解器

def find_solution(index, arrows=None):
    """深度优先搜索一条零失误的通关顺序。

    返回 [(r, c), ...]（按点击先后排列）；无解返回 None。
    箭头数量很少（<= 12），直接穷举即可。
    """
    if arrows is None:
        rows, cols, arrows = parse_level(LEVELS[index])
    else:
        rows, cols = LEVELS[index]["rows"], LEVELS[index]["cols"]

    order = []
    failed_states = set()

    def search(state):
        if not state:
            return True
        key = frozenset(state)
        if key in failed_states:          # 该局面已证明走不通，剪枝
            return False
        for pos in sorted(state):
            if find_blocker(state, rows, cols, pos, state[pos]) is None:
                direction = state.pop(pos)
                order.append(pos)
                if search(state):
                    return True
                order.pop()
                state[pos] = direction
        failed_states.add(key)
        return False

    return order if search(dict(arrows)) else None


def verify_solution(index, order):
    """把求解器给出的顺序真正点一遍，逐步确认每一步都合法。

    返回 (是否成功, 说明文字)。
    """
    state = LevelState(index)
    for step, pos in enumerate(order, 1):
        if pos not in state.arrows:
            return False, "第 %d 步 %s 已经不在棋盘上了" % (step, pos)
        direction = state.arrows[pos]
        blocker = find_blocker(state.arrows, state.rows, state.cols, pos, direction)
        if blocker is not None:
            return False, "第 %d 步 %s（%s）被 %s 挡住，不能飞出" % (
                step, pos, DIR_TO_NAME[direction], blocker)
        result = state.click(pos)
        if result.kind != "out":
            return False, "第 %d 步 %s 点击结果异常：%s" % (step, pos, result.kind)
    if not state.is_cleared:
        return False, "顺序走完后还剩 %d 支箭头" % state.remaining
    if len(order) != state.total:
        return False, "顺序只覆盖 %d / %d 支箭头" % (len(order), state.total)
    return True, "共 %d 步，失误 %d 次" % (len(order), state.mistakes_used)


def analyze(index):
    """给出一关的统计信息，供验证脚本打印。"""
    rows, cols, arrows = parse_level(LEVELS[index])
    free = [p for p in sorted(arrows)
            if find_blocker(arrows, rows, cols, p, arrows[p]) is None]
    order = find_solution(index)
    return {
        "rows": rows,
        "cols": cols,
        "total": len(arrows),
        "free_at_start": free,
        "deadlock": order is None,
        "solution": order,
    }
