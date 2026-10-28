"""Tic-tac-toe rules on the 3x3 grid."""

from typing import List, Optional, Sequence

LINES = (
    [[0, 0], [0, 1], [0, 2]], [[1, 0], [1, 1], [1, 2]], [[2, 0], [2, 1], [2, 2]],
    [[0, 0], [1, 0], [2, 0]], [[0, 1], [1, 1], [2, 1]], [[0, 2], [1, 2], [2, 2]],
    [[0, 0], [1, 1], [2, 2]], [[0, 2], [1, 1], [2, 0]],
)


def other_player(mark: str) -> str:
    return "O" if mark == "X" else "X"


def winning_line(marks: Sequence[Sequence[Optional[str]]]) -> Optional[List[List[int]]]:
    """The first completed line of one mark, or None. `marks[r][c]` is "X", "O" or None."""
    for line in LINES:
        first = marks[line[0][0]][line[0][1]]
        if first and all(marks[r][c] == first for r, c in line):
            return [list(cell) for cell in line]
    return None


def is_full(marks: Sequence[Sequence[Optional[str]]]) -> bool:
    return all(mark for row in marks for mark in row)
