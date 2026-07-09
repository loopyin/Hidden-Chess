import copy

def get_predict_legals(gs, r, c):
    gs_copy = copy.deepcopy(gs)
    # Flip turn to opponent
    gs_copy['turn'] = 'b' if gs['turn'] == 'w' else 'w'
    # Do we need to disable hidden_mode etc? Yes
    gs_copy['hidden_mode'] = False
    gs_copy['fakeout_active'] = False
    # we need to import legal from chess_logic? We can just do chess_logic.legal
    # Wait, in client.py, legal is imported as legal
    pass

