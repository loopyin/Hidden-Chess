from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple

HIDDEN_THRESHOLD = 2.0
FAKEOUT_THRESHOLD = 6.0


@dataclass(frozen=True)
class GestureState:
    active: bool = False
    phase: str = "idle"
    timer: float = 0.0
    hidden: bool = False
    fakeout: bool = False
    source_sq: Optional[Tuple[int, int]] = None
    source_piece: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data.get("source_sq") is not None:
            data["source_sq"] = list(data["source_sq"])
        return data


def gesture_phase(timer: float) -> str:
    if timer >= FAKEOUT_THRESHOLD:
        return "fakeout"
    if timer >= HIDDEN_THRESHOLD:
        return "hidden"
    if timer > 0:
        return "charging"
    return "idle"


def default_gesture_state() -> Dict[str, Any]:
    return GestureState().to_dict()


def normalize_gesture_state(raw: Any) -> Dict[str, Any]:
    base = default_gesture_state()
    if not raw:
        return base

    if isinstance(raw, GestureState):
        raw = raw.to_dict()

    if not isinstance(raw, dict):
        return base

    data = base.copy()
    data["active"] = bool(raw.get("active", data["active"]))
    data["phase"] = str(raw.get("phase", data["phase"]))
    try:
        data["timer"] = float(raw.get("timer", data["timer"]))
    except (TypeError, ValueError):
        data["timer"] = 0.0
    data["hidden"] = bool(raw.get("hidden", data["hidden"]))
    data["fakeout"] = bool(raw.get("fakeout", data["fakeout"]))

    source_sq = raw.get("source_sq", data["source_sq"])
    if isinstance(source_sq, (list, tuple)) and len(source_sq) == 2:
        try:
            data["source_sq"] = [int(source_sq[0]), int(source_sq[1])]
        except (TypeError, ValueError):
            data["source_sq"] = None
    else:
        data["source_sq"] = None

    source_piece = raw.get("source_piece", data["source_piece"])
    data["source_piece"] = source_piece if source_piece is None or isinstance(source_piece, str) else str(source_piece)

    return data


def build_gesture_state(
    timer: float,
    *,
    hidden: bool = False,
    fakeout: bool = False,
    active: bool = True,
    source_sq: Optional[Tuple[int, int]] = None,
    source_piece: Optional[str] = None,
) -> Dict[str, Any]:
    state = GestureState(
        active=active,
        phase=gesture_phase(timer) if active else "idle",
        timer=max(0.0, float(timer)),
        hidden=bool(hidden),
        fakeout=bool(fakeout),
        source_sq=source_sq,
        source_piece=source_piece,
    )
    return state.to_dict()


def gesture_flags(state: Any) -> Tuple[bool, bool]:
    st = normalize_gesture_state(state)
    return st["hidden"], st["fakeout"]
