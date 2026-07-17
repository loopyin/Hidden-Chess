class Action:
    def execute(self, gs):
        raise NotImplementedError
    
    def post_execute(self, gs, client_state, play_sound_fn):
        pass
    
    def to_dict(self):
        raise NotImplementedError

class MovePiece(Action):
    def __init__(self, fr, fc, tr, tc, hidden=False, promo=None, fakeout=False, drafted_turn=None):
        self.fr = fr
        self.fc = fc
        self.tr = tr
        self.tc = tc
        self.hidden = hidden
        self.promo = promo
        self.fakeout = fakeout
        self.drafted_turn = drafted_turn

    def execute(self, gs):
        from chess_logic import exec_move
        if self.fakeout:
            gs['fakeout_active'] = True
        res = exec_move(gs, self.fr, self.fc, self.tr, self.tc, hidden_move=self.hidden, promo=self.promo)
        if hasattr(self, 'drafted_turn') and self.drafted_turn is not None:
            if gs.get('log'):
                last = gs['log'][-1]
                if '|t' not in last:
                    gs['log'][-1] = last + f"|t{self.drafted_turn}"
        return res
    
    def post_execute(self, gs, client_state, play_sound_fn):
        # Auto-trigger next if it's a Normal or Hidden move, NOT a Fakeout
        if not self.fakeout:
            # Replicating the "Next" button click logic
            # This logic needs to be available here, or in a shared utility.
            # For now, let's assume we can trigger the logic.
            # Wait, I cannot call end_turn here, as requested.
            pass

    def to_dict(self):
        return {
            'type': 'move',
            'fr': self.fr,
            'fc': self.fc,
            'tr': self.tr,
            'tc': self.tc,
            'hidden': self.hidden,
            'promo': self.promo,
            'fakeout': self.fakeout,
            'drafted_turn': self.drafted_turn
        }

class EndTurn(Action):
    def __init__(self, drafted_turn=None):
        self.drafted_turn = drafted_turn
    def execute(self, gs):
        from chess_logic import end_turn
        end_turn(gs)
        return True

    def to_dict(self):
        return {'type': 'end_turn', 'drafted_turn': self.drafted_turn}

def deserialize_action(data):
    tipo = data.get('type')
    if tipo == 'move':
        return MovePiece(
            fr=data['fr'], fc=data['fc'], tr=data['tr'], tc=data['tc'],
            hidden=data.get('hidden', False),
            promo=data.get('promo'),
            fakeout=data.get('fakeout', False),
            drafted_turn=data.get('drafted_turn')
        )
    elif tipo == 'end_turn':
        return EndTurn(drafted_turn=data.get('drafted_turn'))
    return None
