from __future__ import annotations

import json
import os
import threading
import traceback
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _repo_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _logs_dir() -> str:
    path = os.path.join(_repo_root(), 'logs')
    os.makedirs(path, exist_ok=True)
    return path


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        if isinstance(value, dict):
            return {str(k): _safe_json(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_safe_json(v) for v in value]
        return repr(value)


class EventRecorder:
    """Small ring buffer plus persistent session log for crash forensics."""

    def __init__(self, namespace: str = 'session', max_events: int = 200):
        self.namespace = namespace
        self.max_events = max_events
        self.buffer = deque(maxlen=max_events)
        self._lock = threading.RLock()
        self._session_path = os.path.join(_logs_dir(), f'{namespace}_session.log')
        self._last_dump_path: Optional[str] = None

    def record(self, event: str, **data: Any) -> None:
        item = {
            'time': datetime.now(timezone.utc).isoformat(),
            'event': event,
            'data': _safe_json(data),
        }
        try:
            with self._lock:
                self.buffer.append(item)
                line = json.dumps(item, ensure_ascii=False, default=repr)
                with open(self._session_path, 'a', encoding='utf-8') as f:
                    f.write(line + '\n')
        except Exception:
            # Never let debug instrumentation break the game flow.
            pass

    def snapshot(self, event: str, gs: Optional[dict] = None, **data: Any) -> None:
        payload: Dict[str, Any] = dict(data)
        if isinstance(gs, dict):
            payload.update({
                'turn': gs.get('turn'),
                'turn_count': gs.get('turn_count'),
                'game_over': gs.get('game_over'),
                'normal_done': gs.get('normal_done'),
                'hidden_count': gs.get('hidden_count'),
                'fakeout_count': gs.get('fakeout_count'),
                'fakeout_active': gs.get('fakeout_active'),
                'fakeout_used': gs.get('fakeout_used'),
                'hidden_mode': gs.get('hidden_mode'),
                'ice_king_enabled': gs.get('ice_king_enabled'),
                'score_to_win': gs.get('score_to_win'),
                'frozen_pieces_count': len(gs.get('frozen_pieces', []) or []),
                'last_predict_by': gs.get('last_predict', {}).get('by') if gs.get('last_predict') else None,
                'queue_w': len(gs.get('next_queue_w', []) or []),
                'queue_b': len(gs.get('next_queue_b', []) or []),
                'pts_w': gs.get('pts', {}).get('w') if isinstance(gs.get('pts'), dict) else None,
                'pts_b': gs.get('pts', {}).get('b') if isinstance(gs.get('pts'), dict) else None,
            })
        self.record(event, **payload)

    def dump(self, label: str = 'crash', exc: Optional[BaseException] = None, context: Optional[dict] = None) -> str:
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(_logs_dir(), f'{self.namespace}_{label}_{ts}.log')

        with self._lock:
            lines = []
            lines.append(f'=== Event Recorder Dump: {self.namespace} ===')
            lines.append(f'Time: {datetime.now(timezone.utc).isoformat()}')
            lines.append(f'Buffer size: {len(self.buffer)}/{self.max_events}')
            lines.append('')

            if exc is not None:
                lines.append('=== Exception ===')
                lines.append(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
                lines.append('')

            if context is not None:
                lines.append('=== Context ===')
                try:
                    lines.append(json.dumps(_safe_json(context), ensure_ascii=False, indent=2, default=repr))
                except Exception:
                    lines.append(repr(context))
                lines.append('')

            lines.append('=== Last Events ===')
            for idx, item in enumerate(self.buffer, 1):
                lines.append(f'{idx:03d} {item["time"]} {item["event"]}')
                try:
                    lines.append(json.dumps(item['data'], ensure_ascii=False, default=repr))
                except Exception:
                    lines.append(repr(item['data']))
            lines.append('')

            with open(filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            self._last_dump_path = filename
            return filename

    @property
    def last_dump_path(self) -> Optional[str]:
        return self._last_dump_path


_global_recorders: Dict[str, EventRecorder] = {}
_global_lock = threading.RLock()


def get_recorder(namespace: str = 'session', max_events: int = 200) -> EventRecorder:
    with _global_lock:
        rec = _global_recorders.get(namespace)
        if rec is None:
            rec = EventRecorder(namespace=namespace, max_events=max_events)
            _global_recorders[namespace] = rec
        return rec
