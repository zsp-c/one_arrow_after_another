# -*- coding: utf-8 -*-
"""关卡自检 / 自动试玩脚本（不需要图形界面）。

用法:  python check_levels.py

对每一关做四件事：
  1. 打印棋盘布局；
  2. 用求解器搜出一条零失误通关顺序；
  3. 把这条顺序通过 LevelState.click() 真正点一遍，逐步校验；
  4. 额外校验"点被挡住的箭头会扣失误""重新开始能复原"。
"""

import sys

# Windows 控制台默认是 GBK，直接输出中文容易乱码，这里统一改成 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from game_logic import (
    DIR_TO_CHAR, DIR_TO_NAME, LevelState, analyze, find_blocker,
    parse_level, verify_solution,
)
from levels import LEVELS


def print_board(rows, cols, arrows, order=None):
    """打印棋盘；给了 order 就在格子里标出它是第几步飞出的。"""
    step_of = {}
    if order:
        for i, pos in enumerate(order, 1):
            step_of[pos] = i

    header = "      " + "".join("c%-3d" % c for c in range(cols))
    print(header)
    for r in range(rows):
        cells = []
        for c in range(cols):
            if (r, c) in arrows:
                cells.append(" %s " % DIR_TO_CHAR[arrows[(r, c)]])
            else:
                cells.append(" · ")
        line = "  r%-2d " % r + "".join(cells)
        marks = []
        for c in range(cols):
            if (r, c) in step_of:
                marks.append("%-3d" % step_of[(r, c)])
            else:
                marks.append("   ")
        print(line + "     " + "".join(marks))
    print()


def check_one(index):
    defn = LEVELS[index]
    rows, cols, arrows = parse_level(defn)
    info = analyze(index)

    print("=" * 66)
    print("第 %d 关 · %s   %d 行 x %d 列   箭头 %d 支   失误上限 %d 次"
          % (index + 1, defn["name"], rows, cols, info["total"], defn["mistakes"]))
    print("=" * 66)

    if info["deadlock"]:
        print_board(rows, cols, arrows)
        print("!! 无解：无论怎么点都不可能清空，请修改关卡数据。\n")
        return False

    print_board(rows, cols, arrows, info["solution"])

    free = info["free_at_start"]
    print("开局就能飞出的箭头：%s" % (
        "、".join("%s(%s)" % (p, DIR_TO_NAME[arrows[p]]) for p in free) or "无"))

    print("\n推荐通关顺序（格子后面的数字是它飞出的步数）：")
    state = LevelState(index)
    for step, pos in enumerate(info["solution"], 1):
        direction = state.arrows[pos]
        state.click(pos)
        print("  第 %2d 步：点击 r%dc%d  %s（向%s）→ 飞出棋盘，剩余 %2d 支"
              % (step, pos[0], pos[1], DIR_TO_CHAR[direction],
                 DIR_TO_NAME[direction], state.remaining))

    ok, msg = verify_solution(index, info["solution"])
    print("\n回放校验：%s —— %s" % ("通过" if ok else "失败", msg))
    if not ok:
        return False

    # --- 额外校验 1：点被挡住的箭头必须扣失误、且箭头不消失 ---
    state = LevelState(index)
    blocked_case = None
    for pos in sorted(state.arrows):
        if find_blocker(state.arrows, state.rows, state.cols, pos, state.arrows[pos]):
            blocked_case = pos
            break
    if blocked_case is not None:
        before = state.remaining
        result = state.click(blocked_case)
        assert result.kind == "blocked", "被挡住的箭头应当返回 blocked"
        assert result.blocker is not None, "被挡住时应给出阻挡者坐标"
        assert state.remaining == before, "被挡住时箭头不应消失"
        assert state.mistakes_left == state.max_mistakes - 1, "失误次数应当减一"
        print("碰撞校验：点击 r%dc%d 被 r%dc%d 挡住，箭头保留，失误 %d → %d，通过"
              % (blocked_case[0], blocked_case[1], result.blocker[0], result.blocker[1],
                 state.max_mistakes, state.mistakes_left))
    else:
        print("碰撞校验：本关开局所有箭头都畅通（无需碰撞校验）")

    # --- 额外校验 1.5：自动提示功能 ---
    # 提示会直接替玩家把箭头点掉，所以这里要确认：选中的箭头必定能飞出去、
    # 必定不会浪费失误次数、次数用完后不再给。
    state = LevelState(index)
    assert state.hints_left == state.max_hints, "开局提示次数应等于上限"
    for i in range(state.max_hints):
        left_arrows = state.remaining
        mistakes = state.mistakes_left
        pos = state.use_hint()
        assert pos is not None, "还剩 %d 次提示，应当能给出提示" % state.hints_left
        assert pos in state.arrows, "提示应当指向棋盘上真实存在的箭头"
        assert state.blocker_of(pos) is None, \
            "提示给出的箭头必须是可以直接飞出棋盘的（%s 被挡住了）" % (pos,)
        assert state.hints_left == state.max_hints - i - 1, "提示次数应逐次递减"

        result = state.click(pos)                     # 自动提示做的就是这一步
        assert result.kind == "out", \
            "自动提示选中的箭头必须能飞出，实际是 %s" % result.kind
        assert state.remaining == left_arrows - 1, "自动提示后箭头应当减少一支"
        assert state.mistakes_left == mistakes, "自动提示不应消耗失误次数"

    assert state.use_hint() is None, "提示次数用完后不应再给出提示"
    assert state.hints_left == 0, "提示次数不应变成负数"
    print("自动提示校验：连续 %d 次提示均自动飞出一支可走的箭头、且不消耗失误，"
          "用完后不再给，通过" % state.max_hints)

    # 提示必须是稳定可复现的：同一局面重复问应当给出同一支箭头
    fresh = LevelState(index)
    assert fresh.use_hint() == LevelState(index).use_hint(), "同一局面的提示结果应当一致"

    # --- 额外校验 2：重新开始必须完全复原 ---
    state = LevelState(index)
    state.click(blocked_case if blocked_case else sorted(state.arrows)[0])
    if blocked_case is None:
        state.click(sorted(state.arrows)[0])
    state.reset()
    assert state.remaining == state.total, "重新开始后箭头数量应复原"
    assert state.mistakes_left == state.max_mistakes, "重新开始后失误次数应复原"
    assert state.mistakes_used == 0, "重新开始后失误计数应清零"
    assert state.hints_left == state.max_hints, "重新开始后提示次数应复原"
    print("重开校验：箭头复原为 %d 支，失误复原为 %d 次，提示复原为 %d 次，通过"
          % (state.total, state.max_mistakes, state.max_hints))

    # --- 额外校验 3：失误耗尽应当判负 ---
    state = LevelState(index)
    for _ in range(state.max_mistakes):
        state.click(blocked_case if blocked_case else sorted(state.arrows)[0])
    assert state.is_failed, "失误用完后应当判负"
    print("失败校验：连续失误 %d 次后 is_failed = True，通过" % state.max_mistakes)
    print()
    return True


def main():
    print()
    print("一箭又一箭 —— 关卡自检报告")
    print()
    all_ok = True
    for i in range(len(LEVELS)):
        all_ok &= check_one(i)

    print("=" * 66)
    if all_ok:
        print("全部 %d 关检查通过：均存在零失误通关顺序，且无死局。" % len(LEVELS))
        print("（上面打印的“推荐通关顺序”已由程序逐步回放验证过。）")
    else:
        print("存在未通过的关卡，请检查 levels.py。")
    print("=" * 66)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
