import time
import json
import traceback
import sys
import platform
import os
import uuid
import copy

class GameDebugger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GameDebugger, cls).__new__(cls)
            cls._instance.reset()
        return cls._instance

    def reset(self):
        self.metadata = {
            "version": "1.5.3",
            "game_id": str(uuid.uuid4()),
            "start_time": time.time(),
            "end_time": None,
            "platform": platform.platform(),
            "os": os.name,
            "python_version": sys.version,
            "mode": "unknown",
            "settings": {}
        }
        self.event_log = []
        self.network_log = []
        self.diff_log = []
        self.snapshots = []
        self.gesture_log = []
        self.hidden_log = []
        self.fakeout_log = []
        self.points_log = []
        self.pieces_log = {}
        self.readable_logs = []
        self.exceptions_log = []
        
        self.last_gs_snapshot = None
        self.last_network_in = None
        self.last_network_out = None
        self.snapshot_counter = 0

    def init_metadata(self, mode, settings=None):
        self.metadata["mode"] = mode
        if settings:
            self.metadata["settings"] = settings

    def log_event(self, origin, event_type, data):
        self.event_log.append({
            "timestamp": time.time(),
            "origin": origin,
            "event": event_type,
            "data": data
        })

    def log_network(self, direction, packet_type, payload):
        entry = {
            "timestamp": time.time(),
            "direction": direction,
            "packet_type": packet_type,
            "payload": payload
        }
        self.network_log.append(entry)
        if direction == "receive":
            self.last_network_in = entry
        else:
            self.last_network_out = entry

    def record_diff(self, old_state, new_state):
        if old_state is None or new_state is None:
            return []
        
        changes = []
        
        # Simple top-level diff
        for k in set(old_state.keys()).union(set(new_state.keys())):
            if k in ['log', 'gesture_state', 'board']: # Skip huge or complex ones for simple diff
                continue
            old_v = old_state.get(k)
            new_v = new_state.get(k)
            if str(old_v) != str(new_v):
                changes.append({
                    "field": k,
                    "old": str(old_v) if old_v is not None else None,
                    "new": str(new_v) if new_v is not None else None
                })
                
        # Points diff
        if 'pts' in old_state and 'pts' in new_state:
            for c in ['w', 'b']:
                if old_state['pts'].get(c) != new_state['pts'].get(c):
                    changes.append({
                        "field": f"pts.{c}",
                        "old": old_state['pts'].get(c),
                        "new": new_state['pts'].get(c)
                    })
                    
        return changes

    def log_snapshot(self, gs, reason):
        # We need to make sure gs is serializable, but to keep it fast, we do a shallow/medium copy of what matters
        self.snapshot_counter += 1
        
        changes = self.record_diff(self.last_gs_snapshot, gs)
        if changes:
            self.diff_log.append({
                "snapshot": self.snapshot_counter,
                "timestamp": time.time(),
                "changes": changes
            })

        self.snapshots.append({
            "id": self.snapshot_counter,
            "timestamp": time.time(),
            "reason": reason,
            # we don't store the entire gs to save memory, maybe just basic info or full if needed
            "turn": gs.get('turn'),
            "pts": copy.deepcopy(gs.get('pts', {})),
            "hidden_count": gs.get('hidden_count')
        })
        
        self.last_gs_snapshot = copy.deepcopy(gs)

    def log_gesture(self, gesture_data):
        self.gesture_log.append(gesture_data)

    def log_hidden(self, hidden_data):
        self.hidden_log.append(hidden_data)

    def log_fakeout(self, fakeout_data):
        self.fakeout_log.append(fakeout_data)

    def log_points(self, player, old_pts, new_pts, reason):
        self.points_log.append({
            "timestamp": time.time(),
            "player": player,
            "old": old_pts,
            "new": new_pts,
            "reason": reason
        })

    def log_piece_history(self, piece_id, event_data):
        if piece_id not in self.pieces_log:
            self.pieces_log[piece_id] = []
        self.pieces_log[piece_id].append({
            "timestamp": time.time(),
            "event": event_data
        })

    def add_readable_log(self, text):
        self.readable_logs.append({
            "timestamp": time.time(),
            "text": text
        })

    def log_exception(self, e, context_msg=""):
        tb = traceback.format_exc()
        self.exceptions_log.append({
            "timestamp": time.time(),
            "context": context_msg,
            "exception": str(e),
            "stack_trace": tb,
            "last_network_in": self.last_network_in,
            "last_network_out": self.last_network_out,
            "last_snapshot": self.snapshot_counter
        })

    def _process_gs_log_for_histories(self):
        if not self.last_gs_snapshot:
            return
        
        gs_log = self.last_gs_snapshot.get('log', [])
        for entry in gs_log:
            parts = entry.split('|')
            if len(parts) >= 2:
                cmd = parts[0]
                if cmd == 'HIDDEN':
                    self.hidden_log.append({"raw": entry, "player": parts[1], "note": parts[2] if len(parts)>2 else ""})
                    self.points_log.append({"timestamp": time.time(), "player": parts[1], "reason": "HIDDEN", "raw": entry})
                elif cmd == 'FAKEOUT':
                    self.fakeout_log.append({"raw": entry, "player": parts[1], "note": parts[2] if len(parts)>2 else ""})
                    self.points_log.append({"timestamp": time.time(), "player": parts[1], "reason": "FAKEOUT", "raw": entry})
                elif cmd == 'ICE':
                    self.points_log.append({"timestamp": time.time(), "player": parts[1], "reason": "ICE", "raw": entry})
                elif cmd.startswith('SYS_'):
                    self.event_log.append({"timestamp": time.time(), "origin": "engine", "event": cmd, "data": entry})
                    if 'FAKEOUT' in cmd:
                        self.fakeout_log.append({"raw": entry, "type": "revealed"})
                    elif 'HIDDEN' in cmd:
                        self.hidden_log.append({"raw": entry, "type": "revealed"})
                
                # Basic piece tracking
                if " de " in entry and " para " in entry:
                    # heuristic text parsing for pieces_log
                    self.pieces_log.setdefault("tracked_pieces", []).append(entry)

    def export(self, filename=None):
        self.metadata["end_time"] = time.time()
        self.metadata["duration"] = self.metadata["end_time"] - self.metadata["start_time"]
        
        self._process_gs_log_for_histories()
        
        export_data = {
            "metadata": self.metadata,
            "event_log": self.event_log,
            "network_log": self.network_log,
            "diff_log": self.diff_log,
            "snapshots": self.snapshots,
            "gesture_log": self.gesture_log,
            "hidden_log": self.hidden_log,
            "fakeout_log": self.fakeout_log,
            "points_log": self.points_log,
            "pieces_log": self.pieces_log,
            "readable_logs": self.readable_logs,
            "exceptions_log": self.exceptions_log
        }
        
        if not filename:
            filename = f"debugger_dump_{int(time.time())}.json"
            
        def debug_encoder(obj):
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            elif isinstance(obj, set):
                return list(obj)
            elif isinstance(obj, tuple):
                return list(obj)
            return str(obj)
            
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=4, ensure_ascii=False, default=debug_encoder)
            
        return filename

debugger = GameDebugger()
