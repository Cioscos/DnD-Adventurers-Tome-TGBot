"""D&D 5e XP thresholds per level.

XP_THRESHOLDS[i] is the minimum XP required to reach level i+1.
Index 0 → Level 1 (0 XP), index 19 → Level 20 (355 000 XP).
"""

XP_THRESHOLDS: tuple[int, ...] = (
    0,        # Level 1
    300,      # Level 2
    900,      # Level 3
    2_700,    # Level 4
    6_500,    # Level 5
    14_000,   # Level 6
    23_000,   # Level 7
    34_000,   # Level 8
    48_000,   # Level 9
    64_000,   # Level 10
    85_000,   # Level 11
    100_000,  # Level 12
    120_000,  # Level 13
    140_000,  # Level 14
    165_000,  # Level 15
    195_000,  # Level 16
    225_000,  # Level 17
    265_000,  # Level 18
    305_000,  # Level 19
    355_000,  # Level 20
)


def xp_to_level(xp: int) -> int:
    """Return the D&D 5e level corresponding to *xp* total experience points."""
    level = 1
    for threshold in XP_THRESHOLDS:
        if xp >= threshold:
            level = XP_THRESHOLDS.index(threshold) + 1
        else:
            break
    return level


def xp_for_next_level(current_xp: int) -> tuple[int, int | None]:
    """Return (current_level, xp_needed_for_next_level).

    xp_needed_for_next_level is None when the character is already level 20.
    """
    current_level = xp_to_level(current_xp)
    if current_level >= 20:
        return 20, None
    next_threshold = XP_THRESHOLDS[current_level]  # index = level (0-based → next level)
    return current_level, next_threshold - current_xp
