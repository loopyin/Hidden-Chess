import pygame, sys, json, os, copy
import math, random, time
import asyncio
import traceback
from collections import deque
from chess_logic import GLYPHS, pt, pc, get_absolute_board, get_true_board, in_check, hidden_cost, check_conflict, \
    legal, serialize_state, deserialize_state, make_state, can_afford, can_afford_fakeout, exec_move, end_turn, alg, deactivate_plies, get_ui_selection, \
    process_next_queues, get_next_turn_from_queue, pop_next_turn_from_queue, compare_turns, ice_king_interaction, register_predict_move
from mechanics import MechanicsManager
from draft_simulator import get_draft_state
from renderer import BoardRenderer
from chess_logic import fakeout_cost


class FlameParticle:
    alpha_layer_qty = 2
    alpha_glow_difference_constant = 2

    def __init__(self, x=0, y=0, r=5, vx=0, vy=0, color_type='blue'):
        self.color_type = color_type
        self.x = x
        self.y = y
        self.r = r
        self.original_r = r
        self.alpha_layers = FlameParticle.alpha_layer_qty
        self.alpha_glow = FlameParticle.alpha_glow_difference_constant
        max_surf_size = max(1, 2 * self.r * self.alpha_layers * self.alpha_layers * self.alpha_glow)
        self.surf = pygame.Surface((max_surf_size, max_surf_size), pygame.SRCALPHA)
        self.burn_rate = 0.1 * random.randint(1, 4)
        self.vx = vx
        self.vy = vy

    def update(self):
        self.y -= 7 - self.r
        self.x += random.randint(-self.r, self.r)
        self.x -= self.vx * 0.05
        self.y -= self.vy * 0.05
        self.original_r -= self.burn_rate
        self.r = int(self.original_r)
        if self.r <= 0:
            self.r = 1

    def draw(self, screen):
        max_surf_size = max(1, 2 * self.r * self.alpha_layers * self.alpha_layers * self.alpha_glow)
        self.surf = pygame.Surface((max_surf_size, max_surf_size), pygame.SRCALPHA)
        for i in range(self.alpha_layers, -1, -1):
            if self.alpha_layers == 0:
                continue
            alpha = 255 - i * (255 // self.alpha_layers - 5)
            if alpha <= 0:
                alpha = 0
            radius = self.r * i * i * self.alpha_glow
            
            if self.color_type == 'orange':
                if self.r >= 4:
                    r_c, g_c, b_c = (255, 150, 50)
                elif self.r >= 2:
                    r_c, g_c, b_c = (255, 50, 0)
                else:
                    r_c, g_c, b_c = (50, 50, 50)
            else:
                if self.r >= 4:
                    r_c, g_c, b_c = (50, 150, 255)
                elif self.r >= 2:
                    r_c, g_c, b_c = (0, 50, 255)
                else:
                    r_c, g_c, b_c = (50, 50, 50)
            
            color = (r_c, g_c, b_c, alpha)
            pygame.draw.circle(self.surf, color, (self.surf.get_width() // 2, self.surf.get_height() // 2), radius)
        screen.blit(self.surf, self.surf.get_rect(center=(int(self.x), int(self.y))))

SESSION_FILE = "session_token.json"

def save_session(room_code, token):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump({'room_code': room_code, 'session_token': token}, f)
    except:
        pass

def load_session():
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return None

def clear_session():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except:
        pass

BOARD_PX = 560
PANEL_H = 215
SIDEBAR_W = 250
WIN_W = BOARD_PX + SIDEBAR_W
WIN_H = BOARD_PX + PANEL_H
SQ = BOARD_PX // 8
FPS = 60
PORTRAIT = False
LIGHT = (238, 238, 210)
DARK = (118, 150, 85)
C_SEL = (130, 151, 105)
C_CHECK = (210, 50, 50)
C_LAST = (205, 210, 106)
C_HIDDEN = (60, 110, 220)
C_FAKEOUT = (245, 120, 20)
BG = (22, 22, 24)
PANEL_BG = (30, 30, 34)
T_MAIN = (230, 215, 185)
T_DIM = (130, 120, 100)
T_BLUE = (90, 160, 255)
T_RED = (255, 90, 80)
BTN_N = (45, 48, 55)
BTN_H = (60, 65, 75)
BTN_BLUE = (38, 70, 180)
BTN_BLUEH = (55, 95, 215)
BTN_ORANGE = (220, 95, 25)
BTN_ORANGEH = (245, 120, 40)
BTN_TXT = (245, 245, 250)
BTN_END = (50, 95, 50)
BTN_ENDH = (70, 125, 70)

def draw_fancy_btn(screen, text, font, base_color, hover_color, text_color, rect, is_hover=False, is_disabled=False, border_color=None, custom_radius=8):
    c = hover_color if is_hover else base_color
    if is_disabled:
        c = (max(0, c[0]-30), max(0, c[1]-30), max(0, c[2]-30))
        text_color = (max(0, text_color[0]-80), max(0, text_color[1]-80), max(0, text_color[2]-80))
        
    # Drop shadow
    if not is_disabled:
        s_rect = rect.copy()
        s_rect.y += min(4, max(2, rect.h // 12))
        pygame.draw.rect(screen, (15, 15, 18), s_rect, border_radius=custom_radius)
        
    pygame.draw.rect(screen, c, rect, border_radius=custom_radius)
    
    if border_color:
        pygame.draw.rect(screen, border_color, rect, 2, border_radius=custom_radius)
        
    # Top edge highlight (inner bevel effect)
    if not is_disabled:
        hl_color = (min(255, c[0]+35), min(255, c[1]+35), min(255, c[2]+35))
        pygame.draw.line(screen, hl_color, (rect.x + custom_radius, rect.y + 1), (rect.right - custom_radius, rect.y + 1), 2)
        
    ts = font.render(text, True, text_color)
    screen.blit(ts, ts.get_rect(center=rect.center))

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_fonts():
    font_path = resource_path(os.path.join("assets", "DejaVuSans.ttf"))

    def get_font(size, bold=False):
        try:
            f = pygame.font.Font(font_path, size)
            if bold: f.set_bold(True)
            return f
        except:
            return pygame.font.SysFont('Arial', size, bold=bold)

    try:
        piece_font = pygame.font.Font(font_path, int(SQ * 0.76))
        promo_font = pygame.font.Font(font_path, int(SQ * 0.92))
    except:
        fallback_fonts = "segoeuisymbol, applecoloremoji, arial"
        piece_font = pygame.font.SysFont(fallback_fonts, int(SQ * 0.76))
        promo_font = pygame.font.SysFont(fallback_fonts, int(SQ * 0.92))

    return dict(
        piece=piece_font, promo=promo_font,
        coord=get_font(11, True), ui=get_font(13, True),
        small=get_font(12), big=get_font(15, True),
        pts=get_font(14, True), title=get_font(40, True)
    )

def registrar_proximo_lance_auto(gs, client_state):
    h_active = client_state.get('history_active', False)
    is_local = client_state.get('is_local', False)
    active_color = gs['turn'] if is_local else client_state.get('my_color')

    can_fakeout = gs.get('hidden_count', 0) == 1 and gs.get('fakeout_count', 0) == 0 and not gs.get('fakeout_used', False)
    cond = (gs.get('normal_done', False) or (gs.get('hidden_count', 0) > 0 and not can_fakeout))

    if not client_state.get('drafting'):
        temp_next_en = not h_active and gs['turn'] == active_color and cond
    else:
        dm = client_state.get('draft_moves', [])
        if dm and dm[-1].get('type') != 'end_turn':
            temp_next_en = not h_active and gs['turn'] == active_color and cond
        else:
            temp_next_en = False

    if client_state.get('draft_moves'):
        has_real_draft = check_has_real_draft(client_state['draft_moves'])
        if not has_real_draft:
            temp_next_en = False

    if not temp_next_en:
        return

    # Execute drafting logic
    play_sound('next')
    
    if client_state.get('drafting'):
        dm = client_state.get('draft_moves', [])
        if dm and dm[-1].get('type') != 'end_turn':
            dgs = get_draft_state(gs, dm, client_state.get('my_color'))
            dm.append({'type': 'end_turn', 'drafted_turn': (dgs['turn_count'] + 1) // 2})
            client_state['draft_moves'] = dm
    client_state['drafting'] = True
    client_state['draft_hidden'] = False
    client_state['draft_fakeout'] = False
    if 'draft_moves' not in client_state or client_state['draft_moves'] is None:
        client_state['draft_moves'] = []

IMAGES = {}
SOUNDS = {}

def load_assets(theme_name="classic"):
    images_dir = resource_path(os.path.join("assets", "themes", theme_name.lower()))
    sounds_dir = resource_path(os.path.join("assets", "sounds"))
    
    if os.path.exists(images_dir):
        for bp in ['wP', 'wR', 'wN', 'wB', 'wQ', 'wK', 'bP', 'bR', 'bN', 'bB', 'bQ', 'bK']:
            img_path = os.path.join(images_dir, f"{bp}.png")
            if os.path.exists(img_path):
                try:
                    img = pygame.image.load(img_path).convert_alpha()
                    IMAGES[bp] = pygame.transform.smoothscale(img, (SQ, SQ))
                except:
                    pass
        
        board_path = os.path.join(images_dir, "board.png")
        if os.path.exists(board_path):
            try:
                img = pygame.image.load(board_path).convert()
                IMAGES['board'] = pygame.transform.smoothscale(img, (BOARD_PX, BOARD_PX))
            except:
                pass
                    
    try:
        pygame.mixer.init()
        if os.path.exists(sounds_dir):
            for sx in ['move', 'capture', 'check', 'game_over', 'hidden', 'hidden_off', 'fakeout', 'fakeout_off', 'click', 'select', 'toggle', 'start', 'resign', 'next', 'end', 'next_move', 'spotted', 'fakeout_spotted', 'menu', 'freeze', 'unfreeze', 'error']:
                for ext in ['.wav', '.ogg', '.raw']:
                    snd_path = os.path.join(sounds_dir, f"{sx}{ext}")
                    if os.path.exists(snd_path):
                        try:
                            SOUNDS[sx] = pygame.mixer.Sound(snd_path)
                            break
                        except:
                            pass
    except:
        pass

def play_sound(snd_name):
    if snd_name in SOUNDS:
        try:
            SOUNDS[snd_name].play()
        except:
            pass

def draw_rect_aa(surf, color, rect, radius=5, border=0):
    pygame.draw.rect(surf, color, rect, border, border_radius=radius)

def spawn_particles(x, y, color, count, client_state, size=3, speed=150, life=0.3):
    if 'particles' not in client_state:
        client_state['particles'] = []
    for _ in range(count):
        angle = random.uniform(0, 6.28)
        vel = random.uniform(speed * 0.3, speed)
        client_state['particles'].append({
            'x': x,
            'y': y,
            'vx': math.cos(angle) * vel,
            'vy': math.sin(angle) * vel,
            'color': color,
            'life': life + random.uniform(-0.1, 0.1),
            'max_life': life + 0.1,
            'size': size * random.uniform(0.5, 1.5)
        })

def trigger_piece_anim(client_state, p, fr, fc, tr, tc, is_shadow=False, is_fakeout=False, is_capture=False):
    from chess_logic import pc
    client_state['anim'] = {
        'p': p,
        'color': pc(p) if p else None,
        'fr': fr, 'fc': fc,
        'tr': tr, 'tc': tc,
        't': 0.0,
        'dur': 0.25,
        'is_capture': is_capture,
        'is_hidden': is_shadow,
        'is_fakeout': is_fakeout
    }
    fr_d, fc_d = 7 - fr if client_state.get('flipped') else fr, 7 - fc if client_state.get('flipped') else fc
    start_x, start_y = fc_d * SQ + SQ // 2, fr_d * SQ + SQ // 2
    if is_shadow:
        spawn_particles(start_x, start_y, (60, 110, 220), 12, client_state, size=2.5, speed=90, life=0.3)
    elif is_fakeout:
        spawn_particles(start_x, start_y, (245, 120, 20), 12, client_state, size=2.5, speed=90, life=0.3)
    else:
        spawn_particles(start_x, start_y, (180, 170, 160), 8, client_state, size=2, speed=80, life=0.2)

def trigger_square_flash(client_state, r, c, color, rtype='hidden'):
    if 'flashes' not in client_state:
        client_state['flashes'] = {}
    client_state['flashes'][(r, c)] = {'t': 0.0, 'color': color}
    r_d, c_d = 7 - r if client_state.get('flipped') else r, 7 - c if client_state.get('flipped') else c
    px, py = c_d * SQ + SQ // 2, r_d * SQ + SQ // 2
    # Spawn particle effect
    spawn_particles(px, py, color, 16, client_state, size=3.5, speed=120, life=0.35)
    # Also play a highlight sound
    if rtype == 'hidden':
        play_sound('spotted')
    elif rtype == 'fakeout':
        play_sound('fakeout_spotted')
    elif rtype == 'gesture_invalid':
        play_sound('hidden_off')
    else:
        play_sound('move')

def trigger_freeze_effect(client_state, gs, r, c):
    """Triggers the freeze visual effect with specific particles and score indicator."""
    play_sound('freeze')
    
    val = 0
    p = gs['board'][r][c]
    if p:
        pt = p[1]
        val = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0}.get(pt, 0)
        
    if 'freeze_fx' not in client_state:
        client_state['freeze_fx'] = []
    
    client_state['freeze_fx'].append({
        'r': r, 'c': c,
        't': 0.0,
        'val': val,
        'particles': []
    })

def trigger_unfreeze_effect(client_state, gs, r, c):
    """Triggers the unfreeze visual effect."""
    play_sound('unfreeze')
    
    val = 0
    p = gs['board'][r][c]
    if p:
        pt = p[1]
        val = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0}.get(pt, 0)

    if 'unfreeze_fx' not in client_state:
        client_state['unfreeze_fx'] = []
    
    client_state['unfreeze_fx'].append({
        'r': r, 'c': c,
        't': 0.0,
        'val': val,
        'particles': []
    })

def get_cached_serialized_state(client_state, target_gs, player_color):
    cache = client_state.setdefault('_serialize_cache', {})
    sig = (
        id(target_gs),
        player_color,
        len(target_gs.get('log', [])),
        target_gs.get('turn'),
        target_gs.get('hidden_count'),
        target_gs.get('pts', {}).get('w') if isinstance(target_gs.get('pts'), dict) else None,
        target_gs.get('pts', {}).get('b') if isinstance(target_gs.get('pts'), dict) else None,
        target_gs.get('gold', {}).get('w') if isinstance(target_gs.get('gold'), dict) else None,
        target_gs.get('gold', {}).get('b') if isinstance(target_gs.get('gold'), dict) else None,
        len(target_gs.get('draft_queue', {}).get('w', []) if isinstance(target_gs.get('draft_queue'), dict) else []),
        len(target_gs.get('draft_queue', {}).get('b', []) if isinstance(target_gs.get('draft_queue'), dict) else []),
        target_gs.get('hidden_mode', False),
        target_gs.get('fakeout_active', False),
        target_gs.get('game_over', False),
        target_gs.get('game_over_msg', ''),
        client_state.get('resign_confirm', False),
        client_state.get('drafting', False),
        len(client_state.get('draft_moves', []) or []),
        client_state.get('draft_hidden', False),
        client_state.get('draft_fakeout', False),
        client_state.get('show_hidden', False),
        client_state.get('flipped', False),
        client_state.get('history_active', False),
        client_state.get('history_index', 0),
    )
    if sig in cache:
        return cache[sig]
    
    
    try:
        if client_state.get('drafting') and not client_state.get('history_active'):
            from draft_simulator import get_draft_state
            dgs = get_draft_state(target_gs, client_state.get('draft_moves', []), client_state.get('my_color'))
        else:
            dgs = None
    except Exception:
        dgs = None
    res = deserialize_state(serialize_state(target_gs, player_color=player_color, dgs=dgs))

    if len(cache) > 20:
        cache.clear()
    cache[sig] = res
    return res

def serialize_game_to_dict(gs, client_state):
    # Convert sets to lists so they are JSON serializable
    captured_w_list = [list(x) for x in gs.get('captured_w', [])]
    captured_b_list = [list(x) for x in gs.get('captured_b', [])]
    
    # Fully resolve hidden pieces
    hidden_w_clean = {}
    for pos, val in gs.get('hidden_w', {}).items():
        key_str = f"{pos[0]},{pos[1]}"
        hidden_w_clean[key_str] = {
            "pub_pos": list(val.pub_pos) if val.pub_pos else None,
            "piece": val.piece,
            "path": [list(x) for x in val.path] if val.path else [],
            "is_fakeout": val.is_fakeout,
            "fakeout_path": [list(x) for x in val.fakeout_path] if val.fakeout_path else [],
            "plies": val.plies
        }
        
    hidden_b_clean = {}
    for pos, val in gs.get('hidden_b', {}).items():
        key_str = f"{pos[0]},{pos[1]}"
        hidden_b_clean[key_str] = {
            "pub_pos": list(val.pub_pos) if val.pub_pos else None,
            "piece": val.piece,
            "path": [list(x) for x in val.path] if val.path else [],
            "is_fakeout": val.is_fakeout,
            "fakeout_path": [list(x) for x in val.fakeout_path] if val.fakeout_path else [],
            "plies": val.plies
        }

    shadow_history_clean = {}
    for ply, info in gs.get('shadow_history', {}).items():
        shadow_history_clean[str(ply)] = info

    export_data = {
        "room_code": client_state.get('room_code', 'LOCAL'),
        "player_color": client_state.get('my_color', 'w'),
        "game_over_msg": gs.get('game_over_msg', ''),
        "turn_count": gs.get('turn_count', 0),
        "points": gs.get('pts', {}),
        "log": gs.get('log', []),
        "shadow_history": shadow_history_clean,
        "board": gs.get('board', []),
        "captured_w_coords": captured_w_list,
        "captured_b_coords": captured_b_list,
        "hidden_pieces_white": hidden_w_clean,
        "hidden_pieces_black": hidden_b_clean,
        "timestamp": int(time.time()),
        "date_local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "turn_history_serialized": [serialize_state(snapshot) for snapshot in client_state.get('turn_history', [])]
    }
    return export_data

def load_replay_files():
    replay_list = []
    for f in os.listdir('.'):
        if f.endswith('.json'):
            if f.startswith('partida_') or 'replay' in f:
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        if "board" in data:
                            date_str = data.get('date_local', f.replace('partida_', '').replace('.json', ''))
                            turn_count = data.get('turn_count', 0)
                            player_color = data.get('player_color', 'w')
                            col_str = "Brancas" if player_color == 'w' else "Pretas"
                            replay_list.append({
                                'filename': f,
                                'date': date_str,
                                'turns': turn_count,
                                'color': col_str,
                                'data': data
                            })
                except Exception as e:
                    pass
    replay_list.sort(key=lambda x: x.get('data', {}).get('timestamp', 0), reverse=True)
    return replay_list

def get_cached_text(fonts, font_name, text, color, client_state):
    cache = client_state.setdefault('_text_cache', {})
    key = (font_name, text, color)
    if key in cache:
        return cache[key]
    if len(cache) > 300:
        cache.clear()
    surf = fonts[font_name].render(text, True, color)
    cache[key] = surf
    return surf

def get_entry_colors(e):
    # Default colors (muted dark)
    bg = (30, 31, 35)
    border = (48, 50, 58)
    txt_col = (200, 200, 205)
    
    color_type = e.get('color_type', 'system')
    if color_type == 'system':
        bg = (18, 42, 28)
        border = (30, 75, 48)
        txt_col = (110, 222, 142)
    elif color_type == 'hidden':
        bg = (10, 25, 50)
        border = (20, 50, 100)
        txt_col = (100, 181, 246) # Blue (Hidden)
    elif color_type == 'revealed':
        bg = (10, 25, 50)
        border = (20, 50, 100)
        txt_col = (100, 181, 246) # Blue (Hidden)
    elif color_type == 'fakeout':
        bg = (52, 34, 16)
        border = (95, 62, 24)
        txt_col = (255, 183, 77) # Orange (Fakeout)
    elif color_type in ('next_cancelled', 'draft_normal', 'draft_hidden', 'draft_fakeout'):
        bg = (48, 24, 24)
        border = (85, 42, 42)
        txt_col = (229, 115, 115) # Red (Desistir / Draft)
    elif color_type == 'next':
        bg = (48, 42, 18)
        border = (85, 75, 30)
        txt_col = (255, 213, 79) # #FFD54F
    elif color_type == 'white_move':
        bg = (32, 36, 44)
        border = (54, 62, 76)
        txt_col = (235, 230, 220)
    elif color_type == 'black_move':
        bg = (22, 25, 30)
        border = (38, 42, 50)
        txt_col = (175, 175, 180)
    return bg, border, txt_col

async def ask_promo(screen, fonts, player_col, websocket, client_state):
    opts = ['Q', 'R', 'B', 'N']
    bw, bh = 84, 84
    gap = 14
    tw = len(opts) * (bw + gap) - gap
    sx = (BOARD_PX - tw) // 2
    sy = (BOARD_PX - bh) // 2
    ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 170))
    screen.blit(ov, (0, 0))
    boxes = []
    for i, o in enumerate(opts):
        x = sx + i * (bw + gap)
        rect = pygame.Rect(x, sy, bw, bh)
        boxes.append((rect, o))
        draw_rect_aa(screen, (245, 238, 220), rect, 8)
        draw_rect_aa(screen, (120, 90, 60), rect, 8, 2)
        piece_key = player_col + o
        if piece_key in IMAGES:
            promo_img = pygame.transform.smoothscale(IMAGES[piece_key], (min(bw-20, SQ), min(bh-20, SQ)))
            screen.blit(promo_img, promo_img.get_rect(center=rect.center))
        else:
            g = fonts['promo'].render(GLYPHS[piece_key], True, (30, 30, 30))
            screen.blit(g, g.get_rect(center=rect.center))
    pygame.display.flip()

    while True:
        if websocket is not None:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                client_state['msg_queue'].append(msg)
            except asyncio.TimeoutError:
                pass

        for ev in pygame.event.get():
            if ev.type == pygame.MOUSEBUTTONDOWN:
                for rect, o in boxes:
                    if rect.collidepoint(ev.pos): return o

        await asyncio.sleep(0)

def check_has_real_draft(draft_moves):
    if not draft_moves:
        return False
    start_i = 0
    for i in range(len(draft_moves)-1, -1, -1):
        if draft_moves[i].get('type') == 'end_turn':
            start_i = i + 1
            break
    cur_dm = draft_moves[start_i:]
    return any((m.get('type') == 'move' and not m.get('fakeout', False)) for m in cur_dm)

def check_draft_endable(draft_moves, base_end_en):
    if not draft_moves:
        return base_end_en
    start_i = 0
    for i in range(len(draft_moves)-1, -1, -1):
        if draft_moves[i].get('type') == 'end_turn':
            start_i = i + 1
            break
    cur_dm = draft_moves[start_i:]
    if not cur_dm:
        has_any_real = any((m.get('type') == 'move' and not m.get('fakeout', False)) for m in draft_moves)
        return base_end_en or has_any_real
    return any((m.get('type') == 'move' and not m.get('fakeout', False)) for m in cur_dm)

def get_trail_points(p1, p2, flipped, SQ):
    fr_disp = 7 - p1[0] if flipped else p1[0]
    fc_disp = 7 - p1[1] if flipped else p1[1]
    tr_disp = 7 - p2[0] if flipped else p2[0]
    tc_disp = 7 - p2[1] if flipped else p2[1]
    
    start_pos = (fc_disp * SQ + SQ // 2, fr_disp * SQ + SQ // 2)
    end_pos = (tc_disp * SQ + SQ // 2, tr_disp * SQ + SQ // 2)
    
    dr = abs(p2[0] - p1[0])
    dc = abs(p2[1] - p1[1])
    
    if (dr == 2 and dc == 1) or (dr == 1 and dc == 2):
        if dr == 2:
            mid_p = (p2[0], p1[1])
        else:
            mid_p = (p1[0], p2[1])
        mid_r_disp = 7 - mid_p[0] if flipped else mid_p[0]
        mid_c_disp = 7 - mid_p[1] if flipped else mid_p[1]
        mid_pos = (mid_c_disp * SQ + SQ // 2, mid_r_disp * SQ + SQ // 2)
        return [start_pos, mid_pos, end_pos]
    return [start_pos, end_pos]

def draw_board(screen, gs, fonts, client_state, mouse):
    turn = gs['turn']
    board = gs['board']
    flipped = client_state['flipped']
    sel = client_state['selected']
    legal_set = set(map(tuple, client_state['legal_sq']))
    last = gs['last_move']
    
    # Vision is always active when game is over or in replay mode
    is_ended = gs.get('game_over', False) or client_state.get('is_replay', False) or client_state.get('reconnected_game_over', False)
    show = not client_state.get('hide_mechanics_ui', False) or is_ended
    
    my_color = client_state['my_color']
    if my_color == 'spectator':
        my_hidden = {}
    else:
        my_hidden = gs['hidden_w'] if my_color == 'w' else gs['hidden_b']
    is_drafting = client_state.get('drafting', False)
    fmode = (client_state.get('draft_fakeout', False) if is_drafting else gs.get('fakeout_active', False)) or client_state.get('fakeout_triggered', False)
    hmode = ((client_state.get('draft_hidden', False) if is_drafting else gs.get('hidden_mode', False)) or client_state.get('hidden_triggered', False)) and not fmode

    if client_state.get('history_active'):
        active_idx = client_state.get('history_index', 0)
        hist = client_state.get('turn_history', [])
        live_gs = hist[-1] if hist else gs
        
        # Apply the trail rendering on the block BEFORE the shadow move (active_idx + 1 logic)
        if (active_idx + 1) in live_gs.get('shadow_history', {}):
            show = True
            info = live_gs['shadow_history'][active_idx + 1]
            c_color = info.get('color', my_color)
            if (active_idx + 1) < len(hist):
                next_gs = hist[active_idx + 1]
                my_hidden = next_gs['hidden_w'] if c_color == 'w' else next_gs['hidden_b']

    abs_b = get_absolute_board(gs)
    tb = get_true_board(gs, my_color)
    if client_state.get('history_active'):
        curr_dgs = gs
    else:
        try:
            curr_dgs = get_draft_state(gs, client_state.get('draft_moves', []), client_state.get('my_color')) if client_state.get('drafting') else gs
        except Exception:
            curr_dgs = gs
    curr_b = [r[:] for r in curr_dgs['board']]
    render_grid = BoardRenderer.get_render_state(gs, client_state, abs_b, tb, my_hidden, show, curr_b)

    mx, my = mouse
    hover_r, hover_c = -1, -1
    if my < BOARD_PX and mx < BOARD_PX:
        hover_c = mx // SQ
        hover_r = my // SQ
        if flipped:
            hover_r = 7 - hover_r
            hover_c = 7 - hover_c

    has_custom_board = 'board' in IMAGES
    if has_custom_board:
        board_img = IMAGES['board']
        screen.blit(board_img, (0, 0))

    for rr in range(8):
        for cc in range(8):
            r = 7 - rr if flipped else rr
            c = 7 - cc if flipped else cc
            x, y = cc * SQ, rr * SQ
            cell = render_grid[r][c]
            base = LIGHT if (r + c) % 2 == 0 else DARK
            if not has_custom_board:
                pygame.draw.rect(screen, base, (x, y, SQ, SQ))
            if cell.is_frozen:
                dark_surf = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                dark_surf.fill((0, 0, 0, 204)) # 80% darker
                screen.blit(dark_surf, (x, y))
            
            fade_t = client_state.get('fill_fade_timer', 0.0)

            if hover_r == r and hover_c == c:
                if not client_state.get('is_dragging_gesture'):
                    hover_surf = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                    hover_surf.fill((255, 255, 255, 40) if (hmode or fmode) else (255, 255, 255, 60))
                    screen.blit(hover_surf, (x, y))

            if cell.is_last_move:
                hl = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                hl.fill((*C_LAST, 100))
                screen.blit(hl, (x, y))

            if cell.is_check:
                pygame.draw.rect(screen, C_CHECK, (x, y, SQ, SQ))

            if cell.is_selected:
                pygame.draw.rect(screen, C_SEL, (x, y, SQ, SQ))
                # Pulsa a borda do quadrado selecionado
                pulse = (math.sin(pygame.time.get_ticks() / 150.0) + 1.0) / 2.0
                pulse_thickness = 2 + int(pulse * 3)
                pygame.draw.rect(screen, (220, 240, 200), (x+1, y+1, SQ-2, SQ-2), pulse_thickness)
                
            fade_t = client_state.get('fill_fade_timer', 0.0)
            if fade_t > 0 and 'fade_squares' in client_state:
                for f_r, f_c, col, alpha, is_border in client_state['fade_squares']:
                    if f_r == r and f_c == c:
                        surf = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                        if is_border:
                            pygame.draw.rect(surf, (*col, int(alpha * fade_t)), (0, 0, SQ, SQ), 3)
                        else:
                            surf.fill((*col, int(alpha * fade_t)))
                        screen.blit(surf, (x, y))

            if cell.is_legal and not cell.is_legal_capture:
                ds = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                pygame.draw.circle(ds, (0, 0, 0, 65), (SQ // 2, SQ // 2), SQ // 7)
                screen.blit(ds, (x, y))
            elif cell.is_legal_capture:
                ds = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                pygame.draw.circle(ds, (0, 0, 0, 65), (SQ // 2, SQ // 2), SQ // 2 - 4, 6)
                screen.blit(ds, (x, y))

            # Draw blue/orange ink trail on the path if show is True


    if client_state.get('is_dragging_gesture') and hover_r >= 0 and hover_c >= 0:
        cc_h = 7 - hover_c if flipped else hover_c
        rr_h = 7 - hover_r if flipped else hover_r
        x_h, y_h = cc_h * SQ, rr_h * SQ
        r_orig = SQ // 2 - 2
        r_new = SQ
        shadow_surf = pygame.Surface((r_new * 2, r_new * 2), pygame.SRCALPHA)
        pygame.draw.circle(shadow_surf, (0, 0, 0, 115), (r_new, r_new), r_new)
        screen.blit(shadow_surf, (x_h + SQ // 2 - r_new, y_h + SQ // 2 - r_new))

    if last:
        fr, fc, tr, tc = last
        pts = get_trail_points((fr, fc), (tr, tc), flipped, SQ)
        arrow_surf = pygame.Surface((WIN_W, BOARD_PX), pygame.SRCALPHA)
        for i in range(len(pts) - 1):
            pygame.draw.line(arrow_surf, (*C_LAST, 140), pts[i], pts[i+1], 5)
        pygame.draw.circle(arrow_surf, (*C_LAST, 140), pts[0], 6)
        screen.blit(arrow_surf, (0, 0))

    if show:
        for t_pos, val in my_hidden.items():
            is_f = val.is_fakeout
            hidden_path = val.path
            fakeout_path = val.fakeout_path

            # 1. Draw hidden pathway (always blue)
            if hidden_path and len(hidden_path) > 1:
                N = len(hidden_path)
                trail_surf = pygame.Surface((WIN_W, BOARD_PX), pygame.SRCALPHA)
                for i in range(N - 1):
                    p1 = hidden_path[i]
                    p2 = hidden_path[i + 1]
                    
                    pts = get_trail_points(p1, p2, flipped, SQ)
                    start_pos = pts[0]
                    end_pos = pts[-1]
                    
                    ratio = (i + 1) / (N - 1)
                    line_alpha = int(45 + 135 * ratio)
                    color = (30, 110, 255, line_alpha)
                    
                    for j in range(len(pts) - 1):
                        pygame.draw.line(trail_surf, color, pts[j], pts[j+1], 4)
                        if j > 0:
                            pygame.draw.circle(trail_surf, color, pts[j], 4)
                    
                    pygame.draw.circle(trail_surf, color, start_pos, 5)
                    if i == N - 2:
                        pygame.draw.circle(trail_surf, color, end_pos, 5)
                        
                screen.blit(trail_surf, (0, 0))

            # 2. Draw fakeout pathway (always orange)
            if is_f:
                f_path = fakeout_path if fakeout_path else hidden_path
                if f_path and len(f_path) > 1:
                    N = len(f_path)
                    trail_surf = pygame.Surface((WIN_W, BOARD_PX), pygame.SRCALPHA)
                    for i in range(N - 1):
                        p1 = f_path[i]
                        p2 = f_path[i + 1]
                        
                        pts = get_trail_points(p1, p2, flipped, SQ)
                        start_pos = pts[0]
                        end_pos = pts[-1]
                        
                        ratio = (i + 1) / (N - 1)
                        line_alpha = int(45 + 135 * ratio)
                        color = (245, 120, 20, line_alpha)
                        
                        for j in range(len(pts) - 1):
                            pygame.draw.line(trail_surf, color, pts[j], pts[j+1], 4)
                            if j > 0:
                                pygame.draw.circle(trail_surf, color, pts[j], 4)
                        
                        pygame.draw.circle(trail_surf, color, start_pos, 5)
                        if i == N - 2:
                            pygame.draw.circle(trail_surf, color, end_pos, 5)
                            
                    screen.blit(trail_surf, (0, 0))

    draft_sequences_to_draw = []
    
    if client_state.get('draft_moves'):
        draft_sequences_to_draw.append([m for m in client_state['draft_moves'] if m.get('type') == 'move'])
        
    my_color = client_state.get('my_color', 'w')
    
    if not client_state.get('draft_moves') and gs.get(f'next_queue_{my_color}'):
        draft_sequences_to_draw.append([m for m in gs[f'next_queue_{my_color}'] if m.get('type') == 'move'])
        
    opp_color = 'b' if my_color == 'w' else 'w'
    if gs.get(f'next_queue_{opp_color}'):
        draft_sequences_to_draw.append([m for m in gs[f'next_queue_{opp_color}'] if m.get('type') == 'move'])

    for d_moves in draft_sequences_to_draw:
        N = len(d_moves)
        if N > 0:
            trail_surf = pygame.Surface((WIN_W, BOARD_PX), pygame.SRCALPHA)
            for i, d_move in enumerate(d_moves):
                p1 = (d_move['fr'], d_move['fc'])
                p2 = (d_move['tr'], d_move['tc'])
                
                pts = get_trail_points(p1, p2, flipped, SQ)
                start_pos = pts[0]
                end_pos = pts[-1]
                
                ratio = (i + 1) / N
                line_alpha = int(45 + 135 * ratio)
                color = (235, 45, 45, line_alpha)
                
                for j in range(len(pts) - 1):
                    pygame.draw.line(trail_surf, color, pts[j], pts[j+1], 4)
                    if j > 0:
                        pygame.draw.circle(trail_surf, color, pts[j], 4)
                
                pygame.draw.circle(trail_surf, color, start_pos, 5)
                pygame.draw.circle(trail_surf, color, end_pos, 5)
            screen.blit(trail_surf, (0, 0))

    for rr in range(8):
        for cc in range(8):
            r = 7 - rr if flipped else rr
            c = 7 - cc if flipped else cc
            x, y = cc * SQ, rr * SQ
            cell = render_grid[r][c]

            p = cell.piece
            if client_state.get('is_dragging_gesture') and client_state.get('drag_piece_sq') == (r, c):
                p = None
            if p:
                if p in IMAGES:
                    img = IMAGES[p]
                    if cell.ghost_alpha < 255:
                        img = img.copy()
                        img.set_alpha(cell.ghost_alpha)
                    screen.blit(img, (x, y))
                else:
                    pc_col = (255, 255, 255) if pc(p) == 'w' else (25, 25, 25)
                    ps = fonts['piece'].render(GLYPHS[p], True, pc_col)
                    if cell.ghost_alpha < 255:
                        ps.set_alpha(cell.ghost_alpha)
                    screen.blit(ps, ps.get_rect(center=(x + SQ // 2, y + SQ // 2)))
                
                # --- ICE KING: Frozen piece indicator ---
                if cell.is_frozen:
                    from renderer import VisualEffectsRenderer
                    t_sec = pygame.time.get_ticks() / 1000.0
                    VisualEffectsRenderer.draw_freeze_overlay(screen, r, c, x, y, SQ, t_sec)
                # ----------------------------------------
                


            hp = cell.ghost_piece
            if hp and show:
                animating_here = False
                if client_state.get('anim'):
                    a = client_state['anim']
                    if a['tr'] == r and a['tc'] == c and a['p'] == my_hidden[(r, c)].piece:
                        animating_here = True
                
                if not animating_here:
                    val = my_hidden[(r, c)]
                    is_f = val.is_fakeout
                    overlay_col = C_FAKEOUT if is_f else C_HIDDEN
                    aura_surf = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                    if hp in IMAGES:
                        img_hp = IMAGES[hp].copy()
                        mask = pygame.mask.from_surface(img_hp)
                        sil = mask.to_surface(setcolor=(*overlay_col, 255), unsetcolor=(0, 0, 0, 0))
                        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                            aura_surf.blit(sil, (dx, dy))
                        aura_surf.blit(img_hp, (0, 0))
                    else:
                        pc_col = (255, 255, 255) if pc(hp) == 'w' else (25, 25, 25)
                        aura_text = fonts['piece'].render(GLYPHS[hp], True, overlay_col)
                        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                            aura_surf.blit(aura_text, aura_text.get_rect(center=(SQ // 2 + dx, SQ // 2 + dy)))
                        nps = fonts['piece'].render(GLYPHS[hp], True, pc_col)
                        aura_surf.blit(nps, nps.get_rect(center=(SQ // 2, SQ // 2)))
                    
                    aura_surf.set_alpha(76)
                    screen.blit(aura_surf, (x, y))

            if cell.is_next_dest and cell.next_dest_piece:
                next_p = cell.next_dest_piece
                aura_surf = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                if next_p in IMAGES:
                    img_next = IMAGES[next_p].copy()
                    mask = pygame.mask.from_surface(img_next)
                    red_sil = mask.to_surface(setcolor=(239, 68, 68, 255), unsetcolor=(0, 0, 0, 0))
                    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                        aura_surf.blit(red_sil, (dx, dy))
                    aura_surf.blit(img_next, (0, 0))
                else:
                    next_pc_col = (255, 255, 255) if pc(next_p) == 'w' else (25, 25, 25)
                    aura_text = fonts['piece'].render(GLYPHS[next_p], True, (239, 68, 68))
                    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                        aura_surf.blit(aura_text, aura_text.get_rect(center=(SQ // 2 + dx, SQ // 2 + dy)))
                    nps = fonts['piece'].render(GLYPHS[next_p], True, next_pc_col)
                    aura_surf.blit(nps, nps.get_rect(center=(SQ // 2, SQ // 2)))
                
                aura_surf.set_alpha(120)
                screen.blit(aura_surf, (x, y))

            if 'flashes' in client_state and (r, c) in client_state['flashes']:
                val_flash = client_state['flashes'][(r, c)]
                if isinstance(val_flash, dict):
                    flash_time = val_flash['t']
                    flash_color = val_flash.get('color', (235, 45, 45))
                else:
                    flash_time = val_flash
                    flash_color = (235, 45, 45)
                blink_duration = 0.18
                current_blink = int(flash_time / blink_duration)
                if current_blink < 2:
                    t = flash_time % blink_duration
                    p = t / blink_duration
                    # Smooth glowing rising and fading beautifully
                    alpha = int(225 * math.sin(p * math.pi))
                    alpha = max(0, min(255, alpha))
                    if alpha > 0:
                        flash_surf = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                        flash_surf.fill((*flash_color, alpha))
                        screen.blit(flash_surf, (x, y))

            cc2 = DARK if (r + c) % 2 == 0 else LIGHT
            if rr == 7:
                f = fonts['coord'].render('abcdefgh'[7 - cc if flipped else cc], True, cc2)
                screen.blit(f, (x + SQ - f.get_width() - 3, y + SQ - f.get_height() - 2))
            if cc == 0:
                rv = fonts['coord'].render(str(rr + 1 if flipped else 8 - rr), True, cc2)
                screen.blit(rv, (x + 3, y + 3))

    if client_state.get('anim'):
        a = client_state['anim']
        fr, fc = 7 - a['fr'] if flipped else a['fr'], 7 - a['fc'] if flipped else a['fc']
        tr, tc = 7 - a['tr'] if flipped else a['tr'], 7 - a['tc'] if flipped else a['tc']
        
        start_x, start_y = fc * SQ, fr * SQ
        end_x, end_y = tc * SQ, tr * SQ
        
        progress = min(1.0, a['t'] / a['dur'])
        # Simple ease out curve
        ease = 1.0 - (1.0 - progress) ** 3
        
        pts_center = get_trail_points((a['fr'], a['fc']), (a['tr'], a['tc']), flipped, SQ)
        pts = [(px - SQ // 2, py - SQ // 2) for px, py in pts_center]
        
        def interpolate_pts(pts, t):
            if len(pts) == 2:
                return pts[0][0] + (pts[1][0] - pts[0][0]) * t, pts[0][1] + (pts[1][1] - pts[0][1]) * t
            
            d1 = abs(pts[1][0] - pts[0][0]) + abs(pts[1][1] - pts[0][1])
            d2 = abs(pts[2][0] - pts[1][0]) + abs(pts[2][1] - pts[1][1])
            t_mid = d1 / (d1 + d2) if (d1 + d2) > 0 else 0.5
            
            if t <= t_mid:
                p_t = t / t_mid if t_mid > 0 else 0
                return pts[0][0] + (pts[1][0] - pts[0][0]) * p_t, pts[0][1] + (pts[1][1] - pts[0][1]) * p_t
            else:
                p_t = (t - t_mid) / (1.0 - t_mid) if t_mid < 1 else 0
                return pts[1][0] + (pts[2][0] - pts[1][0]) * p_t, pts[1][1] + (pts[2][1] - pts[1][1]) * p_t

        cur_x, cur_y = interpolate_pts(pts, ease)
        
        p = a['p']
        pc_col = (255, 255, 255) if pc(p) == 'w' else (25, 25, 25)
        
        # Motion blur trail
        trail_steps = 5
        for step in range(1, trail_steps + 1):
            t_progress = max(0.0, progress - (step * 0.04))
            t_ease = 1.0 - (1.0 - t_progress) ** 3
            tx, ty = interpolate_pts(pts, t_ease)
            
            trail_alpha = int(140 * (1.0 - (step / trail_steps)))
            if p in IMAGES:
                trail_img = IMAGES[p].copy()
                trail_img.set_alpha(trail_alpha)
                screen.blit(trail_img, (tx, ty))
                if a.get('is_hidden') or a.get('is_fakeout'):
                    is_h, is_f = a.get('is_hidden'), a.get('is_fakeout')
                    MechanicsManager.draw_modifier_glow(screen, tx, ty, SQ, is_h, is_f, multiplier=trail_alpha * 0.55 / 45)
            else:
                ts = fonts['piece'].render(GLYPHS[p], True, pc_col)
                ts.set_alpha(trail_alpha)
                screen.blit(ts, ts.get_rect(center=(tx + SQ // 2, ty + SQ // 2)))
                if a.get('is_hidden') or a.get('is_fakeout'):
                    is_h, is_f = a.get('is_hidden'), a.get('is_fakeout')
                    MechanicsManager.draw_modifier_text_glow(screen, fonts, GLYPHS[p], pc_col, tx, ty, SQ, is_h, is_f, trail_alpha=trail_alpha)

        if p in IMAGES:
            screen.blit(IMAGES[p], (cur_x, cur_y))
            if a.get('is_hidden') or a.get('is_fakeout'):
                is_h, is_f = a.get('is_hidden'), a.get('is_fakeout')
                MechanicsManager.draw_modifier_glow(screen, cur_x, cur_y, SQ, is_h, is_f)
        else:
            ps = fonts['piece'].render(GLYPHS[p], True, pc_col)
            screen.blit(ps, ps.get_rect(center=(cur_x + SQ // 2, cur_y + SQ // 2)))
            if a.get('is_hidden') or a.get('is_fakeout'):
                is_h, is_f = a.get('is_hidden'), a.get('is_fakeout')
                MechanicsManager.draw_modifier_text_glow(screen, fonts, GLYPHS[p], pc_col, cur_x, cur_y, SQ, is_h, is_f)

    if client_state.get('particles'):
        for p in client_state['particles']:
            alpha = int(255 * (p['life'] / p['max_life']))
            size = max(1, int(p['size'] * (p['life'] / p['max_life'])))
            psurf = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
            pygame.draw.circle(psurf, (*p['color'], alpha), (size, size), size)
            screen.blit(psurf, (int(p['x'] - size), int(p['y'] - size)))

    if client_state.get('is_dragging_gesture') and 'drag_pos' in client_state:
        mx, my = client_state['drag_pos']
        p = client_state.get('drag_piece_name')
        if p:
            is_fake = client_state.get('fakeout_triggered', False) or gs.get('fakeout_active', False) or client_state.get('draft_fakeout', False)
            is_hid = client_state.get('hidden_triggered', False) or gs.get('hidden_mode', False) or client_state.get('draft_hidden', False)

            
            piece_top = my - SQ
            if p in IMAGES:
                img = IMAGES[p]
                vx, vy = client_state.get('drag_vel', (0.0, 0.0))
                angle = vx * 1.5
                angle = max(-35, min(35, angle))
                scaled_img = pygame.transform.rotozoom(img, angle, 2.5)
                rect = scaled_img.get_rect(midbottom=(mx, my))
                screen.blit(scaled_img, rect)
                piece_top = rect.top
            else:
                pc_col = (255, 255, 255) if pc(p) == 'w' else (25, 25, 25)
                ps = fonts['piece'].render(GLYPHS.get(p, p), True, pc_col)
                rect = ps.get_rect(midbottom=(mx, my))
                screen.blit(ps, rect)
                piece_top = rect.top
                
            is_auto_fakeout = client_state.get('casca_auto_fakeout', False)
            hold_p = 1.0 if is_auto_fakeout else min(1.0, client_state.get('gesture_timer', 0.0) / 3.5)
            is_hid = client_state.get('hidden_triggered', False) or gs.get('hidden_mode', False) or client_state.get('draft_hidden', False)
            is_fake = client_state.get('fakeout_triggered', False) or gs.get('fakeout_active', False) or client_state.get('draft_fakeout', False)
            
            if hold_p > 0.01:
                bar_w = 240
                bar_h = 15
                bar_x = mx - bar_w // 2
                bar_y = piece_top - bar_h - 5
                bar_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
                pygame.draw.rect(bar_surf, (30, 30, 30, 153), (0, 0, bar_w, bar_h), border_radius=2)
                
                pulse = (math.sin(pygame.time.get_ticks() / 150.0) + 1) / 2
                
                if is_fake:
                    # Pulsing orange
                    fill_color = (255, int(120 + 80 * pulse), int(50 * pulse), 153)
                elif client_state.get('gesture_stalled'):
                    if is_hid:
                        # Pulsing blue
                        fill_color = (int(80 * pulse), int(150 + 80 * pulse), 255, 153)
                    else:
                        # Pulsing red
                        fill_color = (255, int(100 * pulse), int(100 * pulse), 153)
                elif is_hid:
                    # Solid blue
                    fill_color = (100, 150, 255, 153)
                else:
                    # Solid white
                    fill_color = (255, 255, 255, 153)
                    
                pygame.draw.rect(bar_surf, fill_color, (0, 0, int(bar_w * hold_p), bar_h), border_radius=2)
                screen.blit(bar_surf, (bar_x, bar_y))
            
            if is_hid or is_fake:
                if 'flame_particles' not in client_state:
                    client_state['flame_particles'] = []
                vx, vy = client_state.get('drag_vel', (0.0, 0.0))
                c_type = 'orange' if is_fake else 'blue'
                for _ in range(2):
                    px = mx + random.randint(-SQ//2, SQ//2)
                    py = my - random.randint(0, SQ)
                    client_state['flame_particles'].append(FlameParticle(px, py, r=random.randint(4, 7), vx=vx, vy=vy, color_type=c_type))
    if client_state.get('flame_particles'):
        for p in client_state['flame_particles']:
            p.update()
            p.draw(screen)
        client_state['flame_particles'] = [p for p in client_state['flame_particles'] if p.r > 1]
    if client_state.get('shockwaves'):
        sw_surf = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
        for sw in client_state['shockwaves']:
            progress = sw['t'] / sw['duration']
            # Explosive easing function
            e_progress = 1.0 - (1.0 - progress)**4
            radius = int(5 + (sw['max_radius'] - 5) * e_progress)
            
            # Vibrant fade-out alpha curve
            alpha = int(245 * (1.0 - progress)**1.5)
            if alpha < 0: alpha = 0
            
            # Color logic
            type = sw.get('type')
            is_hidden_sw = type == 'hidden'
            is_fakeout_sw = type == 'fakeout'
            
            if is_hidden_sw:
                c1, c2, c3, c4, c5 = (30, 100, 235), (40, 110, 255), (210, 230, 255), (15, 75, 185), (80, 150, 255)
            elif is_fakeout_sw:
                c1, c2, c3, c4, c5 = (235, 100, 30), (255, 110, 40), (255, 230, 210), (185, 75, 15), (255, 150, 80)
            else:
                c1, c2, c3, c4, c5 = (30, 235, 100), (40, 255, 110), (210, 255, 230), (15, 185, 75), (80, 255, 150)
            
            # 1. Base vibrant ambient glow
            pygame.draw.circle(sw_surf, (*c1[:3], int(0.22 * alpha)), (sw['cx'], sw['cy']), radius)
            
            # 2. Main neon shock ring
            ring_w = max(2, int(22 * (1.0 - progress)))
            if radius > ring_w:
                pygame.draw.circle(sw_surf, (*c2[:3], alpha), (sw['cx'], sw['cy']), radius, ring_w)
            else:
                pygame.draw.circle(sw_surf, (*c2[:3], alpha), (sw['cx'], sw['cy']), radius)
                
            # 3. Secondary hot white-leading-edge ring
            lead_progress = min(1.0, progress * 1.06)
            e_lead = 1.0 - (1.0 - lead_progress)**4
            lead_radius = int(5 + (sw['max_radius'] - 5) * e_lead)
            lead_alpha = int(alpha * 0.7)
            lead_ring_w = max(1, int(5 * (1.0 - lead_progress)))
            if lead_radius > lead_ring_w:
                pygame.draw.circle(sw_surf, (*c3[:3], lead_alpha), (sw['cx'], sw['cy']), lead_radius, lead_ring_w)
                
            # 4. Third trailing deep energetic wave
            trail_progress = max(0.0, progress - 0.12) / 0.88
            e_trail = 1.0 - (1.0 - trail_progress)**2
            trail_radius = int(5 + (sw['max_radius'] - 5) * e_trail)
            trail_alpha = int(alpha * 0.45)
            trail_ring_w = max(1, int(26 * (1.0 - trail_progress)))
            if trail_radius > trail_ring_w:
                pygame.draw.circle(sw_surf, (*c4[:3], trail_alpha), (sw['cx'], sw['cy']), trail_radius, trail_ring_w)

            # 5. Radiating high-speed energy spikes
            num_spikes = 16
            for i in range(num_spikes):
                angle = (i * 2.0 * math.pi) / num_spikes
                cos_a = math.cos(angle)
                sin_a = math.sin(angle)
                
                sp_start = int(radius * 0.78)
                sp_end = int(radius * 1.04)
                
                x1 = int(sw['cx'] + cos_a * sp_start)
                y1 = int(sw['cy'] + sin_a * sp_start)
                x2 = int(sw['cx'] + cos_a * sp_end)
                y2 = int(sw['cy'] + sin_a * sp_end)
                
                spike_alpha = int(alpha * 0.6)
                spike_w = max(1, int(3 * (1.0 - progress)))
                pygame.draw.line(sw_surf, (*c5[:3], spike_alpha), (x1, y1), (x2, y2), spike_w)
                
        screen.blit(sw_surf, (0, 0))

    from renderer import VisualEffectsRenderer
    VisualEffectsRenderer.draw_active_freeze_effects(screen, client_state, SQ, BOARD_PX)

def draw_panel(screen, gs, fonts, mouse, client_state):
    pygame.draw.rect(screen, PANEL_BG, (0, BOARD_PX, BOARD_PX, PANEL_H))
    pygame.draw.line(screen, (40, 40, 45), (0, BOARD_PX), (BOARD_PX, BOARD_PX), 2)

    turn = gs['turn']
    my_color = client_state['my_color']
    fmode = MechanicsManager.is_fakeout_on(gs, client_state) or client_state.get('fakeout_triggered', False)
    hmode = (MechanicsManager.is_hidden_on(gs, client_state) or client_state.get('hidden_triggered', False)) and not fmode

    turn_hist = client_state.get('turn_history', [])
    total_plys = len(turn_hist)
    active_idx = client_state.get('history_index', 0)
    history_active = total_plys > 0 and active_idx < total_plys - 1

    if history_active:
        status = f"HISTÓRICO: Lance {active_idx} de {total_plys - 1}"
        sc = (160, 160, 160)
    elif client_state['waiting']:
        if client_state.get('reconnected_game_over'):
            status = "Fim de Jogo"
            sc = T_RED
        else:
            status = "Aguardando Oponente..."
            sc = T_RED
    elif gs['game_over']:
        if client_state.get('export_success_msg'):
            status = client_state['export_success_msg']
            sc = (110, 220, 110)
        else:
            status = gs['game_over_msg']
            sc = T_RED
    elif turn != my_color:
        status = "Vez do oponente"
        sc = T_DIM
    elif hmode:
        status = 'Sua vez'
        sc = (100, 181, 246)
    elif fmode:
        status = 'Sua vez'
        sc = (245, 120, 20)
    elif gs['normal_done']:
        if client_state.get('predicting_mode'):
            status = 'Predicting...'
            sc = (255, 235, 59)
        else:
            status = 'Drafting...'
            sc = (229, 115, 115)
    else:
        status = 'Sua vez'
        sc = T_MAIN

    last_status = client_state.get('last_status', None)
    if status == 'Sua vez' and last_status != 'Sua vez':
        play_sound('toggle')
    client_state['last_status'] = status

    st = fonts['big'].render(status, True, sc)
    st_rect = st.get_rect(midleft=(15, BOARD_PX + 28))
    pill_rect = st_rect.inflate(24, 12)

    draw_rect_aa(screen, (20, 20, 24), pill_rect, 12)
    if hmode:
        draw_rect_aa(screen, (80, 120, 220), pill_rect, 12, 1)
    elif fmode:
        draw_rect_aa(screen, (245, 120, 20), pill_rect, 12, 1)
    elif gs['normal_done']:
        if client_state.get('predicting_mode'):
            draw_rect_aa(screen, (255, 235, 59), pill_rect, 12, 1)
        else:
            draw_rect_aa(screen, (229, 115, 115), pill_rect, 12, 1)
    elif turn == my_color and not client_state['waiting'] and not history_active:
        draw_rect_aa(screen, (80, 80, 90), pill_rect, 12, 1)
    screen.blit(st, st_rect)

    is_drafting = client_state.get('drafting', False)
    if (is_drafting or client_state.get('draft_moves')) and not history_active:
        try:
            pts_state = get_draft_state(gs, client_state.get('draft_moves', []), client_state.get('my_color'))
        except Exception:
            pts_state = gs
    else:
        pts_state = gs

    if my_color != 'spectator':
        my_pts = pts_state['pts'].get(my_color, 0)
        formatted_pts = str(int(my_pts)) if my_pts == int(my_pts) else f"{round(my_pts, 2)}"
        
        my_pts_rect = pygame.Rect(BOARD_PX - 130, BOARD_PX + 25, 115, 36)
        draw_rect_aa(screen, (100, 100, 105), my_pts_rect, 6, 1)
        
        pts_lbl = fonts['pts'].render(f"Pontos: {formatted_pts}", True, (150, 150, 150))
        screen.blit(pts_lbl, pts_lbl.get_rect(center=my_pts_rect.center))

    if client_state.get('draft_moves'):
        has_real_draft = check_has_real_draft(client_state['draft_moves'])
        log = gs['log'][-3:]
    else:
        log = gs['log'][-3:]
    log_rect = pygame.Rect(12, BOARD_PX + 42, BOARD_PX - 210, 50)
    draw_rect_aa(screen, (15, 15, 18), log_rect, 6)

    lx, ly = 20, BOARD_PX + 46
    
    raw_log = list(gs.get('log', []))
    clog = list(gs.get('classified_log', []))
    
    if not history_active and client_state.get('draft_moves'):
        from chess_logic import notation
        for idx, dm in enumerate(client_state['draft_moves']):
            if dm.get('type') == 'move':
                prev_moves = client_state['draft_moves'][:idx]
                try:
                    dgs_before = get_draft_state(gs, prev_moves, client_state.get('my_color'))
                    sr, sc = dm['fr'], dm['fc']
                    r, c = dm['tr'], dm['tc']
                    promo = dm.get('promo')
                    is_hid = dm.get('hidden', False)
                    is_fake = dm.get('fakeout', False)
                    try:
                        move_not = notation(dgs_before['board'], sr, sc, r, c, dgs_before.get('ep'), promo)
                    except Exception:
                        move_not = f"{alg(sc, sr)}->{alg(c, r)}"
                    prefix = ""
                    if is_hid:
                        prefix = "🟦 "
                    elif is_fake:
                        prefix = "🟧 "
                    
                    raw_log.append({'text': f"{prefix}{move_not}", 'color_type': 'draft_log'})
                except Exception:
                    break

    start_idx = max(0, len(raw_log) - 3)
    display_entries = []
    
    for i in range(start_idx, len(raw_log)):
        entry_raw = raw_log[i]
        c_entry = clog[i] if i < len(clog) else None
        
        if c_entry:
            text = c_entry['text']
            ct = c_entry.get('color_type', 'system')
        elif isinstance(entry_raw, dict):
            text = entry_raw.get('text', '')
            ct = entry_raw.get('color_type', 'system')
        else:
            text = str(entry_raw)
            ct = 'system'
            parts = text.split('|')
            if len(parts) >= 2:
                cmd = parts[0]
                if cmd == 'HIDDEN':
                    text = parts[2]
                    ct = 'hidden'
                elif cmd == 'FAKEOUT':
                    text = parts[2]
                    ct = 'fakeout'
                elif cmd == 'NEXT':
                    text = parts[2]
                    ct = 'next'
                elif cmd == 'NORMAL':
                    text = parts[2]
                elif cmd == 'SYS_HIDDEN':
                    text = parts[1]
                    ct = 'hidden'
                elif cmd == 'SYS_FAKEOUT':
                    text = parts[1]
                    ct = 'fakeout'
                elif cmd == 'PREDICT':
                    text = parts[1]
                    ct = 'predict'
                elif cmd == 'ICE':
                    text = parts[2]
                    ct = 'system'
                elif cmd == 'LOCAL_WARN':
                    text = parts[1]
                    ct = 'local_warn'
        display_entries.append((text, ct))

    for i, (text, ct) in enumerate(display_entries):
        a = 255 - (len(display_entries) - 1 - i) * 60
        cl = (a, a, a) # System lines fade into gray
        
        # Draw custom colored squares instead of emoji characters to support all fonts/platforms
        offset_x = 0
        remaining_text = text
        if text.startswith("🟦 "):
            # Blue square
            rect_y = ly + i * 14 + 2
            rect_x = lx
            pygame.draw.rect(screen, (33, 150, 243), (rect_x, rect_y, 10, 10), border_radius=2)
            offset_x = 16
            remaining_text = text[2:]
        elif text.startswith("🟧 "):
            # Orange square
            rect_y = ly + i * 14 + 2
            rect_x = lx
            pygame.draw.rect(screen, (255, 152, 0), (rect_x, rect_y, 10, 10), border_radius=2)
            offset_x = 16
            remaining_text = text[2:]

        if ct in ('next_cancelled', ) or "Lance inválido" in text or "Sequência quebrada" in text or "Lance abandonado" in text:
            cl = (229, 115, 115) # Red (#E57373)
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))
        elif ct == 'draft_log':
            cl = (235, 125, 125) # Light/soft red
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))
        elif ct == 'local_warn':
            cl = (245, 160, 50) # Thematic orange
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))
        elif ct == 'predict':
            cl = (255, 235, 59)
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))
        elif ct in ('hidden', 'revealed'):
            cl = (100, 181, 246) # Blue (#64B5F6)
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))
        elif ct == 'fakeout':
            cl = (255, 183, 77) # Orange (#FFB74D)
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))
        elif ct == 'next':
            cl = (255, 213, 79) # Yellow (#FFD54F)
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))
        else:
            ls = fonts['small'].render(remaining_text, True, cl)
            screen.blit(ls, (lx + offset_x, ly + i * 14))

    by2 = BOARD_PX + 112
    bh = 32
    btns = {}

    def draw_eye_btn(x, w, key, is_enabled, is_active, base_color, hover_color, show_eye, y_override=None):
        y_pos = y_override if y_override is not None else by2
        rect = pygame.Rect(x, y_pos, w, bh)
        is_hover = rect.collidepoint(mouse) and is_enabled
        if is_hover or is_active:
            rect.y += 1
        
        draw_fancy_btn(screen, "", fonts['ui'], base_color, hover_color, BTN_TXT, rect, is_hover=is_hover, is_disabled=not is_enabled, custom_radius=6)
        
        cx, cy = rect.center
        if show_eye:
            pygame.draw.ellipse(screen, (200, 200, 200), (cx - 10, cy - 6, 20, 12), 2)
            pygame.draw.circle(screen, (200, 200, 200), (cx, cy), 3)
        else:
            pygame.draw.ellipse(screen, (200, 200, 200), (cx - 10, cy - 6, 20, 12), 2)
            pygame.draw.circle(screen, (200, 200, 200), (cx, cy), 3)
            pygame.draw.line(screen, (200, 200, 200), (cx - 12, cy - 8), (cx + 12, cy + 8), 3)
        btns[key] = rect

    def draw_chat_btn(x, w, key, is_enabled, y_override=None):
        y_pos = y_override if y_override is not None else by2
        rect = pygame.Rect(x, y_pos, w, bh)
        is_hover = rect.collidepoint(mouse) and is_enabled
        if is_hover:
            rect.y += 1
        
        draw_fancy_btn(screen, "", fonts['ui'], (70, 70, 75), (90, 90, 95), BTN_TXT, rect, is_hover=is_hover, is_disabled=not is_enabled, custom_radius=6)
        
        cx, cy = rect.center
        # Draw ellipsis icon
        pygame.draw.circle(screen, (200, 200, 200), (cx - 6, cy), 2)
        pygame.draw.circle(screen, (200, 200, 200), (cx, cy), 2)
        pygame.draw.circle(screen, (200, 200, 200), (cx + 6, cy), 2)
        
        # Draw speech bubble tail
        pygame.draw.polygon(screen, (70, 70, 75), [
            (rect.left + 6, rect.bottom - 1),
            (rect.left + 16, rect.bottom - 1),
            (rect.left + 11, rect.bottom + 6)
        ])
        pygame.draw.line(screen, (200, 200, 200), (rect.left + 6, rect.bottom), (rect.left + 11, rect.bottom + 6), 1)
        pygame.draw.line(screen, (200, 200, 200), (rect.left + 16, rect.bottom), (rect.left + 11, rect.bottom + 6), 1)
        btns[key] = rect

    def draw_theme_btn(x, w, key, text, is_enabled, y_override=None):
        y_pos = y_override if y_override is not None else by2
        rect = pygame.Rect(x, y_pos, w, bh)
        is_hover = rect.collidepoint(mouse) and is_enabled
        
        if is_hover:
            rect.y += 1
            
        draw_fancy_btn(screen, text, fonts['ui'], (70, 70, 75), (90, 90, 95), BTN_TXT, rect, is_hover=is_hover, is_disabled=not is_enabled, custom_radius=6)
        btns[key] = rect

    def draw_btn(x, w, key, text, is_enabled, is_active, base_color, hover_color, y_override=None):
        y_pos = y_override if y_override is not None else by2
        rect = pygame.Rect(x, y_pos, w, bh)
        is_hover = rect.collidepoint(mouse) and is_enabled
        
        # Slight press down effect
        if is_hover or is_active:
            rect.y += 1
            
        b_color = None
        if is_active:
            b_color = (245, 120, 20) if key == 'fakeout' else (80, 120, 220)
            
        draw_fancy_btn(screen, text, fonts['ui'], base_color, hover_color, BTN_TXT, rect, is_hover=is_hover, is_disabled=not is_enabled, border_color=b_color, custom_radius=6)
        btns[key] = rect

    if client_state.get('is_replay'):
        draw_btn(12, 180, 'exit_replay', 'Voltar ao Menu', True, False, (140, 50, 50), (180, 70, 70))
    elif gs['game_over']:
        draw_btn(12, 120, 'menu', 'Voltar ao Menu', True, False, BTN_N, BTN_H)
        draw_btn(BOARD_PX - 185, 170, 'export_json', 'Salvar Replay', True, False, BTN_BLUE, BTN_BLUEH, y_override=BOARD_PX + 75)

        req_by = gs.get('rematch_requested_by')
        declined = gs.get('rematch_declined')
        opp_left = gs.get('opponent_left')

        if my_color == 'spectator':
            rem_st = fonts['ui'].render("Partida encerrada.", True, T_DIM)
            screen.blit(rem_st, (150, by2 + 6))
        elif opp_left:
            rem_st = fonts['ui'].render("O oponente saiu da sala.", True, T_RED)
            screen.blit(rem_st, (150, by2 + 6))
        elif declined:
            rem_st = fonts['ui'].render("Revanche recusada.", True, T_RED)
            screen.blit(rem_st, (150, by2 + 6))
        elif req_by == my_color:
            rem_st = fonts['ui'].render("Aguardando oponente...", True, T_DIM)
            screen.blit(rem_st, (150, by2 + 6))
        elif req_by and req_by != my_color:
            draw_btn(150, 120, 'accept', 'Aceitar Revanche', True, False, BTN_END, BTN_ENDH)
            draw_btn(280, 90, 'decline', 'Recusar', True, False, (140, 50, 50), (180, 70, 70))
        else:
            draw_btn(150, 130, 'rematch', 'Pedir Revanche', True, False, BTN_BLUE, BTN_BLUEH)

    else:
        if client_state.get('reconnected_game_over') and client_state['waiting']:
            draw_btn(12, 120, 'menu', 'Voltar ao Menu', True, False, BTN_N, BTN_H)
        elif my_color == 'spectator':
            draw_btn(12, 120, 'menu', 'Voltar ao Menu', True, False, BTN_N, BTN_H)
        elif my_color != 'spectator':
            is_confirm = client_state.get('resign_confirm', False)
            r_txt = "Confirma?" if is_confirm else "Desistir"
            r_col = (180, 40, 40) if is_confirm else (140, 50, 50)
            r_hov = (220, 60, 60) if is_confirm else (180, 70, 70)
            draw_btn(8, 68, 'resign', r_txt, not history_active, is_confirm, r_col, r_hov)
            
            show_ui = not client_state.get('hide_mechanics_ui', False)
            draw_eye_btn(8 + 68 + 8, 36, 'toggle_ui', True, False, (70, 70, 75), (90, 90, 95), show_ui)
            draw_chat_btn(8 + 68 + 8 + 36 + 8, 36, 'chat', True)
            theme_text = client_state.get('theme', 'Classic')
            draw_theme_btn(8 + 68 + 8 + 36 + 8 + 36 + 8, 80, 'theme', theme_text, True)
        else:
            # Spectator just has toggle UI button
            show_ui = not client_state.get('hide_mechanics_ui', False)
            draw_eye_btn(8, 36, 'toggle_ui', True, False, (70, 70, 75), (90, 90, 95), show_ui)

    # NAVE (draggable block-sized line)
    cx = BOARD_PX // 2
    nave_w = SQ
    nave_h = 15
    pill_w = SQ * 3
    pill_h = nave_h + 10
    pill_y = BOARD_PX + PANEL_H - 10 - pill_h  # 10 pixels de distância do topo da linha vertical do explorador
    pill_x = cx - pill_w // 2

    # Draw pill
    pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
    pygame.draw.rect(screen, (35, 35, 40), pill_rect, border_radius=pill_h // 2)

    # Nave offset state
    nave_offset = client_state.get('nave_offset', 0)
    max_offset = (pill_w - nave_w) // 2
    
    if not client_state.get('is_dragging_nave', False) and nave_offset != 0:
        nave_offset = int(nave_offset * 0.7)
        if abs(nave_offset) < 2:
            nave_offset = 0

    nave_offset = max(-max_offset, min(max_offset, nave_offset))
    client_state['nave_offset'] = nave_offset

    # Draw nave
    nave_x = cx - nave_w // 2 + nave_offset
    nave_rect = pygame.Rect(nave_x, pill_y + (pill_h - nave_h) // 2, nave_w, nave_h)
    
    nave_color = (150, 150, 150)
    nave_error_time = client_state.get('nave_error_time', 0)
    now = pygame.time.get_ticks()
    if now - nave_error_time < 500:
        progress = (now - nave_error_time) / 500.0
        r = int(150 + (230 - 150) * (1 - progress))
        g = int(150 + (80 - 150) * (1 - progress))
        b = int(150 + (80 - 150) * (1 - progress))
        nave_color = (r, g, b)
        
    pygame.draw.rect(screen, nave_color, nave_rect, border_radius=6)

    # Save rects for event handling
    client_state['nave_rect'] = nave_rect
    client_state['pill_rect'] = pill_rect
    client_state['nave_max_offset'] = max_offset

    # Replay button and log buttons removed during mid-game.

    return btns

def draw_sidebar(screen, gs, fonts, client_state, mouse):
    if PORTRAIT:
        bg_rect = pygame.Rect(0, BOARD_PX + PANEL_H, BOARD_PX, WIN_H - (BOARD_PX + PANEL_H))
        pygame.draw.rect(screen, (22, 22, 26), bg_rect)
        pygame.draw.line(screen, (45, 45, 52), (0, BOARD_PX + PANEL_H), (BOARD_PX, BOARD_PX + PANEL_H), 2)
    else:
        bg_rect = pygame.Rect(BOARD_PX, 0, SIDEBAR_W, WIN_H)
        pygame.draw.rect(screen, (22, 22, 26), bg_rect)
        pygame.draw.line(screen, (45, 45, 52), (BOARD_PX, 0), (BOARD_PX, WIN_H), 2)

    old_clip = screen.get_clip()
    screen.set_clip(bg_rect)
    
    cx = bg_rect.centerx
    pygame.draw.line(screen, (45, 45, 52), (cx, bg_rect.top), (cx, bg_rect.bottom), 1)

    if 'draft_blocks' not in client_state:
        client_state['draft_blocks'] = []
    client_state['draft_blocks'].clear()

    turns = gs.get('log_turns', [])
    if not turns:
        screen.set_clip(old_clip)
        return
        
    import re
    def clean_text(txt):
        txt = re.sub(r'^\s*\d+\.\s*', '', txt)
        txt = txt.strip()
        txt = txt.replace('[Fakeout] ', '')
        txt = txt.replace('[Hidden] ', '')
        txt = re.sub(r'\(-?\d+pt\)', '', txt).strip()
        if 'Lance abandonado:' in txt:
            return txt.split('Lance abandonado:', 1)[1].strip()
        elif 'Lance abandonado' in txt:
            return 'Abandonado'
        if 'Lance inválido:' in txt:
            return txt.split('Lance inválido:', 1)[1].strip()
        elif 'Lance inválido' in txt:
            return 'Inválido'
        return txt

    def get_color(ctype):
        if ctype in ('white_move', 'black_move', 'draft_normal'): return (230, 230, 230)
        if ctype in ('fakeout', 'draft_fakeout'): return (245, 120, 20)
        if ctype in ('hidden', 'revealed'): return (60, 110, 220)
        if ctype == 'predict': return (160, 80, 200)
        if ctype == 'next_cancelled': return (100, 100, 100)
        if ctype == 'system': return (150, 150, 150)
        return (200, 200, 200)
        
    # Scroll handling (auto-scroll to bottom if overflows)
    padding = 20
    block_h = 36
    y_gap = 12
    total_h = padding
    
    for turn in turns:
        total_h += block_h + y_gap
        
    max_scroll = 0
    min_scroll = min(0, bg_rect.height - total_h)
    
    # Auto-scroll if log grew and we were at bottom, or if not initialized
    prev_total = client_state.get('sidebar_prev_total_h', total_h)
    at_bottom = False
    if 'sidebar_scroll_y' not in client_state:
        client_state['sidebar_scroll_y'] = min_scroll
    else:
        if abs(client_state['sidebar_scroll_y'] - min(0, bg_rect.height - prev_total)) < 10:
            at_bottom = True
            
    if total_h != prev_total and at_bottom:
        client_state['sidebar_scroll_y'] = min_scroll
        
    client_state['sidebar_prev_total_h'] = total_h
    
    client_state['sidebar_min_scroll'] = min_scroll
    client_state['sidebar_max_scroll'] = max_scroll
    
    scroll_y = client_state['sidebar_scroll_y']
    if not client_state.get('is_touch_scrolling_sidebar'):
        if scroll_y > max_scroll:
            scroll_y += (max_scroll - scroll_y) * 0.2
            if abs(scroll_y - max_scroll) < 1: scroll_y = max_scroll
        elif scroll_y < min_scroll:
            scroll_y += (min_scroll - scroll_y) * 0.2
            if abs(scroll_y - min_scroll) < 1: scroll_y = min_scroll
        client_state['sidebar_scroll_y'] = scroll_y
        
    old_scroll_y = client_state.get('sidebar_prev_scroll_y', scroll_y)
    if abs(old_scroll_y - scroll_y) > 0.1 or client_state.get('is_touch_scrolling_sidebar'):
        client_state['last_scroll_time'] = pygame.time.get_ticks()
    client_state['sidebar_prev_scroll_y'] = scroll_y

    y = bg_rect.top + padding + scroll_y
    
    prev_first_w_brect = None
    prev_first_w_is_draft = None
    prev_first_b_brect = None
    prev_first_b_is_draft = None
    
    for turn in turns:
        turn_num = turn['number']
        entries = turn['entries']
        
        w_entries = [e for e in entries if e['color'] == 'w' and e['type'] != 'SYSTEM']
        b_entries = [e for e in entries if e['color'] == 'b' and e['type'] != 'SYSTEM']
        
        # Turn Square
        t_surf = fonts['pts'].render(str(turn_num), True, (245, 245, 220))
        t_rect = t_surf.get_rect(center=(cx, y + block_h // 2))
        sq_rect = pygame.Rect(0, 0, max(32, t_rect.width + 16), 32)
        sq_rect.center = t_rect.center
        pygame.draw.rect(screen, (30, 30, 35), sq_rect, border_radius=4)
        screen.blit(t_surf, t_rect)
        
        # Draw White (Right to Left)
        wx = sq_rect.left - 10
        prev_e = None
        prev_brect = None
        for i, e in enumerate(w_entries):
            txt = clean_text(e['text'])
            c = get_color(e['color_type'])
            
            e_surf = fonts['pts'].render(txt, True, c)
            e_rect = e_surf.get_rect()
            
            bw = e_rect.width + 20
            bx = wx - bw
            brect = pygame.Rect(bx, y + block_h//2 - 16, bw, 32)
            
            if i == 0:
                is_draft = bool(e.get('drafted_turn'))
                if prev_first_w_brect:
                    if is_draft:
                        x1 = prev_first_w_brect.right - 16
                        y1 = prev_first_w_brect.bottom
                        x2 = brect.right - 16
                        y2 = brect.top
                        pygame.draw.line(screen, (220, 60, 60), (x1, y1), (x2, y2), 2)
                prev_first_w_brect = brect
                prev_first_w_is_draft = is_draft
            
            # Check for connection
            if prev_e and ((prev_e.get('type') == 'HIDDEN' and e.get('type') == 'FAKEOUT') or (prev_e.get('type') == 'FAKEOUT' and e.get('type') == 'HIDDEN')):
                pygame.draw.line(screen, (150, 150, 150), (brect.right, brect.centery), (prev_brect.left, prev_brect.centery), 2)

            block_id = (turn_num, 'w', i)
            client_state['draft_blocks'].append((brect, block_id))

            is_selected = client_state.get('selected_block') == block_id
            # background
            bg_color = (80, 80, 85) if is_selected else (25, 25, 28)
            pygame.draw.rect(screen, bg_color, brect, border_radius=4)
            # border
            border_color = (220, 60, 60) if e.get('drafted_turn') else (150, 150, 150)
            if is_selected:
                import math
                bw_anim = int(2 + math.sin(pygame.time.get_ticks() / 150) * 1)
                pygame.draw.rect(screen, border_color, brect, bw_anim, border_radius=4)
            else:
                pygame.draw.rect(screen, border_color, brect, 1, border_radius=4)
            
            e_rect.center = brect.center
            screen.blit(e_surf, e_rect)
            
            wx -= bw + 8
            prev_e = e
            prev_brect = brect
        
        # Draw Black (Left to Right)
        bx_start = sq_rect.right + 10
        prev_e = None
        prev_brect = None
        for i, e in enumerate(b_entries):
            txt = clean_text(e['text'])
            c = get_color(e['color_type'])
            
            e_surf = fonts['pts'].render(txt, True, c)
            e_rect = e_surf.get_rect()
            
            bw = e_rect.width + 20
            brect = pygame.Rect(bx_start, y + block_h//2 - 16, bw, 32)
            
            if i == 0:
                is_draft = bool(e.get('drafted_turn'))
                if prev_first_b_brect:
                    if is_draft:
                        x1 = prev_first_b_brect.left + 16
                        y1 = prev_first_b_brect.bottom
                        x2 = brect.left + 16
                        y2 = brect.top
                        pygame.draw.line(screen, (220, 60, 60), (x1, y1), (x2, y2), 2)
                prev_first_b_brect = brect
                prev_first_b_is_draft = is_draft
            
            # Check for connection
            if prev_e and ((prev_e.get('type') == 'HIDDEN' and e.get('type') == 'FAKEOUT') or (prev_e.get('type') == 'FAKEOUT' and e.get('type') == 'HIDDEN')):
                pygame.draw.line(screen, (150, 150, 150), (prev_brect.right, prev_brect.centery), (brect.left, brect.centery), 2)
            
            block_id = (turn_num, 'b', i)
            client_state['draft_blocks'].append((brect, block_id))

            is_selected = client_state.get('selected_block') == block_id
            # background
            bg_color = (80, 80, 85) if is_selected else (25, 25, 28)
            pygame.draw.rect(screen, bg_color, brect, border_radius=4)
            # border
            border_color = (220, 60, 60) if e.get('drafted_turn') else (150, 150, 150)
            if is_selected:
                import math
                bw_anim = int(2 + math.sin(pygame.time.get_ticks() / 150) * 1)
                pygame.draw.rect(screen, border_color, brect, bw_anim, border_radius=4)
            else:
                pygame.draw.rect(screen, border_color, brect, 1, border_radius=4)
            
            e_rect.center = brect.center
            screen.blit(e_surf, e_rect)
            
            bx_start += bw + 8
            prev_e = e
            prev_brect = brect
            
        y += block_h + y_gap
        
    if client_state.get('scroll_to_selected') and client_state.get('selected_block'):
        sel_id = client_state['selected_block']
        for br, bid in client_state['draft_blocks']:
            if bid == sel_id:
                padding_y = 20
                delta = 0
                if br.top < bg_rect.top + padding_y:
                    delta = (bg_rect.top + padding_y) - br.top
                elif br.bottom > bg_rect.bottom - padding_y:
                    delta = (bg_rect.bottom - padding_y) - br.bottom
                
                if delta != 0:
                    new_scroll = client_state.get('sidebar_scroll_y', 0) + delta
                    min_s = client_state.get('sidebar_min_scroll', 0)
                    max_s = client_state.get('sidebar_max_scroll', 0)
                    client_state['sidebar_scroll_y'] = max(min_s, min(max_s, new_scroll))
                break
        client_state['scroll_to_selected'] = False
        
    if total_h > bg_rect.height:
        gradient_h = 60
        if scroll_y < max_scroll - 2:
            grad = pygame.Surface((bg_rect.width, gradient_h), pygame.SRCALPHA)
            for i in range(gradient_h):
                alpha = int(255 * (1 - (i / gradient_h)))
                pygame.draw.line(grad, (22, 22, 26, alpha), (0, i), (bg_rect.width, i))
            screen.blit(grad, (bg_rect.left, bg_rect.top))
            
        if scroll_y > min_scroll + 2:
            grad = pygame.Surface((bg_rect.width, gradient_h), pygame.SRCALPHA)
            for i in range(gradient_h):
                alpha = int(255 * (i / gradient_h))
                pygame.draw.line(grad, (22, 22, 26, alpha), (0, i), (bg_rect.width, i))
            screen.blit(grad, (bg_rect.left, bg_rect.bottom - gradient_h))
            
        # Draw scrollbar indicator
        now = pygame.time.get_ticks()
        last_scroll = client_state.get('last_scroll_time', 0)
        time_since_scroll = now - last_scroll
        if time_since_scroll < 1000:
            # Fade out over the last 300ms
            alpha = 255
            if time_since_scroll > 700:
                alpha = int(255 * (1 - (time_since_scroll - 700) / 300.0))
                
            sb_h = max(20, int(bg_rect.height * (bg_rect.height / total_h)))
            
            # min_scroll is negative or 0. scroll_y goes from max_scroll(0) to min_scroll
            if min_scroll < 0:
                progress = scroll_y / min_scroll
                progress = max(0.0, min(1.0, progress))
            else:
                progress = 0
                
            sb_y = bg_rect.top + int(progress * (bg_rect.height - sb_h))
            sb_rect = pygame.Rect(bg_rect.left + 2, sb_y, 4, sb_h)
            
            sb_surf = pygame.Surface((sb_rect.width, sb_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(sb_surf, (150, 150, 150, alpha), sb_surf.get_rect(), border_radius=2)
            screen.blit(sb_surf, sb_rect.topleft)

    screen.set_clip(old_clip)

def draw_text_center(screen, text, font, color, y_pos, cx=None):
    surf = font.render(text, True, color)
    center_x = cx if cx is not None else (WIN_W // 2)
    rect = surf.get_rect(center=(center_x, y_pos))
    screen.blit(surf, rect)
    return rect

async def handle_gesture_release(mx, my, client_state, gs, is_local, websocket, screen, fonts):
    if not client_state.get('is_dragging_gesture'):
        return gs

    # drag_piece_sq is the clicked square (might be pub_pos)
    # selected is the true square resolved by get_ui_selection
    dsr, dsc = client_state['drag_piece_sq']
    if client_state.get('selected'):
        sr, sc = client_state['selected']
    else:
        sr, sc = dsr, dsc
    
    if mx < BOARD_PX and my < BOARD_PX:
        cc2 = mx // SQ
        rr2 = my // SQ
        r = 7 - rr2 if client_state['flipped'] else rr2
        c = 7 - cc2 if client_state['flipped'] else cc2
        
        if (r, c) == (dsr, dsc):
            # ... existing source click logic ...
            client_state['selected'] = None
            client_state['legal_sq'] = []
            client_state['is_dragging_gesture'] = False
            client_state['casca_auto_fakeout'] = False
            if client_state.get('fakeout_triggered'):
                await MechanicsManager.execute_toggle_fakeout(gs, client_state, is_local, websocket, play_sound, None)
            elif client_state.get('hidden_triggered'):
                await MechanicsManager.execute_toggle_hidden(gs, client_state, is_local, websocket, play_sound, None)
            else:
                if (gs.get('fakeout_active') or client_state.get('draft_fakeout')) and not client_state.get('casca_auto_fakeout'):
                    await MechanicsManager.execute_toggle_fakeout(gs, client_state, is_local, websocket, play_sound, None)
                elif gs.get('hidden_mode') or client_state.get('draft_hidden'):
                    await MechanicsManager.execute_toggle_hidden(gs, client_state, is_local, websocket, play_sound, None)
            client_state['hidden_triggered'] = False
            client_state['fakeout_triggered'] = False
            client_state['casca_auto_fakeout'] = False
            return gs
        
        # --- ICE KING CHECK ---
        else:
            curr_dgs_k = get_draft_state(gs, client_state.get('draft_moves', []), client_state.get('my_color')) if client_state.get('drafting') else gs
            tb_k = get_true_board(curr_dgs_k, gs['turn'])
            p_king = tb_k[sr][sc]
            p_target = tb_k[r][c]
            
            if p_king and pt(p_king) == 'K' and pc(p_king) == gs['turn'] and p_target and pc(p_target) == gs['turn'] and pt(p_target) != 'K':
                # Interaction returns 'frozen', 'unfrozen' or None
                res = ice_king_interaction(gs, sr, sc, r, c)
                if res:
                    if res == 'frozen':
                        trigger_freeze_effect(client_state, gs, r, c)
                    else:
                        trigger_unfreeze_effect(client_state, gs, r, c)
                    
                    if not is_local:
                        await websocket.send(json.dumps({
                            "type": "action", "action": "ice_king",
                            "kr": sr, "kc": sc, "tr": r, "tc": c
                        }))
                    
                    client_state['is_dragging_gesture'] = False
                    
                    client_state['casca_auto_fakeout'] = False
                    client_state['casca_auto_fakeout'] = False
                    client_state['selected'] = None
                    client_state['legal_sq'] = []
                    client_state['hidden_triggered'] = False
                    client_state['fakeout_triggered'] = False
                    if gs.get('fakeout_active') or client_state.get('draft_fakeout'):
                        gs['fakeout_active'] = False
                        client_state['draft_fakeout'] = False
                    elif gs.get('hidden_mode') or client_state.get('draft_hidden'):
                        gs['hidden_mode'] = False
                        client_state['draft_hidden'] = False
                    return gs
        # --- END ICE KING CHECK ---
        
        if client_state.get('predicting_mode'):
            if (r, c) in client_state['legal_sq']:
                sr, sc = client_state.get('drag_piece_sq', client_state.get('selected', (0, 0)))
                gs_temp = copy.deepcopy(gs)
                gs_temp['turn'] = 'b' if gs['turn'] == 'w' else 'w'
                tb_temp = get_true_board(gs_temp, gs_temp['turn'])
                p_target = tb_temp[r][c]
                p_dragged = tb_temp[sr][sc]
                is_casca_drag = p_dragged is None
                if is_casca_drag:
                    my_hidden = gs_temp["hidden_w"] if gs_temp["turn"] == "w" else gs_temp["hidden_b"]
                    for val in my_hidden.values():
                        if val.pub_pos == (sr, sc):
                            p_dragged = val.piece
                            break
                            
                promo = None
                if p_dragged and pt(p_dragged) == 'P' and r in (0, 7):
                    promo = await ask_promo(screen, fonts, gs_temp['turn'], websocket, client_state)

                if is_local:
                    dm_copy = client_state.get('draft_moves', [])
                    if dm_copy:
                        q_key_sq = f'next_queue_{gs["turn"]}'
                        gs[q_key_sq] = copy.deepcopy(dm_copy)
                    if register_predict_move(gs, gs['turn'], sr, sc, r, c, promo, cost=0.2):
                        client_state['predict_cost_total'] = round(client_state.get('predict_cost_total', 0.0) + 0.2, 2)
                        play_sound('capture' if p_target is not None else 'move')
                    else:
                        play_sound('error')
                        gs['log'].append({'text': 'Pontuação insuficiente', 'color_type': 'predict'})
                        trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
                else:
                    if gs['pts'][gs['turn']] >= 0.2:
                        play_sound('capture' if p_target is not None else 'move')
                        await websocket.send(json.dumps({
                            'type': 'action',
                            'action': 'predict_move',
                            'fr': sr,
                            'fc': sc,
                            'tr': r,
                            'tc': c,
                            'promo': promo
                        }))
                    else:
                        play_sound('error')
                        gs['log'].append({'text': 'Pontuação insuficiente', 'color_type': 'predict'})
                        trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
            else:
                play_sound('error')
                trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
                
            client_state['selected'] = None
            client_state['legal_sq'] = []
            client_state['is_dragging_gesture'] = False
            client_state['casca_auto_fakeout'] = False
            return gs

        if (r, c) in client_state['legal_sq']:
            curr_dgs = get_draft_state(gs, client_state.get('draft_moves', []), client_state.get('my_color')) if client_state.get('drafting') else gs
            tb = get_true_board(curr_dgs, gs['turn'])
            p = tb[sr][sc]
            is_casca_drag = p is None
            if is_casca_drag:
                my_hidden = curr_dgs["hidden_w"] if gs["turn"] == "w" else curr_dgs["hidden_b"]
                for val in my_hidden.values():
                    if val.pub_pos == (sr, sc):
                        p = val.piece
                        break
            is_fakeout_active_now = client_state.get('draft_fakeout', False) if client_state.get('drafting') else gs.get('fakeout_active', False)
            if is_casca_drag and not is_fakeout_active_now:
                play_sound('error')
                trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
                client_state['selected'] = None
                client_state['legal_sq'] = []
                client_state['is_dragging_gesture'] = False
                client_state['casca_auto_fakeout'] = False
                return gs
                
            # Release on valid target concludes the move!
            promo = None
            if p and pt(p) == 'P' and r in (0, 7):
                promo = await ask_promo(screen, fonts, gs['turn'], websocket, client_state)

            is_auto_draft = not client_state.get('drafting') and gs.get('hidden_count', 0) > 0 and not (gs.get('fakeout_active', False) or client_state.get('fakeout_triggered', False))
            if client_state.get('drafting') or is_auto_draft:
                if is_auto_draft:
                    client_state['drafting'] = True
                is_hidden_move = client_state.get('draft_hidden', False) or client_state.get('hidden_triggered', False) or gs.get('hidden_mode', False)
            else:
                is_hidden_move = gs.get('hidden_mode', False) or client_state.get('hidden_triggered', False)

            if client_state.get('drafting'):
                d_moves = client_state.get('draft_moves', [])
                dgs = get_draft_state(gs, d_moves, client_state.get('my_color'))
                dgs['fakeout_active'] = client_state.get('draft_fakeout', False)
                dgs['hidden_mode'] = is_hidden_move
                legals = legal(dgs, sr, sc)
                if (r, c) in legals:
                    is_fake = client_state.get('draft_fakeout', False)
                    d_moves.append({
                        'type': 'move',
                        'fr': sr, 'fc': sc, 'tr': r, 'tc': c,
                        'hidden': is_hidden_move,
                        'fakeout': is_fake,
                        'promo': promo,
                        'drafted_turn': ((dgs['turn_count'] + 1) // 2) - (1 if is_fake else 0)
                    })
                    client_state['draft_moves'] = d_moves
                    
                    play_sound('next_move')
                    client_state['draft_hidden'] = False
                    client_state['draft_fakeout'] = False
                    if gs.get('hidden_mode', False) and not is_local:
                        await websocket.send(json.dumps({"type": "action", "action": "toggle_hidden"}))
                    if gs.get('fakeout_active', False) and not is_local:
                        await websocket.send(json.dumps({"type": "action", "action": "toggle_fakeout"}))
                    gs['hidden_mode'] = False
                    gs['fakeout_active'] = False
                    client_state['fill_fade_timer'] = 1.0
                    col = (245, 120, 20) if is_fake else ((30, 110, 255) if is_hidden_move else (239, 68, 68))
                    sqs = [(r, c, col, 255, False)]
                    dr, dc = r - sr, c - sc
                    steps = max(abs(dr), abs(dc))
                    if (abs(dr) == 2 and abs(dc) == 1) or (abs(dr) == 1 and abs(dc) == 2):
                        mid_r, mid_c = (r, sc) if abs(dr) == 2 else (sr, c)
                        sqs.append((mid_r, mid_c, col, 127, False))
                    elif steps > 0:
                        alpha = 127
                        for i in range(steps - 1, 0, -1):
                            sq_r = sr + int(i * dr / steps)
                            sq_c = sc + int(i * dc / steps)
                            sqs.append((sq_r, sq_c, col, alpha, False))
                            alpha = max(10, alpha // 2)
                    client_state['fade_squares'] = sqs
                client_state['selected'] = None
                client_state['legal_sq'] = []
            else:
                if is_local:
                    old_game_over = gs.get('game_over', False)
                    old_last = gs.get('last_move')
                    n_cap_w = len(gs.get('captured_w', []))
                    n_cap_b = len(gs.get('captured_b', []))
                    
                    has_captured_piece_on_square = False
                    if gs.get('board') and 0 <= r < 8 and 0 <= c < 8:
                        has_captured_piece_on_square = gs['board'][r][c] is not None
                        
                    is_fakeout = gs.get('fakeout_active', False)
                    res = exec_move(gs, sr, sc, r, c, hidden_move=is_hidden_move, promo=promo)
                    if res:
                        if 'current_turn_actions' not in gs: gs['current_turn_actions'] = []
                        gs['current_turn_actions'].append({
                            'type': 'move', 'fr': sr, 'fc': sc, 'tr': r, 'tc': c,
                            'promo': promo, 'hidden': is_hidden_move, 'fakeout': is_fakeout
                        })
                    
                    new_last = gs.get('last_move')
                    
                    cap_w = len(gs.get('captured_w', [])) > n_cap_w
                    cap_b = len(gs.get('captured_b', [])) > n_cap_b
                    
                    if res and old_last != new_last and new_last:
                        nfr, nfc, ntr, ntc = new_last
                        
                        is_capture_by_log = False
                        if gs.get('log'):
                            norm_last_log = gs['log'][-1].lower()
                            if "capturado" in norm_last_log or "capturada" in norm_last_log:
                                is_capture_by_log = True
                            elif 'x' in norm_last_log:
                                without_xeque = norm_last_log.replace("xeque", "")
                                if 'x' in without_xeque:
                                    is_capture_by_log = True
                        
                        is_capture = cap_w or cap_b or has_captured_piece_on_square or res == "ghost_capture" or is_capture_by_log
                        
                        p_anim = gs['board'][ntr][ntc]
                        if not p_anim:
                            for h_dict in [gs.get('hidden_w', {}), gs.get('hidden_b', {})]:
                                if (ntr, ntc) in h_dict:
                                    target_val = h_dict[(ntr, ntc)]
                                    p_anim = target_val.piece if hasattr(target_val, 'piece') else target_val[1]
                                    break
                        if p_anim:
                            trigger_piece_anim(client_state, p_anim, nfr, nfc, ntr, ntc, is_hidden_move, gs.get('fakeout_used', False) or gs.get('fakeout_active', False), is_capture)
                        
                        is_fakeout = gs.get('fakeout_used', False)
                        is_shadow = gs.get('hidden_count', 0) > 0
                        if gs.get('game_over', False) and not old_game_over:
                            play_sound('game_over')
                        elif is_capture: play_sound('capture')
                        else: play_sound('move')
                        
                    if res == "ghost_capture":
                        gc_type = gs.get('ghost_capture_type', 'standard')
                        col = (245, 120, 20) if gc_type == 'fakeout' else (60, 110, 220)
                        trigger_square_flash(client_state, r, c, col, gc_type)
                        gs['ghost_capture_flash'] = None
                        gs['ghost_capture_type'] = None

                    if gs.get('reveal_flashes'):
                        for r_fl in gs['reveal_flashes']:
                            rr, rc = r_fl[0], r_fl[1]
                            rtype = r_fl[2] if len(r_fl) > 2 else 'hidden'
                            col = (245, 120, 20) if rtype == 'fakeout' else (60, 110, 220)
                            trigger_square_flash(client_state, rr, rc, col, rtype)
                        gs['reveal_flashes'] = []

                    client_state['selected'] = None
                    client_state['legal_sq'] = []
                    gs['hidden_mode'] = False
                else:
                    move_cmd = {
                        "type": "action", "action": "move",
                        "fr": sr, "fc": sc, "tr": r, "tc": c, "promo": promo, "gesture_hidden": is_hidden_move
                    }
                    await websocket.send(json.dumps(move_cmd))
                    client_state['selected'] = None
                    client_state['legal_sq'] = []
            
            client_state['is_dragging_gesture'] = False
            
            client_state['casca_auto_fakeout'] = False
            client_state['hidden_triggered'] = False
            client_state['fakeout_triggered'] = False
        else:
            # Release on an invalid square -> Red pulse
            trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
            client_state['is_dragging_gesture'] = False
            client_state['casca_auto_fakeout'] = False
            # ADDED: Reset triggers
            if client_state.get('fakeout_triggered'):
                await MechanicsManager.execute_toggle_fakeout(gs, client_state, is_local, websocket, play_sound, None)
            elif client_state.get('hidden_triggered'):
                await MechanicsManager.execute_toggle_hidden(gs, client_state, is_local, websocket, play_sound, None)
            client_state['hidden_triggered'] = False
            client_state['fakeout_triggered'] = False
            
            client_state['selected'] = None
            client_state['legal_sq'] = []
    else:
        # Released outside the board -> Reset state
        client_state['is_dragging_gesture'] = False
        client_state['casca_auto_fakeout'] = False
        client_state['hidden_triggered'] = False
        # ADDED: Reset triggers
        if client_state.get('fakeout_triggered'):
            await MechanicsManager.execute_toggle_fakeout(gs, client_state, is_local, websocket, play_sound, None)
        elif client_state.get('hidden_triggered'):
            await MechanicsManager.execute_toggle_hidden(gs, client_state, is_local, websocket, play_sound, None)
        client_state['hidden_triggered'] = False
        client_state['fakeout_triggered'] = False
        
        client_state['selected'] = None
        client_state['legal_sq'] = []

    return gs

async def wake_up_server(uri):
    pass

async def connect_and_join(uri, action, room_code=None, token=None):
    from firebase_transport import MockWebsocket
    try:
        ws = MockWebsocket()
        if action == "create_room":
            await ws.send(json.dumps({"type": "create_room"}))
        elif action == "join_room":
            await ws.send(json.dumps({"type": "join_room", "room": room_code, "session_token": token}))
        elif action == "spectate_room":
            await ws.send(json.dumps({"type": "spectate_room", "room": room_code, "session_token": token}))
        return ws
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Connection error:", e)
        return e

async def game_loop():
    global WIN_W, WIN_H, PORTRAIT
    pygame.init()
    pygame.key.set_repeat(0)

    try:
        info = pygame.display.Info()
        if info.current_h > info.current_w and info.current_w > 0:
            PORTRAIT = True
            WIN_W = BOARD_PX
            ratio = info.current_h / info.current_w
            WIN_H = max(int(WIN_W * ratio), BOARD_PX + PANEL_H + 200)
        else:
            PORTRAIT = False
            WIN_W = BOARD_PX + SIDEBAR_W
            WIN_H = BOARD_PX + PANEL_H
    except Exception:
        PORTRAIT = False
        WIN_W = BOARD_PX + SIDEBAR_W
        WIN_H = BOARD_PX + PANEL_H

    is_android = hasattr(sys, 'getandroidapilevel')
    flags = pygame.SCALED
    if is_android:
        import os
        os.environ['SDL_RENDER_SCALE_QUALITY'] = '1'
        flags |= pygame.FULLSCREEN
    else:
        flags |= pygame.RESIZABLE

    screen = pygame.display.set_mode((WIN_W, WIN_H), flags)
    try:
        pygame.scrap.init()
    except:
        pass
    pygame.display.set_caption('Hidden Chess')
    fonts = load_fonts()
    load_assets()
    title_font = fonts['title']

    uri = ""
    
    # Try to wake up server immediately in background
    asyncio.create_task(wake_up_server(uri))

    error_msg = ""
    running = True

    app_state = "INTRO_ANIM"
    gs = make_state()
    client_state = {
        'intro_start': pygame.time.get_ticks(),
        'my_color': None,
        'waiting': True,
        'flipped': False,
        'selected': None,
        'legal_sq': [],
        'room_code': None,
        'is_typing': False,
        'msg_queue': deque(),
        'show_hidden': True,
        'resign_confirm': False,
        'panel_btns': {},
        'is_local': False,
        'turn_start_snapshot': None,
        'turn_history': [],
        'history_index': 0,
        'score_to_win': False
    }
    input_text = ""
    websocket = None
    clock = pygame.time.Clock()

    menu_y_start = (WIN_H // 2) - 140
    btn_create = pygame.Rect(WIN_W // 2 - 100, menu_y_start, 200, 50)
    btn_join = pygame.Rect(WIN_W // 2 - 100, menu_y_start + 65, 200, 50)
    btn_spectate = pygame.Rect(WIN_W // 2 - 100, menu_y_start + 130, 200, 50)
    btn_local = pygame.Rect(WIN_W // 2 - 100, menu_y_start + 195, 200, 50)
    btn_replays = pygame.Rect(WIN_W // 2 - 100, menu_y_start + 260, 200, 50)

    def start_local_game(is_test=False):
        nonlocal gs, client_state, app_state
        gs = make_state()
        gs['game_started'] = True
        gs['fakeout_mode_enabled'] = True
        gs['score_to_win'] = True
        gs['ice_king_enabled'] = True
        current_t = client_state.get('theme', 'Classic')
        client_state = {
            'theme': current_t,
            'my_color': 'w',
            'waiting': False,
            'flipped': False,
            'selected': None,
            'legal_sq': [],
            'room_code': "TEST" if is_test else "LOCAL",
            'is_typing': False,
            'msg_queue': deque(),
            'show_hidden': True,
            'resign_confirm': False,
            'panel_btns': {},
            'is_local': True,
            'is_test': is_test,
            'turn_start_snapshot': copy.deepcopy(gs),
            'turn_history': [copy.deepcopy(gs)],
            'history_index': 0,
            'fakeout_mode_enabled': True,
            'score_to_win': True,
            'ice_king_enabled': True
        }
        app_state = "PLAYING"
        play_sound('start')
        if is_test:
            pygame.display.set_caption("Hidden Chess - Partida Teste")
        else:
            pygame.display.set_caption("Hidden Chess - Partida Local")

    while running:
        dt = clock.tick(FPS) / 1000.0
        await asyncio.sleep(0) # yield control so websocket background task won't drop pong packets
        
        if client_state.get('is_dragging_gesture'):
            if not client_state.get('predicting_mode'):
                client_state['gesture_timer'] = client_state.get('gesture_timer', 0.0) + dt
                client_state['gesture_stalled'] = False
            if not client_state.get('predicting_mode') and not client_state.get('hidden_triggered') and not client_state.get('fakeout_triggered'):
                is_dragging_casca = False
                if 'drag_piece_sq' in client_state:
                    dr, dc = client_state['drag_piece_sq']
                    curr_dgs = get_draft_state(gs, client_state.get('draft_moves', []), client_state.get('my_color')) if client_state.get('drafting') else gs
                    my_hidden = curr_dgs['hidden_w'] if gs['turn'] == 'w' else curr_dgs['hidden_b']
                    for val in my_hidden.values():
                        if getattr(val, 'pub_pos', None) == (dr, dc) or (isinstance(val, dict) and val.get('pub_pos') in ((dr, dc), [dr, dc])):
                            is_dragging_casca = True
                            break
                if is_dragging_casca:
                    client_state['gesture_timer'] = 0.0
                elif client_state['gesture_timer'] >= 2.0:
                    if MechanicsManager.can_toggle_hidden(gs, client_state):
                        client_state['hidden_triggered'] = True
                        # Trigger hidden logic (async)
                        mx, my = client_state.get('drag_pos', (0,0))
                        await MechanicsManager.execute_toggle_hidden(gs, client_state, client_state.get('is_local', False), websocket, play_sound, None, click_pos=(mx, my), force_shockwave=True)
                        
                        # UPDATE LEGAL SQUARES
                        sr, sc = client_state['drag_piece_sq']
                        gs_temp = copy.copy(gs)
                        gs_temp['drafting_active'] = client_state.get('drafting', False)
                        if client_state.get('drafting'):
                            gs_temp['fakeout_active'] = client_state.get('draft_fakeout', False)
                            gs_temp['hidden_mode'] = client_state.get('draft_hidden', False)
                        sel, legs = get_ui_selection(gs_temp, sr, sc, draft_moves=client_state.get('draft_moves', []))
                        if sel is not None:
                            client_state['selected'] = sel
                            client_state['legal_sq'] = legs
                        else:
                            client_state['legal_sq'] = []
                    else:
                        # Cannot afford or toggle hidden, let timer continue if we can afford fakeout
                        if not MechanicsManager.can_toggle_fakeout(gs, client_state):
                            client_state['gesture_timer'] = 2.0
                            client_state['gesture_stalled'] = True

            if not client_state.get('predicting_mode') and client_state['gesture_timer'] >= 3.5 and not client_state.get('fakeout_triggered'):
                if MechanicsManager.can_toggle_fakeout(gs, client_state):
                    client_state['fakeout_triggered'] = True
                    client_state['hidden_triggered'] = False
                    # Trigger fakeout logic (async)
                    mx, my = client_state.get('drag_pos', (0,0))
                    await MechanicsManager.execute_toggle_fakeout(gs, client_state, client_state.get('is_local', False), websocket, play_sound, None, click_pos=(mx, my), force_shockwave=True)
                    
                    # UPDATE LEGAL SQUARES
                    sr, sc = client_state['drag_piece_sq']
                    gs_temp = copy.copy(gs)
                    gs_temp['drafting_active'] = client_state.get('drafting', False)
                    if client_state.get('drafting'):
                        gs_temp['fakeout_active'] = client_state.get('draft_fakeout', False)
                        gs_temp['hidden_mode'] = client_state.get('draft_hidden', False)
                    sel, legs = get_ui_selection(gs_temp, sr, sc, draft_moves=client_state.get('draft_moves', []))
                    if sel is not None:
                        client_state['selected'] = sel
                        client_state['legal_sq'] = legs
                    else:
                        client_state['legal_sq'] = []
                else:
                    client_state['gesture_timer'] = 3.5
                    client_state['gesture_stalled'] = True

        if 'fill_fade_timer' in client_state and client_state['fill_fade_timer'] > 0:
            client_state['fill_fade_timer'] = max(0.0, client_state['fill_fade_timer'] - dt)

        if client_state.get('anim'):
            client_state['anim']['t'] += dt
            a = client_state['anim']
            
            if a.get('is_hidden') or a.get('is_fakeout'):
                flipped = client_state.get('flipped', False)
                fr, fc = 7 - a['fr'] if flipped else a['fr'], 7 - a['fc'] if flipped else a['fc']
                tr, tc = 7 - a['tr'] if flipped else a['tr'], 7 - a['tc'] if flipped else a['tc']
                start_x, start_y = fc * SQ, fr * SQ
                end_x, end_y = tc * SQ, tr * SQ
                
                progress = min(1.0, a['t'] / a['dur'])
                ease = 1.0 - (1.0 - progress) ** 3
                cur_x = start_x + (end_x - start_x) * ease + SQ // 2
                cur_y = start_y + (end_y - start_y) * ease + SQ // 2
                
                p_color = (60, 110, 220) if a.get('is_hidden') else (245, 120, 20)
                if 'particles' not in client_state:
                    client_state['particles'] = []
                for _ in range(2):
                    angle = random.uniform(0, 6.28)
                    vel = random.uniform(15, 45)
                    client_state['particles'].append({
                        'x': cur_x,
                        'y': cur_y,
                        'vx': math.cos(angle) * vel,
                        'vy': math.sin(angle) * vel,
                        'color': p_color,
                        'life': 0.15 + random.uniform(0, 0.15),
                        'max_life': 0.3,
                        'size': random.uniform(2.5, 5.5)
                    })

            if client_state['anim']['t'] >= client_state['anim']['dur']:
                fr_d, fc_d = 7 - a['tr'] if client_state.get('flipped') else a['tr'], 7 - a['tc'] if client_state.get('flipped') else a['tc']
                end_x, end_y = fc_d * SQ + SQ // 2, fr_d * SQ + SQ // 2
                
                is_cap = a.get('is_capture', False)
                if is_cap:
                    spawn_particles(end_x, end_y, (230, 60, 60), 20, client_state, size=4, speed=200, life=0.4)
                elif a.get('is_hidden'):
                    spawn_particles(end_x, end_y, (60, 110, 220), 16, client_state, size=3.5, speed=120, life=0.35)
                elif a.get('is_fakeout'):
                    spawn_particles(end_x, end_y, (245, 120, 20), 16, client_state, size=3.5, speed=120, life=0.35)
                else:
                    spawn_particles(end_x, end_y, (180, 170, 160), 12, client_state, size=3, speed=100, life=0.25)
                
                a = client_state['anim']
                client_state['anim'] = None
                if a.get('color') == client_state.get('my_color'):
                    client_state['fill_fade_timer'] = 1.0
                    
                    sqs = []
                    # Path fading
                    fr, fc, tr, tc = a['fr'], a['fc'], a['tr'], a['tc']
                    is_h = a.get('is_hidden')
                    is_f = a.get('is_fakeout')
                    col = (245, 120, 20) if is_f else ((30, 110, 255) if is_h else (239, 68, 68))
                    
                    # compute path ALWAYS for all move types
                    dr = tr - fr
                    dc = tc - fc
                    steps = max(abs(dr), abs(dc))
                    if (abs(dr) == 2 and abs(dc) == 1) or (abs(dr) == 1 and abs(dc) == 2):
                        mid_r, mid_c = (tr, fc) if abs(dr) == 2 else (fr, tc)
                        sqs.append((mid_r, mid_c, col, 72, False))
                        sqs.append((tr, tc, col, 120, False))
                    elif steps > 0:
                        for i in range(1, steps + 1):
                            r = fr + int(i * dr / steps)
                            c = fc + int(i * dc / steps)
                            alpha = int(25 + 95 * (i / steps))
                            sqs.append((r, c, col, alpha, False))
                    client_state['fade_squares'] = sqs

        if client_state.get('particles'):
            for p in client_state['particles']:
                p['x'] += p['vx'] * dt
                p['y'] += p['vy'] * dt
                p['life'] -= dt
            client_state['particles'] = [p for p in client_state['particles'] if p['life'] > 0]

        # Update shockwaves
        if client_state.get('shockwaves'):
            for sw in client_state['shockwaves']:
                sw['t'] += dt
            client_state['shockwaves'] = [sw for sw in client_state['shockwaves'] if sw['t'] < sw['duration']]

        if client_state.get('freeze_fx'):
            for fx in client_state['freeze_fx']:
                fx['t'] += dt
            client_state['freeze_fx'] = [fx for fx in client_state['freeze_fx'] if fx['t'] < 2.0]

        if client_state.get('unfreeze_fx'):
            for fx in client_state['unfreeze_fx']:
                fx['t'] += dt
            client_state['unfreeze_fx'] = [fx for fx in client_state['unfreeze_fx'] if fx['t'] < 1.0]

        mouse = pygame.mouse.get_pos()
        if client_state.get('is_dragging_gesture'):
            old_pos = client_state.get('drag_pos', mouse)
            client_state['drag_pos'] = mouse
            dx = mouse[0] - old_pos[0]
            dy = mouse[1] - old_pos[1]
            vx, vy = client_state.get('drag_vel', (0.0, 0.0))
            vx = vx * 0.8 + dx * 0.2
            vy = vy * 0.8 + dy * 0.2
            client_state['drag_vel'] = (vx, vy)

        # Update flashes
        if 'flashes' in client_state:
            finished_flashes = []
            for sq in list(client_state['flashes'].keys()):
                val = client_state['flashes'][sq]
                if isinstance(val, dict):
                    val['t'] += dt
                    t_val = val['t']
                else:
                    client_state['flashes'][sq] += dt
                    t_val = client_state['flashes'][sq]
                if t_val >= 0.36:  # 2 blinks of 0.18s each
                    finished_flashes.append(sq)
            for sq in finished_flashes:
                del client_state['flashes'][sq]

        # Check if we have a pending connection task
        if client_state.get('conn_task'):
            t = client_state['conn_task']
            if t.done():
                try:
                    res = t.result()
                    client_state['conn_task'] = None
                    if isinstance(res, Exception):
                        error_msg = f"Falha na conexão. Tente novamente."
                        app_state = "MENU"
                        websocket = None
                    else:
                        websocket = res
                except Exception as e:
                    client_state['conn_task'] = None
                    error_msg = f"Falha na conexão: {e}"
                    app_state = "MENU"
                    websocket = None

        # A. Websocket message parsing (multiplayer only)
        if websocket is not None and not client_state.get('is_local', False):
            try:
                if client_state['msg_queue']:
                    msg = client_state['msg_queue'].popleft()
                else:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=0.005)

                data = json.loads(msg)
                
                if data['type'] == 'room_created':
                    client_state['room_code'] = data['room']
                    client_state['my_color'] = data['color']
                    app_state = "LOBBY"
                    save_session(data['room'], data.get('session_token'))

                elif data['type'] == 'room_joined':
                    client_state['room_code'] = data['room']
                    client_state['my_color'] = data['color']
                    client_state['flipped'] = (data['color'] == 'b')
                    save_session(data['room'], data.get('session_token'))
                    if data.get('reconnected'):
                        app_state = "PLAYING"
                        client_state['waiting'] = True # Will be cleared by state_update
                        if data.get('game_over'):
                            client_state['reconnected_game_over'] = True
                    else:
                        app_state = "LOBBY"

                elif data['type'] == 'state_update':
                    client_state['waiting'] = False
                    new_gs = deserialize_state(data['state'])
                    
                    if new_gs.get('game_over') and not gs.get('game_over'):
                        play_sound('game_over')
                    elif (gs.get('last_move') != new_gs.get('last_move') and new_gs.get('last_move')) or len(new_gs.get('log', [])) != len(gs.get('log', [])):
                        lm = new_gs.get('last_move')
                        fr, fc, tr, tc = lm if lm else (None, None, None, None)
                        
                        # Detect any captured piece on destination square before the move
                        has_captured_piece_on_square = False
                        if gs.get('board') and tr is not None and tc is not None and 0 <= tr < 8 and 0 <= tc < 8:
                            has_captured_piece_on_square = gs['board'][tr][tc] is not None
                        
                        # Robust check of all new log entries to see if any represent a capture
                        new_log_entries = []
                        if gs.get('log') and len(new_gs.get('log', [])) > len(gs['log']):
                            new_log_entries = new_gs['log'][len(gs['log']):]
                        elif new_gs.get('log'):
                            new_log_entries = [new_gs['log'][-1]]
                        
                        is_capture_by_log = False
                        for entry in new_log_entries:
                            norm_entry = entry.lower()
                            if "capturado" in norm_entry or "capturada" in norm_entry:
                                is_capture_by_log = True
                                break
                            if 'x' in norm_entry:
                                without_xeque = norm_entry.replace("xeque", "")
                                if 'x' in without_xeque:
                                    is_capture_by_log = True
                                    break
                        
                        cap_w = len(new_gs.get('captured_w', [])) > len(gs.get('captured_w', []))
                        cap_b = len(new_gs.get('captured_b', [])) > len(gs.get('captured_b', []))
                        is_capture = cap_w or cap_b or has_captured_piece_on_square or is_capture_by_log
                        
                        last_log = new_gs['log'][-1] if new_gs.get('log') else ""
                        is_shadow = "HIDDEN" in last_log
                        is_fakeout = "FAKEOUT" in last_log
                        
                        is_next_move = "[next]" in last_log.lower() if last_log else False
                        
                        abs_b_new = get_absolute_board(new_gs)
                        if new_gs.get('game_over', False) and not gs.get('game_over', False):
                            pass # Handled below by play_sound('game_over') ? Wait, no
                            
                        if in_check(abs_b_new, new_gs['turn']):
                            play_sound('check')
                        elif is_capture:
                            play_sound('capture')
                        elif is_next_move:
                            play_sound('next_move')
                        else:
                            play_sound('move')
                        
                        is_undo = new_gs.get('turn_count', 0) < gs.get('turn_count', 0) or (new_gs.get('turn_count', 0) == gs.get('turn_count', 0) and len(new_gs.get('log', [])) < len(gs.get('log', [])))

                        if is_undo:
                            if gs.get('last_move'):
                                fr_u, fc_u, tr_u, tc_u = gs['last_move']
                                p_anim = gs['board'][tr_u][tc_u]
                                if not p_anim:
                                    for h_key in ['hidden_w', 'hidden_b']:
                                        h_dict = gs.get(h_key, {})
                                        pos_key = (tr_u, tc_u)
                                        if pos_key in h_dict:
                                            p_anim = h_dict[pos_key].piece
                                            break
                                if p_anim:
                                    trigger_piece_anim(client_state, p_anim, tr_u, tc_u, fr_u, fc_u, is_shadow=False, is_fakeout=False, is_capture=False)
                        else:
                            if new_gs.get('last_move'):
                                fr, fc, tr, tc = new_gs['last_move']
                                p_anim = new_gs['board'][tr][tc]
                                if not p_anim:
                                    for h_key in ['hidden_w', 'hidden_b']:
                                        h_dict = new_gs.get(h_key, {})
                                        pos_key = (tr, tc)
                                        if pos_key in h_dict:
                                            p_anim = h_dict[pos_key].piece
                                            break
                                if p_anim:
                                    trigger_piece_anim(client_state, p_anim, fr, fc, tr, tc, is_shadow, is_fakeout, is_capture)
                    
                    client_state['drafting'] = False
                    client_state['draft_moves'] = []

                    if 'turn_history' not in client_state:
                        client_state['turn_history'] = []
                        client_state['history_index'] = 0

                    if new_gs.get('state_history'):
                        old_hist_len = len(client_state.get('turn_history', []))
                        client_state['turn_history'] = copy.deepcopy(new_gs['state_history'])
                        if client_state.get('history_index', 0) >= old_hist_len - 1:
                            client_state['history_index'] = len(client_state['turn_history']) - 1
                    elif new_gs.get('game_started', False):
                        if not client_state['turn_history']:
                            client_state['turn_history'] = [copy.deepcopy(new_gs)]
                            client_state['history_index'] = 0
                        else:
                            last_gs = client_state['turn_history'][-1]
                            if (last_gs['game_over'] and not new_gs['game_over']) or (new_gs['turn_count'] == 1 and last_gs['turn_count'] > 1):
                                client_state['turn_history'] = [copy.deepcopy(new_gs)]
                                client_state['history_index'] = 0
                                client_state.pop('export_success_msg', None)
                            elif (new_gs['turn'] != last_gs['turn'] or 
                                  new_gs['turn_count'] != last_gs['turn_count'] or 
                                  (new_gs['game_over'] and not last_gs['game_over'])):
                                client_state['turn_history'].append(copy.deepcopy(new_gs))
                                if client_state.get('history_index', 0) == len(client_state['turn_history']) - 2:
                                    client_state['history_index'] = len(client_state['turn_history']) - 1

                    if new_gs.get('ghost_capture_flash'):
                        gr, gc_pos = new_gs['ghost_capture_flash']
                        gctype = new_gs.get('ghost_capture_type')
                        col = (245, 120, 20) if gctype == 'fakeout' else (60, 110, 220)
                        trigger_square_flash(client_state, gr, gc_pos, col, gctype)

                    if new_gs.get('reveal_flashes'):
                        for rf in new_gs['reveal_flashes']:
                            rr, rc = rf[0], rf[1]
                            rtype = rf[2] if len(rf) > 2 else 'hidden'
                            col = (245, 120, 20) if rtype == 'fakeout' else (60, 110, 220)
                            trigger_square_flash(client_state, rr, rc, col, rtype)

                    if new_gs['turn'] != gs['turn']:
                        client_state['resign_confirm'] = False

                    if client_state['selected']:
                        r, c = client_state['selected']
                        tb = get_true_board(new_gs, client_state['my_color'])
                        p = tb[r][c]

                        if p and pc(p) == client_state['my_color'] and new_gs['turn'] == client_state[
                            'my_color']:
                            client_state['legal_sq'] = legal(new_gs, r, c)
                        else:
                            client_state['selected'] = None
                            client_state['legal_sq'] = []

                    gs = new_gs
                    if gs.get('game_started', False):
                        if app_state != "PLAYING":
                            play_sound('start')
                        app_state = "PLAYING"
                        if client_state['my_color'] == 'spectator':
                            pygame.display.set_caption(f"Hidden Chess - Espectador (Sala: {client_state['room_code']})")
                        else:
                            pygame.display.set_caption(
                                f"Hidden Chess - Jogando de {'Brancas' if client_state['my_color'] == 'w' else 'Pretas'} (Sala: {client_state['room_code']})")
                    else:
                        app_state = "LOBBY"
                        client_state['fakeout_mode_enabled'] = gs.get('fakeout_mode_enabled', True)
                        client_state['score_to_win'] = gs.get('score_to_win', True)
                        client_state['ice_king_enabled'] = gs.get('ice_king_enabled', True)

                elif data['type'] == 'error':
                    error_msg = data['message']
                    if error_msg == "Room not found or full." or error_msg == "Room not found or full":
                        error_msg = "Sala não encontrada ou cheia."
                    elif error_msg == "Room not found." or error_msg == "Room not found":
                        error_msg = "Sala não encontrada."
                    app_state = "MENU"
                    if websocket:
                        await websocket.close()
                        websocket = None

            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print("Websocket error:", e)

        # C. Handle local and remote pygame events
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                break
                
            if ev.type == pygame.VIDEORESIZE:
                if not is_android:
                    WIN_W, WIN_H = ev.w, ev.h
                    screen = pygame.display.set_mode((WIN_W, WIN_H), flags)
            elif ev.type == getattr(pygame, 'APP_DIDENTERFOREGROUND', None) or (ev.type == getattr(pygame, 'WINDOWEVENT', None) and getattr(ev, 'window_event', getattr(ev, 'event', None)) == getattr(pygame, 'WINDOWEVENT_RESTORED', None)):
                if is_android:
                    screen = pygame.display.set_mode((WIN_W, WIN_H), flags)
                
            if app_state == "MENU":
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    if btn_create.collidepoint((mx, my)):
                        play_sound('click')
                        app_state = "CONNECTING"
                        gs = make_state()
                        current_t = client_state.get('theme', 'Classic')
                        client_state = {
                            'theme': current_t,
                            'my_color': None,
                            'waiting': True,
                            'flipped': False,
                            'selected': None,
                            'legal_sq': [],
                            'room_code': None,
                            'is_typing': False,
                            'msg_queue': deque(),
                            'show_hidden': True,
                            'resign_confirm': False,
                            'panel_btns': {},
                            'is_local': False,
                            'fakeout_mode_enabled': False,
                            'score_to_win': False
                        }
                        try:
                            client_state['conn_task'] = asyncio.create_task(connect_and_join(uri, "create_room"))
                        except Exception as e:
                            error_msg = f"Falha ao conectar."
                            app_state = "MENU"
                            
                    elif btn_join.collidepoint((mx, my)):
                        play_sound('click')
                        app_state = "JOINING"
                        client_state['is_spectating_attempt'] = False
                        session_data = load_session()
                        input_text = session_data.get('room_code', "") if session_data else ""
                        error_msg = ""
                        
                    elif btn_spectate.collidepoint((mx, my)):
                        play_sound('click')
                        app_state = "JOINING"
                        client_state['is_spectating_attempt'] = True
                        session_data = load_session()
                        input_text = session_data.get('room_code', "") if session_data else ""
                        error_msg = ""

                    elif btn_local.collidepoint((mx, my)):
                        play_sound('click')
                        start_local_game(is_test=False)
                    elif btn_replays.collidepoint((mx, my)):
                        play_sound('menu')
                        app_state = "REPLAY_LIST"
                        client_state['replay_list'] = load_replay_files()
                        client_state['replay_page'] = 0

            elif app_state == "JOINING":
                if ev.type == pygame.TEXTINPUT and len(input_text) < 4:
                    if ev.text and ev.text.isalnum():
                        input_text += ev.text.upper()
                
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    if 'join_btn_enter' in client_state and client_state['join_btn_enter'].collidepoint((mx, my)):
                        if len(input_text) == 4:
                            app_state = "CONNECTING"
                            try: pygame.key.stop_text_input()
                            except: pass
                            gs = make_state()
                            current_t = client_state.get('theme', 'Classic')
                            client_state = {
                                'theme': current_t,
                                'my_color': None, 'waiting': True, 'flipped': False,
                                'selected': None, 'legal_sq': [], 'room_code': None,
                                'is_typing': False, 'msg_queue': deque(),
                                'show_hidden': True, 'resign_confirm': False,
                                'panel_btns': {}, 'is_local': False, 'score_to_win': False,
                                'fakeout_mode_enabled': False
                            }
                            try:
                                token = None
                                session_data = load_session()
                                if session_data and session_data.get('room_code') == input_text:
                                    token = session_data.get('session_token')
                                action_type = "spectate_room" if client_state.get('is_spectating_attempt') else "join_room"
                                client_state['conn_task'] = asyncio.create_task(connect_and_join(uri, action_type, input_text, token))
                            except Exception as e:
                                error_msg = f"Falha ao conectar."
                                app_state = "MENU"
                    elif 'join_btn_back' in client_state and client_state['join_btn_back'].collidepoint((mx, my)):
                        input_text = input_text[:-1]
                    elif 'join_btn_esc' in client_state and client_state['join_btn_esc'].collidepoint((mx, my)):
                        app_state = "MENU"
                        try: pygame.key.stop_text_input()
                        except: pass
                    elif 'join_input_rect' in client_state and client_state['join_input_rect'].collidepoint((mx, my)):
                        try: pygame.key.start_text_input()
                        except: pass
                    elif 'join_kbt' in client_state:
                        for char, rect in client_state['join_kbt'].items():
                            if rect.collidepoint((mx, my)):
                                if len(input_text) < 4:
                                    input_text += char
                                break

            elif app_state == "REPLAY_LIST":
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    if 'replay_rects' in client_state:
                        for global_idx, rect in client_state['replay_rects'].items():
                            if rect.collidepoint((mx, my)):
                                play_sound('click')
                                replays = client_state['replay_list']
                                rep = replays[global_idx]
                                data = rep['data']
                                try:
                                    th_serialized = data.get("turn_history_serialized", [])
                                    if th_serialized:
                                        loaded_history = [deserialize_state(snap) for snap in th_serialized]
                                    else:
                                        loaded_history = [deserialize_state(data)]
                                except Exception as err:
                                    print("Erro ao carregar o replay:", err)
                                    loaded_history = [deserialize_state(data)]
                                gs = loaded_history[0] if loaded_history else deserialize_state(data)
                                current_t = client_state.get('theme', 'Classic')
                                client_state = {
                                    'theme': current_t,
                                    'my_color': data.get('player_color', 'w'),
                                    'waiting': False,
                                    'flipped': False,
                                    'selected': None,
                                    'legal_sq': [],
                                    'room_code': data.get('room_code', 'LOCAL'),
                                    'is_typing': False,
                                    'msg_queue': deque(),
                                    'show_hidden': True,
                                    'resign_confirm': False,
                                    'panel_btns': {},
                                    'is_local': True,
                                    'is_replay': True,
                                    'turn_start_snapshot': copy.deepcopy(gs),
                                    'turn_history': loaded_history,
                                    'history_index': 0,
                                    'fakeout_mode_enabled': False,
                                    'score_to_win': False
                                }
                                app_state = "REPLAY_VIEW"
                                break
                    if 'replay_btn_back' in client_state and client_state['replay_btn_back'].collidepoint((mx, my)):
                        play_sound('click')
                        app_state = "MENU"
                        client_state.pop('replay_list', None)
                    elif client_state.get('replay_prev_page') and client_state['replay_prev_page'].collidepoint((mx, my)):
                        play_sound('click')
                        client_state['replay_page'] = max(0, client_state.get('replay_page', 0) - 1)
                    elif client_state.get('replay_next_page') and client_state['replay_next_page'].collidepoint((mx, my)):
                        play_sound('click')
                        replays = client_state['replay_list']
                        max_page = (len(replays) - 1) // 5
                        client_state['replay_page'] = min(max_page, client_state.get('replay_page', 0) + 1)

            elif app_state == "REPLAY_VIEW":
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    if mx < BOARD_PX and BOARD_PX <= my < BOARD_PX + PANEL_H:
                        btns = client_state['panel_btns']
                        if btns.get('exit_replay') and btns['exit_replay'].collidepoint((mx, my)):
                            play_sound('click')
                            app_state = "REPLAY_LIST"

            elif app_state == "LOBBY":
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    play_btn_y = WIN_H // 2 - 20
                    play_btn_rect = pygame.Rect((WIN_W - 240) // 2, play_btn_y, 240, 52)
                    
                    back_btn_y = play_btn_y + 80
                    back_btn_rect = pygame.Rect((WIN_W - 160) // 2, back_btn_y, 160, 44)

                    if back_btn_rect.collidepoint((mx, my)):
                        play_sound('click')
                        if websocket:
                            await websocket.send(json.dumps({"type": "leave_room"}))
                            await websocket.close()
                            websocket = None
                        app_state = "MENU"
                        client_state['room_code'] = None

                    if client_state.get('my_color') != 'b':
                        if play_btn_rect.collidepoint((mx, my)):
                            if client_state.get('is_local', False):
                                gs['game_started'] = True
                                gs['fakeout_mode_enabled'] = True
                                gs['score_to_win'] = True
                                gs['ice_king_enabled'] = True
                                client_state['turn_start_snapshot'] = copy.deepcopy(gs)
                                client_state['turn_history'] = [copy.deepcopy(gs)]
                                client_state['history_index'] = 0
                                app_state = "PLAYING"
                                play_sound('start')
                                if client_state.get('is_test'):
                                    pygame.display.set_caption("Hidden Chess - Partida Teste")
                                else:
                                    pygame.display.set_caption("Hidden Chess - Partida Local")
                            else:
                                if gs.get('opponent_joined', False):
                                    if websocket:
                                        await websocket.send(json.dumps({
                                            "type": "action",
                                            "action": "start_game"
                                        }))

            elif app_state == "PLAYING":
                is_local = client_state.get('is_local', False)
                if is_local:
                    client_state['flipped'] = (gs['turn'] == 'b')
                active_color = gs['turn'] if is_local else client_state['my_color']

                if ev.type == pygame.MOUSEBUTTONUP:
                    if client_state.get('is_dragging_nave'):
                        client_state['is_dragging_nave'] = False
                        
                        dx = ev.pos[0] - client_state.get('nave_drag_start_mx', ev.pos[0])
                        dt = pygame.time.get_ticks() - client_state.get('nave_drag_start_time', 0)
                        
                        if abs(dx) > 15 and not client_state.get('nave_moved_during_drag', False):
                            draft_blocks = client_state.get('draft_blocks', [])
                            if draft_blocks:
                                current_sel = client_state.get('selected_block')
                                current_idx = -1
                                for i, (br, bid) in enumerate(draft_blocks):
                                    if bid == current_sel:
                                        current_idx = i
                                        break
                                
                                moved = False
                                if dx < 0:
                                    if current_idx == -1:
                                        client_state['selected_block'] = draft_blocks[-1][1]
                                        moved = True
                                    elif current_idx > 0:
                                        client_state['selected_block'] = draft_blocks[current_idx - 1][1]
                                        moved = True
                                    else:
                                        client_state['nave_error_time'] = pygame.time.get_ticks()
                                elif dx > 0:
                                    if current_idx == -1:
                                        client_state['selected_block'] = draft_blocks[0][1]
                                        moved = True
                                    elif current_idx < len(draft_blocks) - 1:
                                        client_state['selected_block'] = draft_blocks[current_idx + 1][1]
                                        moved = True
                                    else:
                                        client_state['nave_error_time'] = pygame.time.get_ticks()

                                
                                if moved:
                                    play_sound('toggle')
                                    client_state['scroll_to_selected'] = True
                        elif abs(dx) <= 3 and not client_state.get('nave_moved_during_drag', False):
                            draft_blocks = client_state.get('draft_blocks', [])
                            if draft_blocks:
                                client_state['selected_block'] = draft_blocks[-1][1]
                                client_state['scroll_to_selected'] = True
                                play_sound('toggle')
                                client_state['hide_selector_time'] = pygame.time.get_ticks() + 2000

                    if client_state.get('is_dragging_gesture') and not client_state.get('waiting'):
                        mx, my = ev.pos
                        gs = await handle_gesture_release(mx, my, client_state, gs, is_local, websocket, screen, fonts)
                    if client_state.get('is_touch_scrolling_sidebar'):
                        client_state['is_touch_scrolling_sidebar'] = False
                elif ev.type == pygame.MOUSEMOTION:
                    if client_state.get('is_dragging_nave'):
                        mx = ev.pos[0]
                        dx = mx - client_state.get('nave_drag_start_mx', mx)
                        new_offset = client_state.get('nave_drag_start_offset', 0) + dx
                        client_state['nave_offset'] = new_offset
                    elif client_state.get('is_dragging_gesture'):
                        client_state['drag_pos'] = ev.pos
                    elif client_state.get('is_touch_scrolling_sidebar'):
                        my = ev.pos[1]
                        dy = my - client_state.get('touch_scroll_start_y', my)
                        raw_y = client_state.get('touch_scroll_orig_y', 0) + dy
                        
                        max_s = client_state.get('sidebar_max_scroll', 0)
                        min_s = client_state.get('sidebar_min_scroll', 0)
                        
                        if raw_y > max_s:
                            over = raw_y - max_s
                            raw_y = max_s + 150 * (1 - math.exp(-over / 150))
                        elif raw_y < min_s:
                            over = min_s - raw_y
                            raw_y = min_s - 150 * (1 - math.exp(-over / 150))
                            
                        client_state['sidebar_scroll_y'] = raw_y
                elif ev.type == pygame.MOUSEWHEEL:
                    if 'sidebar_scroll_y' not in client_state:
                        client_state['sidebar_scroll_y'] = 0
                    client_state['sidebar_scroll_y'] += ev.y * 20
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                    if ev.button in (4, 5):
                        if 'sidebar_scroll_y' not in client_state:
                            client_state['sidebar_scroll_y'] = 0
                        client_state['sidebar_scroll_y'] += 20 if ev.button == 4 else -20
                        continue
                        
                    if ev.button == 1:
                        if 'hide_selector_time' in client_state:
                            del client_state['hide_selector_time']
                        if 'pill_rect' in client_state and client_state['pill_rect'].collidepoint((mx, my)):
                            client_state['is_dragging_nave'] = True
                            client_state['nave_drag_start_mx'] = mx
                            client_state['nave_drag_start_time'] = pygame.time.get_ticks()
                            client_state['last_nave_move_time'] = pygame.time.get_ticks()
                            client_state['nave_moved_during_drag'] = False
                            client_state['nave_drag_start_offset'] = client_state.get('nave_offset', 0)
                            continue

                        is_sidebar = (my >= BOARD_PX + PANEL_H) if PORTRAIT else (mx >= BOARD_PX)
                        if is_sidebar:
                            client_state['is_touch_scrolling_sidebar'] = True
                            client_state['touch_scroll_start_y'] = my
                            client_state['touch_scroll_orig_y'] = client_state.get('sidebar_scroll_y', 0)
                            
                            clicked_block = False
                            for brect, block_id in client_state.get('draft_blocks', []):
                                if brect.collidepoint((mx, my)):
                                    if client_state.get('selected_block') != block_id:
                                        client_state['selected_block'] = block_id
                                        play_sound('toggle')
                                    clicked_block = True
                                    break

                    if client_state['waiting']:
                        allow_menu = False
                        btns = client_state.get('panel_btns', {})
                        if btns.get('menu') and btns['menu'].collidepoint((mx, my)):
                            allow_menu = True
                        if not allow_menu:
                            continue

                    if mx < BOARD_PX and BOARD_PX <= my < BOARD_PX + PANEL_H:
                        btns = client_state['panel_btns']

                        if btns.get('menu') and btns['menu'].collidepoint((mx, my)):
                            if is_local:
                                app_state = "MENU"
                                client_state['room_code'] = None
                            else:
                                await websocket.send(json.dumps({"type": "leave_room"}))
                                if websocket:
                                    await websocket.close()
                                    websocket = None
                                app_state = "MENU"
                                client_state['room_code'] = None
                            continue
                        
                        if btns.get('chat') and btns['chat'].collidepoint((mx, my)):
                             gs['log'].append("Chat em desenvolvimento...")
                             play_sound('toggle')
                             continue
                        if btns.get('theme') and btns['theme'].collidepoint((mx, my)):
                             current_theme = client_state.get('theme', 'Classic')
                             new_theme = 'Wood' if current_theme == 'Classic' else 'Classic'
                             client_state['theme'] = new_theme
                             load_assets(new_theme)
                             play_sound('toggle')
                             continue
                            
                        if gs['game_over'] or (client_state.get('reconnected_game_over') and client_state.get('waiting')):
                            if btns.get('rematch') and btns['rematch'].collidepoint((mx, my)):
                                if is_local:
                                    is_test_mode = client_state.get('is_test', False)
                                    start_local_game(is_test=is_test_mode)
                                else:
                                    await websocket.send(
                                        json.dumps({"type": "action", "action": "rematch_request"}))
                            elif btns.get('accept') and btns['accept'].collidepoint((mx, my)):
                                if not is_local:
                                    await websocket.send(
                                        json.dumps({"type": "action", "action": "rematch_accept"}))
                            elif btns.get('decline') and btns['decline'].collidepoint((mx, my)):
                                if not is_local:
                                    await websocket.send(
                                        json.dumps({"type": "action", "action": "rematch_decline"}))
                            elif btns.get('export_json') and btns['export_json'].collidepoint((mx, my)):
                                try:
                                    export_data = serialize_game_to_dict(gs, client_state)
                                    filename = f"partida_{int(time.time())}.json"
                                    with open(filename, "w", encoding="utf-8") as f_out:
                                        json.dump(export_data, f_out, indent=4, ensure_ascii=False)
                                    client_state['export_success_msg'] = f"Exportado com sucesso para {filename}!"
                                    gs['log'].append(f"Replay exportado com sucesso para {filename}!")
                                except Exception as e:
                                    client_state['export_success_msg'] = f"Erro no export: {str(e)}"
                            continue

                        if btns.get('export_json') and btns['export_json'].collidepoint((mx, my)):
                            try:
                                export_data = serialize_game_to_dict(gs, client_state)
                                filename = f"partida_{int(time.time())}.json"
                                with open(filename, "w", encoding="utf-8") as f_out:
                                    json.dump(export_data, f_out, indent=4, ensure_ascii=False)
                                client_state['export_success_msg'] = f"Exportado com sucesso para {filename}!"
                                gs['log'].append(f"Replay exportado com sucesso para {filename}!")
                            except Exception as e:
                                client_state['export_success_msg'] = f"Erro no export: {str(e)}"

                        pass
                        
                        if btns.get('toggle_ui') and btns['toggle_ui'].collidepoint((mx, my)):
                            client_state['hide_mechanics_ui'] = not client_state.get('hide_mechanics_ui', False)
                            play_sound('toggle')
                            continue

                        if btns.get('resign') and btns['resign'].collidepoint((mx, my)):
                            if not client_state.get('resign_confirm'):
                                client_state['resign_confirm'] = True
                                play_sound('resign')
                            else:
                                if is_local:
                                    gs['game_over'] = True
                                    winner = 'Pretas' if gs['turn'] == 'w' else 'Brancas'
                                    resigner = 'Brancas' if gs['turn'] == 'w' else 'Pretas'
                                    gs['game_over_msg'] = f"As {resigner} desistiram. As {winner} venceram!"
                                    client_state['resign_confirm'] = False
                                    client_state['_serialize_cache'] = {}
                                    play_sound('game_over')
                                else:
                                    await websocket.send(json.dumps({"type": "action", "action": "resign"}))
                                    client_state['resign_confirm'] = False
                                    client_state['_serialize_cache'] = {}
                        else:
                            client_state['resign_confirm'] = False
                        continue

                    if mx < BOARD_PX and my < BOARD_PX:
                        now = time.time()
                        cc2 = mx // SQ
                        rr2 = my // SQ
                        r = 7 - rr2 if client_state['flipped'] else rr2
                        c = 7 - cc2 if client_state['flipped'] else cc2
                        prev_time = client_state.get('last_sq_click_time', 0.0)
                        prev_coord = client_state.get('last_sq_click_coord')
                        
                        client_state['last_sq_click_time'] = now
                        client_state['last_sq_click_coord'] = (r, c)
                        
                        if prev_coord == (r, c) and (now - prev_time) <= 0.35:
                            h_active = client_state.get('history_active', False)
                            q_key_dc = f'next_queue_{gs["turn"]}'
                            temp_end_en = not h_active and gs['turn'] == active_color and (gs['normal_done'] or gs.get('hidden_count', 0) > 0 or gs.get(q_key_dc))
                            if client_state.get('draft_moves'):
                                temp_end_en = check_draft_endable(client_state['draft_moves'], temp_end_en)
                                    
                            if temp_end_en:
                                if 'shockwaves' not in client_state:
                                    client_state['shockwaves'] = []
                                sq_center_x = (cc2 * SQ) + SQ // 2
                                sq_center_y = (rr2 * SQ) + SQ // 2
                                client_state['shockwaves'].append({
                                    'cx': sq_center_x,
                                    'cy': sq_center_y,
                                    't': 0.0,
                                    'duration': 0.6,
                                    'max_radius': BOARD_PX * 1.4
                                })
                                spawn_particles(sq_center_x, sq_center_y, (50, 245, 105), 30, client_state, size=4.0, speed=240, life=0.5)
                                play_sound('end')
                                
                                dm = client_state.get('draft_moves', [])
                                dm_copy = []
                                for m in dm:
                                    m_dict = copy.deepcopy(m)
                                    if 'type' not in m_dict:
                                        m_dict['type'] = 'move'
                                    dm_copy.append(m_dict)
                                if dm_copy and dm_copy[-1].get('type') != 'end_turn':
                                    temp_dgs = get_draft_state(gs, dm_copy, client_state.get('my_color'))
                                    dm_copy.append({'type': 'end_turn', 'drafted_turn': (temp_dgs['turn_count'] + 1) // 2})
                                    
                                if dm:
                                    client_state['predict_cost_total'] = 0.0
                                else:
                                    refund = client_state.get('predict_cost_total', 0.0)
                                    if refund > 0:
                                        gs['pts'][active_color] = round(gs['pts'][active_color] + refund, 2)
                                    client_state['predict_cost_total'] = 0.0
                                    
                                if is_local:
                                    q_key_sq = f'next_queue_{gs["turn"]}'
                                    if gs['normal_done'] or gs['hidden_count'] > 0 or gs.get(q_key_sq):
                                        
                                        if gs.get('normal_done') or gs.get('hidden_count', 0) > 0:
                                            # Manual move was made
                                            next_a = get_next_turn_from_queue(gs, gs['turn'])
                                            if next_a:
                                                if compare_turns(gs.get('current_turn_actions', []), next_a):
                                                    gs['pts'][gs['turn']] = round(gs['pts'][gs['turn']] + 1, 2)
                                                else:
                                                    gs['pts'][gs['turn']] = round(gs['pts'][gs['turn']] - 1, 2)
                                                    for m in next_a:
                                                        if m.get('type') == 'move':
                                                            c_t = gs['turn']
                                                            htxt = "[Fakeout] " if m.get('fakeout') else "[Sombra] " if m.get('hidden') else ""
                                                            dt_suffix = f"|t{m.get('drafted_turn')}" if m.get('drafted_turn') is not None else ""
                                                            m_text = f"{htxt}{alg(m['fc'], m['fr'])}-{alg(m['tc'], m['tr'])}"
                                                            if m.get('hidden'):
                                                                note_msg = f"Lance abandonado: {m_text}"
                                                                gs['log'].append(f"HIDDEN|{c_t}|{note_msg}|0{dt_suffix}")
                                                                ply_idx = len(gs['log'])
                                                                if 'shadow_history' not in gs: gs['shadow_history'] = {}
                                                                gs['shadow_history'][ply_idx] = {'type': 'HIDDEN', 'color': c_t, 'note': note_msg, 'active': True}
                                                            elif m.get('fakeout'):
                                                                gs['log'].append(f"FAKEOUT|{c_t}|Lance abandonado: {m_text}{dt_suffix}")
                                                            else:
                                                                gs['log'].append(f"NORMAL|{c_t}|Lance abandonado: {m_text}{dt_suffix}")

                                                pop_next_turn_from_queue(gs, gs['turn'])

                                            if dm_copy and dm:
                                                if q_key_sq not in gs: gs[q_key_sq] = []
                                                gs[q_key_sq].extend(dm_copy)
                                            end_turn(gs)
                                        else:
                                            # No manual move
                                            if dm_copy and dm:
                                                if q_key_sq not in gs: gs[q_key_sq] = []
                                                gs[q_key_sq].extend(dm_copy)
                                            
                                            if gs.get(q_key_sq):
                                                process_next_queues(gs)
                                            else:
                                                end_turn(gs)
                                        if in_check(get_absolute_board(gs), gs['turn']):
                                            play_sound('check')
                                        if gs.get('reveal_flashes'):
                                            for rf in gs['reveal_flashes']:
                                                rr, rc = rf[0], rf[1]
                                                rtype = rf[2] if len(rf) > 2 else 'hidden'
                                                col = (245, 120, 20) if rtype == 'fakeout' else (60, 110, 220)
                                                trigger_square_flash(client_state, rr, rc, col, rtype)
                                            gs['reveal_flashes'] = []
                                        gs['hidden_mode'] = False
                                        client_state['turn_start_snapshot'] = copy.deepcopy(gs)
                                        client_state['turn_history'].append(copy.deepcopy(gs))
                                        client_state['history_index'] = len(client_state['turn_history']) - 1
                                else:
                                    if dm_copy:
                                        await websocket.send(json.dumps({"type": "action", "action": "end_turn", "draft_moves": dm_copy}))
                                    else:
                                        await websocket.send(json.dumps({"type": "action", "action": "end_turn"}))
                                client_state['drafting'] = False
                                client_state['draft_moves'] = []
                                client_state['selected'] = None
                                client_state['legal_sq'] = []
                                continue

                        if client_state.get('history_active', False): continue
                        if gs['turn'] != active_color: continue
                        if not gs.get('fakeout_active', False):
                            can_fakeout = gs.get('hidden_count', 0) == 1 and gs.get('fakeout_count', 0) == 0 and not gs.get('fakeout_used', False)
                            if (gs['normal_done'] or (gs.get('hidden_count', 0) > 0 and not can_fakeout)) and not client_state.get('drafting'): continue
                            if gs['hidden_mode'] and not can_afford(gs): continue

                        cc2 = mx // SQ
                        rr2 = my // SQ
                        r = 7 - rr2 if client_state['flipped'] else rr2
                        c = 7 - cc2 if client_state['flipped'] else cc2
                        curr_dgs = get_draft_state(gs, client_state.get('draft_moves', []), client_state.get('my_color')) if client_state.get('drafting') else gs
                        tb = get_true_board(curr_dgs, gs['turn'])
                        p_on_sq = tb[r][c]
                        is_my_casca = False
                        my_hidden = curr_dgs["hidden_w"] if gs["turn"] == "w" else curr_dgs["hidden_b"]
                        for val in my_hidden.values():
                            if val.pub_pos == (r, c):
                                is_my_casca = True
                                p_on_sq = val.piece
                                break

                        if is_my_casca and not gs.get('fakeout_active', False) and not client_state.get('draft_fakeout', False):
                            can_fakeout = gs.get('hidden_count', 0) == 1 and gs.get('fakeout_count', 0) == 0 and not gs.get('fakeout_used', False)
                            if can_fakeout and can_afford_fakeout(curr_dgs):
                                client_state['casca_auto_fakeout'] = True
                                await MechanicsManager.execute_toggle_fakeout(gs, client_state, client_state.get('is_local', False), websocket, play_sound, None, click_pos=(mx, my), force_shockwave=True)
                        is_opponent = p_on_sq is not None and pc(p_on_sq) != gs["turn"]
                        
                        if is_opponent and (client_state.get('drafting') or gs['normal_done']):
                            gs_temp = copy.deepcopy(gs)
                            gs_temp['turn'] = 'b' if gs['turn'] == 'w' else 'w'
                            gs_temp['hidden_mode'] = False
                            gs_temp['fakeout_active'] = False
                            legs = legal(gs_temp, r, c)
                            if legs is not None:
                                client_state['predicting_mode'] = True
                                client_state['selected'] = (r, c)
                                client_state['legal_sq'] = legs
                                play_sound('select')
                                client_state['is_dragging_gesture'] = True
                                client_state['drag_piece_sq'] = (r, c)
                                client_state['drag_piece_name'] = p_on_sq
                                client_state['drag_pos'] = (mx, my)
                                client_state['gesture_timer'] = 0.0
                                client_state['hidden_triggered'] = False
                                client_state['fakeout_triggered'] = False
                            continue

                        if (p_on_sq is not None and pc(p_on_sq) == gs["turn"]) or is_my_casca:
                            if client_state.get('selected') == (r, c):
                                client_state['selected'] = None
                                client_state['legal_sq'] = []
                                if gs.get('hidden_mode'):
                                    gs['hidden_mode'] = False
                                    play_sound('hidden_off')
                                elif client_state.get('draft_hidden'):
                                    client_state['draft_hidden'] = False
                                    play_sound('hidden_off')
                                else:
                                    play_sound('select')
                                continue
                            gs_temp = copy.copy(gs)
                            gs_temp['drafting_active'] = client_state.get('drafting', False)
                            if client_state.get('drafting'):
                                gs_temp['fakeout_active'] = client_state.get('draft_fakeout', False)
                                gs_temp['hidden_mode'] = client_state.get('draft_hidden', False)
                            sel, legs = get_ui_selection(gs_temp, r, c, draft_moves=client_state.get('draft_moves', []))
                            if sel is not None:
                                client_state['predicting_mode'] = False
                                client_state['selected'] = sel
                                client_state['legal_sq'] = legs
                                play_sound('select')
                                client_state['is_dragging_gesture'] = True
                                client_state['drag_piece_sq'] = (r, c)
                                client_state['drag_piece_name'] = p_on_sq
                                client_state['drag_pos'] = (mx, my)
                                client_state['gesture_timer'] = 0.0
                                client_state['hidden_triggered'] = False
                                client_state['fakeout_triggered'] = False
                                continue

                        if client_state['selected']:
                            sr, sc = client_state['selected']
                            target_p = tb[r][c]
                            
                            # --- ICE KING CHECK (Standard) ---
                            if target_p and pt(tb[sr][sc]) == 'K' and pc(tb[sr][sc]) == gs['turn'] and pc(target_p) == gs['turn'] and pt(target_p) != 'K':
                                res = ice_king_interaction(gs, sr, sc, r, c)
                                if res:
                                    if res == 'frozen':
                                        trigger_freeze_effect(client_state, gs, r, c)
                                    else:
                                        trigger_unfreeze_effect(client_state, gs, r, c)
                                    
                                    if not is_local:
                                        await websocket.send(json.dumps({
                                            "type": "action", "action": "ice_king",
                                            "kr": sr, "kc": sc, "tr": r, "tc": c
                                        }))
                                    
                                    client_state['selected'] = None
                                    client_state['legal_sq'] = []
                                    if gs.get('fakeout_active') or client_state.get('draft_fakeout'):
                                        gs['fakeout_active'] = False
                                        client_state['draft_fakeout'] = False
                                    elif gs.get('hidden_mode') or client_state.get('draft_hidden'):
                                        gs['hidden_mode'] = False
                                        client_state['draft_hidden'] = False
                                    continue
                            # --- END ICE KING CHECK ---

                            if target_p and pt(tb[sr][sc]) == 'K' and pc(tb[sr][sc]) == gs['turn'] and pt(target_p) == 'R' and pc(
                                    target_p) == gs['turn']:
                                c = 6 if c == 7 else 2

                        if client_state.get('predicting_mode'):
                            if (r, c) in client_state['legal_sq']:
                                sr, sc = client_state['selected']
                                gs_temp = copy.deepcopy(gs)
                                gs_temp['turn'] = 'b' if gs['turn'] == 'w' else 'w'
                                tb_temp = get_true_board(gs_temp, gs_temp['turn'])
                                p_target = tb_temp[r][c]
                                p_selected = tb_temp[sr][sc]
                                is_casca = p_selected is None
                                if is_casca:
                                    my_hidden = gs_temp["hidden_w"] if gs_temp["turn"] == "w" else gs_temp["hidden_b"]
                                    for val in my_hidden.values():
                                        if val.pub_pos == (sr, sc):
                                            p_selected = val.piece
                                            break

                                promo = None
                                if p_selected and pt(p_selected) == 'P' and r in (0, 7):
                                    promo = await ask_promo(screen, fonts, gs_temp['turn'], websocket, client_state)

                                if is_local:
                                    if register_predict_move(gs, gs['turn'], sr, sc, r, c, promo, cost=0.2):
                                        client_state['predict_cost_total'] = round(client_state.get('predict_cost_total', 0.0) + 0.2, 2)
                                        play_sound('capture' if p_target is not None else 'move')
                                    else:
                                        play_sound('error')
                                        gs['log'].append({'text': 'Pontuação insuficiente', 'color_type': 'predict'})
                                        trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
                                else:
                                    if gs['pts'][gs['turn']] >= 0.2:
                                        play_sound('capture' if p_target is not None else 'move')
                                        payload = {
                                            'type': 'action',
                                            'action': 'predict_move',
                                            'fr': sr,
                                            'fc': sc,
                                            'tr': r,
                                            'tc': c,
                                            'promo': promo
                                        }
                                        if client_state.get('draft_moves'):
                                            payload['draft_moves'] = client_state['draft_moves']
                                        await websocket.send(json.dumps(payload))
                                    else:
                                        play_sound('error')
                                        gs['log'].append({'text': 'Pontuação insuficiente', 'color_type': 'predict'})
                                        trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
                            else:
                                play_sound('error')
                                trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
                                
                            client_state['selected'] = None
                            client_state['legal_sq'] = []
                            continue

                        if client_state['selected']:
                            if (r, c) in client_state['legal_sq']:
                                sr, sc = client_state['selected']
                                curr_dgs_click = get_draft_state(gs, client_state.get('draft_moves', []), client_state.get('my_color')) if client_state.get('drafting') else gs
                                tb_click = get_true_board(curr_dgs_click, gs['turn'])
                                p_click = tb_click[sr][sc]
                                is_casca_drag = p_click is None
                                is_fakeout_active_now = client_state.get('draft_fakeout', False) if client_state.get('drafting') else gs.get('fakeout_active', False)
                                
                                if is_casca_drag and not is_fakeout_active_now:
                                    play_sound('error')
                                    trigger_square_flash(client_state, r, c, (230, 60, 60), 'gesture_invalid')
                                    client_state['selected'] = None
                                    client_state['legal_sq'] = []
                                    continue

                                conflict = check_conflict(gs, sr, sc, r, c)
                                if conflict:
                                    if is_local:
                                        kind, cr2, cc3 = conflict
                                        if kind == 'src':
                                            gs['board'][cr2][cc3] = None
                                            my_cap = gs['captured_w'] if gs['turn'] == 'w' else gs['captured_b']
                                            my_cap.discard((cr2, cc3))
                                            ghost_type = 'hidden'
                                            
                                            for h_dict in [gs.get('hidden_w', {}), gs.get('hidden_b', {})]:
                                                to_remove = []
                                                for tp, val in list(h_dict.items()):
                                                    pub_pos = val.pub_pos
                                                    is_f = val.is_fakeout
                                                    if pub_pos == (cr2, cc3) or tp == (cr2, cc3):
                                                         if is_f:
                                                             ghost_type = 'fakeout'
                                                         deactivate_plies(gs, val.plies)
                                                         if is_f:
                                                             to_remove.append(tp)
                                                for tp in to_remove:
                                                    h_dict.pop(tp, None)
                                            if ghost_type == 'fakeout':
                                                gs['log'].append(f"SYS_FAKEOUT|Peça desapareceu em {alg(cc3, cr2)}!")
                                            else:
                                                gs['log'].append(f"SYS_HIDDEN|Peça desapareceu em {alg(cc3, cr2)}!")
                                            if 'reveal_flashes' not in gs:
                                                gs['reveal_flashes'] = []
                                            gs['reveal_flashes'].append([cr2, cc3, ghost_type])
                                        elif kind == 'dst':
                                            enemy_hid = gs['hidden_b'] if gs['turn'] == 'w' else gs['hidden_w']
                                            val = enemy_hid.pop((cr2, cc3), None)
                                            if val:
                                                pub_pos, hp = val.pub_pos, val.piece
                                                is_f = val.is_fakeout
                                                if pub_pos: gs['board'][pub_pos[0]][pub_pos[1]] = None
                                                gs['board'][cr2][cc3] = hp
                                                enemy_cap = gs['captured_w'] if gs['turn'] == 'w' else gs['captured_b']
                                                enemy_cap.discard((cr2, cc3))
                                                if is_f:
                                                    gs['log'].append(f"SYS_FAKEOUT|Peça revelada em {alg(cc3, cr2)}!")
                                                else:
                                                    gs['log'].append(f"SYS_HIDDEN|Peça revelada em {alg(cc3, cr2)}!")
                                                
                                                deactivate_plies(gs, val.plies)
                                                if 'reveal_flashes' not in gs:
                                                    gs['reveal_flashes'] = []
                                                gs['reveal_flashes'].append([cr2, cc3, 'fakeout' if is_f else 'hidden'])
                                        
                                        if gs.get('reveal_flashes'):
                                            for rf in gs['reveal_flashes']:
                                                rr, rc = rf[0], rf[1]
                                                rtype = rf[2] if len(rf) > 2 else 'hidden'
                                                col = (245, 120, 20) if rtype == 'fakeout' else (60, 110, 220)
                                                trigger_square_flash(client_state, rr, rc, col, rtype)
                                            gs['reveal_flashes'] = []
                                        
                                        client_state['selected'] = None
                                        client_state['legal_sq'] = []
                                    else:
                                        await websocket.send(json.dumps(
                                            {"type": "action", "action": "conflict_resolve",
                                             "conflict": conflict}))
                                        client_state['selected'] = None
                                        client_state['legal_sq'] = []
                                else:
                                    promo = None
                                    p = tb[sr][sc]
                                    if p is None:
                                        my_hid = curr_dgs_click["hidden_w"] if gs["turn"] == "w" else curr_dgs_click["hidden_b"]
                                        for val in my_hid.values():
                                            if val.pub_pos == (sr, sc):
                                                p = val.piece
                                                break
                                    if p and pt(p) == "P" and r in (0, 7):
                                        promo = await ask_promo(screen, fonts, active_color, websocket, client_state)

                                    is_auto_draft = not client_state.get('drafting') and gs.get('hidden_count', 0) > 0 and not (gs.get('fakeout_active', False) or client_state.get('fakeout_triggered', False))
                                    if client_state.get('drafting') or is_auto_draft:
                                        if is_auto_draft:
                                            client_state['drafting'] = True
                                        d_moves = client_state.get('draft_moves', [])
                                        dgs = get_draft_state(gs, d_moves, client_state.get('my_color'))
                                        is_fake = client_state.get('draft_fakeout', False) or gs.get('fakeout_active', False)
                                        is_hid = client_state.get('draft_hidden', False) or gs.get('hidden_mode', False)
                                        dgs['fakeout_active'] = is_fake
                                        dgs['hidden_mode'] = is_hid
                                        legals = legal(dgs, sr, sc)
                                        if (r, c) in legals:
                                            is_fake = client_state.get('draft_fakeout', False)
                                            d_moves.append({
                                                'type': 'move',
                                                'fr': sr, 'fc': sc, 'tr': r, 'tc': c,
                                                'hidden': is_hid,
                                                'fakeout': is_fake,
                                                'promo': promo,
                                                'drafted_turn': ((dgs['turn_count'] + 1) // 2) - (1 if is_fake else 0)
                                            })
                                            client_state['draft_moves'] = d_moves
                                            
                                            play_sound('next_move')
                                            client_state['draft_hidden'] = False
                                            client_state['draft_fakeout'] = False
                                            if gs.get('hidden_mode', False) and not is_local:
                                                await websocket.send(json.dumps({"type": "action", "action": "toggle_hidden"}))
                                            if gs.get('fakeout_active', False) and not is_local:
                                                await websocket.send(json.dumps({"type": "action", "action": "toggle_fakeout"}))
                                            gs['hidden_mode'] = False
                                            gs['fakeout_active'] = False
                                            client_state['fill_fade_timer'] = 1.0
                                            d = d_moves[-1]
                                            d_fr, d_fc, d_tr, d_tc = d['fr'], d['fc'], d['tr'], d['tc']
                                            is_hid = d.get('hidden', False)
                                            is_fake = d.get('fakeout', False)
                                            col = (245, 120, 20) if is_fake else ((30, 110, 255) if is_hid else (239, 68, 68))
                                            sqs = [(d_tr, d_tc, col, 255, False)]
                                            dr, dc = d_tr - d_fr, d_tc - d_fc
                                            steps = max(abs(dr), abs(dc))
                                            if (abs(dr) == 2 and abs(dc) == 1) or (abs(dr) == 1 and abs(dc) == 2):
                                                mid_r, mid_c = (d_tr, d_fc) if abs(dr) == 2 else (d_fr, d_tc)
                                                sqs.append((mid_r, mid_c, col, 127, False))
                                            elif steps > 0:
                                                alpha = 127
                                                for i in range(steps - 1, 0, -1):
                                                    sq_r = d_fr + int(i * dr / steps)
                                                    sq_c = d_fc + int(i * dc / steps)
                                                    sqs.append((sq_r, sq_c, col, alpha, False))
                                                    alpha = max(10, alpha // 2)
                                            client_state['fade_squares'] = sqs
                                        client_state['selected'] = None
                                        client_state['legal_sq'] = []
                                    else:
                                        if is_local:
                                            old_game_over = gs.get('game_over', False)
                                            old_last = gs.get('last_move')
                                            n_cap_w = len(gs.get('captured_w', []))
                                            n_cap_b = len(gs.get('captured_b', []))
                                            
                                            has_captured_piece_on_square = False
                                            if gs.get('board') and 0 <= r < 8 and 0 <= c < 8:
                                                has_captured_piece_on_square = gs['board'][r][c] is not None
                                                
                                            is_fakeout = gs.get('fakeout_active', False)
                                            res = exec_move(gs, sr, sc, r, c, hidden_move=gs.get('hidden_mode', False), promo=promo)
                                            if res:
                                                if 'current_turn_actions' not in gs: gs['current_turn_actions'] = []
                                                gs['current_turn_actions'].append({
                                                    'type': 'move', 'fr': sr, 'fc': sc, 'tr': r, 'tc': c,
                                                    'promo': promo, 'hidden': gs.get('hidden_mode', False),
                                                    'fakeout': is_fakeout
                                                })
                                            
                                            new_last = gs.get('last_move')
                                            
                                            cap_w = len(gs.get('captured_w', [])) > n_cap_w
                                            cap_b = len(gs.get('captured_b', [])) > n_cap_b
                                            
                                            if res and old_last != new_last and new_last:
                                                nfr, nfc, ntr, ntc = new_last
                                                
                                                is_capture_by_log = False
                                                if gs.get('log'):
                                                    norm_last_log = gs['log'][-1].lower()
                                                    if "capturado" in norm_last_log or "capturada" in norm_last_log:
                                                        is_capture_by_log = True
                                                    elif 'x' in norm_last_log:
                                                        without_xeque = norm_last_log.replace("xeque", "")
                                                        if 'x' in without_xeque:
                                                            is_capture_by_log = True
                                                
                                                is_capture = cap_w or cap_b or has_captured_piece_on_square or res == "ghost_capture" or is_capture_by_log
                                                
                                                p_anim = gs['board'][ntr][ntc]
                                                if not p_anim:
                                                    for h_dict in [gs.get('hidden_w', {}), gs.get('hidden_b', {})]:
                                                        if (ntr, ntc) in h_dict:
                                                            target_val = h_dict[(ntr, ntc)]
                                                            p_anim = target_val.piece if hasattr(target_val, 'piece') else target_val[1]
                                                            break
                                                if p_anim:
                                                    trigger_piece_anim(client_state, p_anim, nfr, nfc, ntr, ntc, gs.get('hidden_mode', False), gs.get('fakeout_used', False) or gs.get('fakeout_active', False), is_capture)
                                                
                                                is_fakeout = gs.get('fakeout_used', False)
                                                is_shadow = gs.get('hidden_count', 0) > 0
                                                if gs.get('game_over', False) and not old_game_over:
                                                    play_sound('game_over')
                                                elif is_capture: play_sound('capture')
                                                else: play_sound('move')
                                                
                                            if res == "ghost_capture":
                                                gc_type = gs.get('ghost_capture_type', 'standard')
                                                col = (245, 120, 20) if gc_type == 'fakeout' else (60, 110, 220)
                                                trigger_square_flash(client_state, r, c, col, gc_type)
                                                gs['ghost_capture_flash'] = None
                                                gs['ghost_capture_type'] = None

                                            if gs.get('reveal_flashes'):
                                                for r_fl in gs['reveal_flashes']:
                                                    rr, rc = r_fl[0], r_fl[1]
                                                    rtype = r_fl[2] if len(r_fl) > 2 else 'hidden'
                                                    col = (245, 120, 20) if rtype == 'fakeout' else (60, 110, 220)
                                                    trigger_square_flash(client_state, rr, rc, col, rtype)
                                                gs['reveal_flashes'] = []

                                            client_state['selected'] = None
                                            client_state['legal_sq'] = []
                                            gs['hidden_mode'] = False
                                        else:
                                            move_cmd = {
                                                "type": "action", "action": "move",
                                                "fr": sr, "fc": sc, "tr": r, "tc": c, "promo": promo
                                            }
                                            await websocket.send(json.dumps(move_cmd))
                                            client_state['selected'] = None
                                            client_state['legal_sq'] = []
                            else:
                                gs_temp = copy.copy(gs)
                                gs_temp['drafting_active'] = client_state.get('drafting', False)
                                if client_state.get('drafting'):
                                    gs_temp['fakeout_active'] = client_state.get('draft_fakeout', False)
                                    gs_temp['hidden_mode'] = client_state.get('draft_hidden', False)
                                sel, legs = get_ui_selection(gs_temp, r, c, draft_moves=client_state.get('draft_moves', []))
                                if sel is not None:
                                    client_state['selected'] = sel
                                    client_state['legal_sq'] = legs
                                    play_sound('select')
                                else:
                                    client_state['selected'] = None
                                    client_state['legal_sq'] = []
                                    if gs.get('fakeout_active') or client_state.get('draft_fakeout'):
                                        await MechanicsManager.execute_toggle_fakeout(gs, client_state, is_local, websocket, play_sound, None)
                                    elif gs.get('hidden_mode') or client_state.get('draft_hidden'):
                                        await MechanicsManager.execute_toggle_hidden(gs, client_state, is_local, websocket, play_sound, None)
                        else:
                            gs_temp = copy.copy(gs)
                            gs_temp['drafting_active'] = client_state.get('drafting', False)
                            if client_state.get('drafting'):
                                gs_temp['fakeout_active'] = client_state.get('draft_fakeout', False)
                                gs_temp['hidden_mode'] = client_state.get('draft_hidden', False)
                            sel, legs = get_ui_selection(gs_temp, r, c, draft_moves=client_state.get('draft_moves', []))
                            if sel is not None:
                                client_state['selected'] = sel
                                client_state['legal_sq'] = legs
                                play_sound('select')
                            # do not clear selection if clicking empty square when not selected

        if not running:
            break

        screen.fill(BG)

        if app_state == "INTRO_ANIM":
            screen.fill((0, 0, 0))
            if 'intro_start' not in client_state:
                client_state['intro_start'] = pygame.time.get_ticks()
            t_ms = pygame.time.get_ticks() - client_state['intro_start']
            cx, cy = WIN_W // 2, WIN_H // 2
            
            p_str = 'wP'
            img = IMAGES.get(p_str)
            if img:
                base_img = pygame.transform.smoothscale(img, (SQ, SQ))
            else:
                base_img = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                t_surf = fonts['piece'].render(GLYPHS[p_str], True, (255, 255, 255))
                base_img.blit(t_surf, t_surf.get_rect(center=(SQ//2, SQ//2)))

            current_cy = cy
            if t_ms >= 5500 and t_ms < 7500:
                p_up = min(1.0, (t_ms - 5500) / 500.0)
                current_cy = cy - (p_up * p_up * 150)
                
            if t_ms < 7500:
                if 'intro_flame_particles' not in client_state:
                    client_state['intro_flame_particles'] = []
                if t_ms < 5500 or (t_ms >= 5500 and t_ms < 6000):
                    for _ in range(2):
                        px = cx + random.randint(-SQ//3, SQ//3)
                        py = int(current_cy) + random.randint(0, int(SQ*0.5))
                        client_state['intro_flame_particles'].append(FlameParticle(px, py, r=random.randint(4, 7), vx=0, vy=0, color_type='blue'))

            if client_state.get('intro_flame_particles'):
                for p in client_state['intro_flame_particles']:
                    p.update()
                    p.draw(screen)
                client_state['intro_flame_particles'] = [p for p in client_state['intro_flame_particles'] if p.r > 1]

            if t_ms < 1500:
                p = t_ms / 1500.0
                alpha = int(255 * p)
                scale = 1.3 - 0.3 * p
                size = int(SQ * scale)
                s_img = pygame.transform.smoothscale(base_img, (size, size))
                s_img.set_alpha(alpha)
                screen.blit(s_img, s_img.get_rect(center=(cx, int(current_cy))))
            elif t_ms < 5500:
                s_img = pygame.transform.smoothscale(base_img, (SQ, SQ))
                screen.blit(s_img, s_img.get_rect(center=(cx, int(current_cy))))
                
                bar_w = 80
                bar_h = 2
                bx = cx - bar_w // 2
                by = int(current_cy) + SQ // 2 + 10
                p_bar = (t_ms - 1500) / 4000.0
                draw_rect_aa(screen, (30, 30, 35), pygame.Rect(bx, by, bar_w, bar_h))
                draw_rect_aa(screen, (240, 240, 245), pygame.Rect(bx, by, int(bar_w * p_bar), bar_h))
            elif t_ms < 7500:
                p_up = min(1.0, (t_ms - 5500) / 500.0)
                alpha = int(255 * (1.0 - p_up))
                if alpha > 0:
                    s_img = pygame.transform.smoothscale(base_img, (SQ, SQ))
                    s_img.set_alpha(alpha)
                    screen.blit(s_img, s_img.get_rect(center=(cx, int(current_cy))))
            if t_ms >= 7500:
                app_state = "MENU"

        if app_state == "MENU":
            if 'menu_anim_t' not in client_state or client_state.get('menu_anim_state') != app_state:
                client_state['menu_anim_t'] = pygame.time.get_ticks()
                client_state['menu_anim_state'] = app_state
                client_state['menu_anim_flash'] = False

            m_ms = pygame.time.get_ticks() - client_state['menu_anim_t']
            
            cx = WIN_W // 2
            cy = menu_y_start - 160
            
            if not client_state['menu_anim_flash'] and m_ms > 200:
                play_sound('move')
                spawn_particles(cx, cy, (245, 120, 20), 16, client_state, size=3.5, speed=120, life=0.35)
                client_state['menu_anim_flash'] = True
               
            p_str = 'wK'
            if p_str in IMAGES:
                k_img = pygame.transform.smoothscale(IMAGES[p_str], (SQ, SQ))
            else:
                k_img = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                k_surf = fonts['piece'].render(GLYPHS[p_str], True, (255, 255, 255))
                k_img.blit(k_surf, k_surf.get_rect(center=(SQ//2, SQ//2)))

            if m_ms > 200:
                anim_dur = 400
                progress = min(1.0, (m_ms - 200) / anim_dur)
                k_alpha = int(255 * progress)
                current_y = (cy - 40) + 40 * progress
                
                if progress < 1.0:
                    trail = k_img.copy()
                    trail.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
                    for step in range(1, 4):
                        prev_y = (cy - 40) + 40 * max(0, progress - step*0.1)
                        if prev_y < current_y:
                            trail_alpha = int(120 * (1.0 - step/4.0) * progress)
                            trail.set_alpha(trail_alpha)
                            screen.blit(trail, trail.get_rect(center=(cx, int(prev_y))))
                
                drawn_k = k_img.copy()
                drawn_k.set_alpha(k_alpha)
                
                if progress >= 1.0:
                    if 'menu_flame_particles' not in client_state:
                        client_state['menu_flame_particles'] = []
                    for _ in range(2):
                        px = cx + random.randint(-SQ//3, SQ//3)
                        py = int(current_y) + random.randint(0, int(SQ*0.5))
                        client_state['menu_flame_particles'].append(FlameParticle(px, py, r=random.randint(4, 7), vx=0, vy=0, color_type='orange'))

            if client_state.get('menu_flame_particles'):
                for p in client_state['menu_flame_particles']:
                    p.update()
                    p.draw(screen)
                client_state['menu_flame_particles'] = [p for p in client_state['menu_flame_particles'] if p.r > 1]
                
            if m_ms > 200:
                screen.blit(drawn_k, drawn_k.get_rect(center=(cx, int(current_y))))
                
            if client_state.get('particles'):
                for p in client_state['particles']:
                    alpha = max(0, min(255, int(255 * (p['life'] / p['max_life']))))
                    size = max(1, int(p['size'] * (p['life'] / p['max_life'])))
                    psurf = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
                    pygame.draw.circle(psurf, (*p['color'], alpha), (size, size), size)
                    screen.blit(psurf, (int(p['x'] - size), int(p['y'] - size)))

            draw_text_center(screen, "Hidden Chess", title_font, T_MAIN, menu_y_start - 80)
            draw_text_center(screen, "v1.5.4", fonts['small'], T_DIM, menu_y_start - 40)
            
            draw_fancy_btn(screen, "Criar Jogo", fonts['big'], BTN_N, BTN_H, BTN_TXT, btn_create, is_hover=btn_create.collidepoint(mouse))
            draw_fancy_btn(screen, "Entrar no Jogo", fonts['big'], BTN_N, BTN_H, BTN_TXT, btn_join, is_hover=btn_join.collidepoint(mouse))
            draw_fancy_btn(screen, "Assistir jogo", fonts['big'], BTN_N, BTN_H, BTN_TXT, btn_spectate, is_hover=btn_spectate.collidepoint(mouse))
            draw_fancy_btn(screen, "Jogar localmente", fonts['big'], BTN_N, BTN_H, BTN_TXT, btn_local, is_hover=btn_local.collidepoint(mouse))
            draw_fancy_btn(screen, "Replays", fonts['big'], BTN_N, BTN_H, BTN_TXT, btn_replays, is_hover=btn_replays.collidepoint(mouse))

            if error_msg:
                if 'last_error_msg' not in client_state or client_state['last_error_msg'] != error_msg:
                    client_state['last_error_msg'] = error_msg
                    client_state['error_time'] = pygame.time.get_ticks()
                elif pygame.time.get_ticks() - client_state.get('error_time', 0) > 4000:
                    error_msg = ""
                    client_state['last_error_msg'] = ""
                
                if error_msg:
                    draw_text_center(screen, error_msg, fonts['small'], T_RED, menu_y_start + 400)
                
            draw_text_center(screen, "By Loopyin", fonts['small'], (150, 150, 150), WIN_H - 30)

        elif app_state == "CONNECTING":
            draw_text_center(screen, "CONECTANDO AO SERVIDOR...", fonts['big'], T_MAIN, WIN_H // 2 - 25)
            draw_text_center(screen, "Por favor, aguarde.", fonts['small'], T_DIM, WIN_H // 2 + 25)

        elif app_state == "JOINING":
            if client_state.get('is_spectating_attempt'):
                draw_text_center(screen, "DIGITE O CÓDIGO DA SALA (ESPECTADOR):", fonts['big'], T_MAIN, WIN_H // 2 - 80)
            else:
                draw_text_center(screen, "DIGITE O CÓDIGO DA SALA:", fonts['big'], T_MAIN, WIN_H // 2 - 80)
            box_w = 160
            input_rect = pygame.Rect(WIN_W // 2 - box_w // 2, WIN_H // 2 - 40, box_w, 60)
            client_state['join_input_rect'] = input_rect
            
            draw_rect_aa(screen, (40, 40, 45), input_rect, 5)
            draw_rect_aa(screen, (80, 120, 220), input_rect, 5, 2)
            draw_text_center(screen, input_text, title_font, (255, 255, 255), input_rect.centery)

            btn_gap = 10
            bw = 100
            bx_center = WIN_W // 2
            
            # Apagar btn
            btn_apagar = pygame.Rect(bx_center - bw // 2 - bw - btn_gap, WIN_H // 2 + 65, bw, 40)
            is_hover_a = btn_apagar.collidepoint(mouse)
            has_text = len(input_text) > 0
            draw_fancy_btn(screen, "Apagar", fonts['small'], (120, 50, 50), (150, 60, 60), (255, 255, 255), btn_apagar, is_hover=has_text and is_hover_a, is_disabled=not has_text, custom_radius=6)
            client_state['join_btn_back'] = btn_apagar
            
            # Entrar btn
            btn_entrar = pygame.Rect(bx_center - bw // 2, WIN_H // 2 + 65, bw, 40)
            is_hover_e = btn_entrar.collidepoint(mouse)
            can_enter = len(input_text) == 4
            draw_fancy_btn(screen, "Entrar", fonts['small'], (30, 110, 200), (50, 130, 230), (255, 255, 255), btn_entrar, is_hover=can_enter and is_hover_e, is_disabled=not can_enter, custom_radius=6)
            client_state['join_btn_enter'] = btn_entrar

            # Voltar btn
            btn_voltar = pygame.Rect(bx_center + bw // 2 + btn_gap, WIN_H // 2 + 65, bw, 40)
            draw_fancy_btn(screen, "Cancelar", fonts['small'], BTN_N, BTN_H, BTN_TXT, btn_voltar, is_hover=btn_voltar.collidepoint(mouse), custom_radius=6)
            client_state['join_btn_esc'] = btn_voltar

            keyboard_y = WIN_H // 2 + 130
            key_w = min(36, (WIN_W - 20) // 10 - 4)
            key_h = 44
            key_gap = 4
            rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
            client_state['join_kbt'] = {}
            for r, row in enumerate(rows):
                row_w = len(row) * key_w + (len(row) - 1) * key_gap
                start_x = WIN_W // 2 - row_w // 2
                for i, char in enumerate(row):
                    kval = pygame.Rect(start_x + i * (key_w + key_gap), keyboard_y + r * (key_h + key_gap), key_w, key_h)
                    client_state['join_kbt'][char] = kval
                    draw_fancy_btn(screen, char, fonts['small'], (50, 50, 55), (70, 70, 75), (255, 255, 255), kval, is_hover=kval.collidepoint(mouse), custom_radius=4)

        elif app_state == "LOBBY":
            draw_text_center(screen, "Aguardando", title_font, T_MAIN, WIN_H // 2 - 240)
            
            if client_state.get('is_local', False):
                pass
            else:
                room_type = "Online"
                draw_text_center(screen, room_type, fonts['small'], T_DIM, WIN_H // 2 - 200)
                draw_text_center(screen, f"CÓDIGO DA SALA: {client_state.get('room_code', '').upper()}", fonts['small'], T_BLUE, WIN_H // 2 - 175)
                if gs.get('opponent_joined', False):
                    draw_text_center(screen, "OPONENTE CONECTADO!", fonts['small'], (100, 220, 100), WIN_H // 2 - 150)
                else:
                    draw_text_center(screen, "AGUARDANDO OPONENTE...", fonts['small'], T_DIM, WIN_H // 2 - 150)

            play_btn_y = WIN_H // 2 - 20
            play_btn_rect = pygame.Rect((WIN_W - 240) // 2, play_btn_y, 240, 52)

            if client_state.get('my_color') == 'b':
                draw_text_center(screen, "AGUARDANDO O ANFITRIÃO INICIAR...", fonts['big'], (200, 200, 200), play_btn_rect.centery)
            else:
                can_play = client_state.get('is_local', False) or gs.get('opponent_joined', False)
                play_hover = play_btn_rect.collidepoint(mouse) and can_play
                if can_play:
                    draw_fancy_btn(screen, "Play", title_font, (35, 130, 65), (50, 160, 85), (255, 255, 255), play_btn_rect, is_hover=play_hover, custom_radius=8)
                else:
                    draw_fancy_btn(screen, "Play", title_font, (45, 45, 48), (45, 45, 48), (120, 120, 125), play_btn_rect, is_disabled=True, custom_radius=8)

            # Voltar botão
            back_btn_y = play_btn_y + 80
            back_btn_rect = pygame.Rect((WIN_W - 160) // 2, back_btn_y, 160, 44)
            draw_fancy_btn(screen, "Voltar", fonts['small'], (70, 70, 75), (90, 90, 95), (255, 255, 255), back_btn_rect, is_hover=back_btn_rect.collidepoint(mouse), custom_radius=6)

        elif app_state == "REPLAY_LIST":
            draw_text_center(screen, "REPLAYS SALVOS", title_font, T_MAIN, menu_y_start - 70)
            
            if 'replay_list' not in client_state:
                client_state['replay_list'] = load_replay_files()
                client_state['replay_page'] = 0

            replays = client_state['replay_list']
            page = client_state.get('replay_page', 0)
            items_per_page = 5
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(replays))
            
            visible_replays = replays[start_idx:end_idx]
            
            current_y = menu_y_start - 20
            client_state['replay_rects'] = {}
            
            if not replays:
                draw_text_center(screen, "Nenhum replay salvo encontrado.", fonts['big'], T_DIM, WIN_H // 2 - 20)
            else:
                for idx, rep in enumerate(visible_replays):
                    rep_rect = pygame.Rect(WIN_W // 2 - 250, current_y, 500, 50)
                    is_hover = rep_rect.collidepoint(mouse)
                    
                    name_text = f"{rep['date']} - {rep['turns']} lances ({rep['color']})"
                    room = rep['data'].get('room_code', 'LOCAL')
                    if room != 'LOCAL':
                        name_text += f" [Sala: {room}]"
                    
                    b_col = (80, 120, 220) if is_hover else None
                    draw_fancy_btn(screen, name_text, fonts['big'], BTN_N, BTN_H, BTN_TXT, rep_rect, is_hover=is_hover, border_color=b_col, custom_radius=6)
                    
                    global_idx = start_idx + idx
                    client_state['replay_rects'][global_idx] = rep_rect
                    current_y += 65
            
            client_state['replay_prev_page'] = None
            client_state['replay_next_page'] = None
            
            if len(replays) > items_per_page:
                btn_py = current_y + 10
                if page > 0:
                    prev_rect = pygame.Rect(WIN_W // 2 - 250, btn_py, 120, 36)
                    is_h = prev_rect.collidepoint(mouse)
                    draw_fancy_btn(screen, "Anterior", fonts['small'], BTN_N, BTN_H, BTN_TXT, prev_rect, is_hover=is_h, custom_radius=6)
                    client_state['replay_prev_page'] = prev_rect
                
                if end_idx < len(replays):
                    next_rect = pygame.Rect(WIN_W // 2 + 130, btn_py, 120, 36)
                    is_h = next_rect.collidepoint(mouse)
                    draw_fancy_btn(screen, "Próximo", fonts['small'], BTN_N, BTN_H, BTN_TXT, next_rect, is_hover=is_h, custom_radius=6)
                    client_state['replay_next_page'] = next_rect
                    
                page_text = f"Pág {page + 1} de {((len(replays) - 1) // items_per_page) + 1}"
                draw_text_center(screen, page_text, fonts['small'], T_DIM, btn_py + 18)
            
            btn_voltar_replay = pygame.Rect(WIN_W // 2 - 100, WIN_H - 100, 200, 44)
            is_hover_voltar = btn_voltar_replay.collidepoint(mouse)
            b_col_voltar = (100, 100, 105) if is_hover_voltar else None
            draw_fancy_btn(screen, "Voltar", fonts['big'], BTN_N, BTN_H, BTN_TXT, btn_voltar_replay, is_hover=is_hover_voltar, border_color=b_col_voltar, custom_radius=6)
            client_state['replay_btn_back'] = btn_voltar_replay

        elif app_state == "REPLAY_VIEW":
            turn_hist = client_state.get('turn_history', [])
            active_idx = client_state.get('history_index', 0)
            if turn_hist:
                h_gs = turn_hist[active_idx]
            else:
                h_gs = gs
            
            draw_board(screen, h_gs, fonts, client_state, mouse)
            client_state['panel_btns'] = draw_panel(screen, h_gs, fonts, mouse, client_state)
            draw_sidebar(screen, h_gs, fonts, client_state, mouse)

        elif app_state == "PLAYING":
            registrar_proximo_lance_auto(gs, client_state)
            
            if 'hide_selector_time' in client_state:
                if pygame.time.get_ticks() >= client_state['hide_selector_time']:
                    client_state['selected_block'] = None
                    del client_state['hide_selector_time']
            
            if client_state.get('is_dragging_nave'):
                now = pygame.time.get_ticks()
                offset = client_state.get('nave_offset', 0)
                max_offset = client_state.get('nave_max_offset', 60)
                if abs(offset) >= max_offset - 2:
                    delay = 250
                    if now - client_state.get('last_nave_move_time', 0) > delay:
                        draft_blocks = client_state.get('draft_blocks', [])
                        if draft_blocks:
                            current_sel = client_state.get('selected_block')
                            current_idx = -1
                            for i, (br, bid) in enumerate(draft_blocks):
                                if bid == current_sel:
                                    current_idx = i
                                    break
                            
                            moved = False
                            if offset < 0:
                                if current_idx == -1:
                                    client_state['selected_block'] = draft_blocks[-1][1]
                                    moved = True
                                elif current_idx > 0:
                                    client_state['selected_block'] = draft_blocks[current_idx - 1][1]
                                    moved = True
                                else:
                                    client_state['nave_error_time'] = pygame.time.get_ticks()
                            elif offset > 0:
                                if current_idx != -1:
                                    if current_idx < len(draft_blocks) - 1:
                                        client_state['selected_block'] = draft_blocks[current_idx + 1][1]
                                        moved = True
                                    else:
                                        client_state['nave_error_time'] = pygame.time.get_ticks()
                            
                            if moved:
                                play_sound('toggle')
                                client_state['scroll_to_selected'] = True
                                client_state['last_nave_move_time'] = now
                                client_state['nave_moved_during_drag'] = True

            turn_hist = client_state.get('turn_history', [])
            active_idx = client_state.get('history_index', 0)
            history_active = len(turn_hist) > 0 and active_idx < len(turn_hist) - 1
            client_state['history_active'] = history_active

            if history_active:
                h_gs = turn_hist[active_idx]
            else:
                h_gs = gs

            if client_state.get('is_local', False):
                display_gs = get_cached_serialized_state(client_state, h_gs, h_gs['turn'])
                if not history_active:
                    client_state['my_color'] = gs['turn']
                draw_board(screen, display_gs, fonts, client_state, mouse)
                client_state['panel_btns'] = draw_panel(screen, display_gs, fonts, mouse, client_state)
                draw_sidebar(screen, display_gs, fonts, client_state, mouse)
            else:
                draw_board(screen, h_gs, fonts, client_state, mouse)
                client_state['panel_btns'] = draw_panel(screen, h_gs, fonts, mouse, client_state)
                draw_sidebar(screen, h_gs, fonts, client_state, mouse)

            # Log modal rendering removed

        pygame.display.flip()
        await asyncio.sleep(1 / FPS)

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    asyncio.run(game_loop())
