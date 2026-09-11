import pygame, sys, os, json, math, random, time, threading
import requests
import websocket

# ========== 禁用代理 ==========
os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

# ========== 常量 ==========
WIDTH, HEIGHT, FPS = 1280, 720, 60
RES_W, RES_H = 800, 450
MOUSE_SENS, TURN_SPEED = 0.0026, 2.4

# ========== 服务器地址 ==========
SERVER_URL = "http://uk.frp.one:57335"
WS_URL = "ws://uk.frp.one:57335"
WS_ROOM = "global"

# ========== 触屏控制 ==========
TOUCH_MODE = True

TOUCH_JOYSTICK = {
    "active": False, "touch_id": None,
    "base_x": 200, "base_y": HEIGHT - 200,
    "knob_x": 200, "knob_y": HEIGHT - 200,
    "dx": 0.0, "dy": 0.0,
    "max_dist": 80, "look_id": None, "look_x": 0
}

TOUCH_BUTTONS = {
    "shoot":   {"rect": pygame.Rect(WIDTH - 180, HEIGHT - 180, 110, 110), "label": "射击", "color": (220, 60, 60),  "pressed": False},
    "reload":  {"rect": pygame.Rect(WIDTH - 320, HEIGHT - 130, 75, 75),   "label": "换弹", "color": (60, 120, 220), "pressed": False},
    "heal":    {"rect": pygame.Rect(WIDTH - 320, HEIGHT - 220, 75, 75),   "label": "治疗", "color": (60, 200, 100), "pressed": False},
    "flash":   {"rect": pygame.Rect(WIDTH - 410, HEIGHT - 180, 75, 75),   "label": "手电", "color": (220, 200, 80), "pressed": False},
    "use":     {"rect": pygame.Rect(WIDTH - 410, HEIGHT - 90,  75, 75),   "label": "互动", "color": (180, 100, 220), "pressed": False},
    "sprint":  {"rect": pygame.Rect(50,  HEIGHT - 380, 75, 75),           "label": "疾跑", "color": (255, 150, 60), "pressed": False},
    "chat":    {"rect": pygame.Rect(50,  HEIGHT - 280, 75, 75),           "label": "聊天", "color": (100, 180, 255), "pressed": False},
}

CHAT_PRESETS = ["集合", "小心", "救救我", "干得好", "需要弹药", "撤退"]

# ========== 玩家存档 ==========
SAVE = {"money": 0, "armor": 0, "dmg": 0, "ammo": 0, "tasks": {"kill": 0, "collect": 0, "extract": 0}}

# ========== Pygame变量 ==========
VIEW = {"a": 0.0}
FLASH_ON = False
canvas = None
MENU_BG = None
SND = {}
FEED = {"hp": None, "cans": None, "ammo": None, "med": None, "ehp": None, "ecnt": None,
        "res": "play", "rl": False, "texts": [], "hit": 0.0, "dmg": 0.0, "muzzle": 0.0, "bob": 0.0}

# ========== 登录状态 ==========
LOGIN_USER = None
LOGIN_PASS = ""
login_user_text = ""
login_pass_text = ""
login_focus = "user"
login_msg = ""
ALERT_MSG = ""
ALERT_TIME = 0.0
HELP_OPEN = False
MERCHANT_OPEN = False

# ========== 游戏状态 ==========
SYNC_RUNNING = False
REMOTE_PLAYERS = {}
LAST_SYNC_TIME = 0
SYNC_INTERVAL = 1.5
MULTIPLAYER_MODE = False
MULTIPLAYER_GAME = None
CURRENT_ROOM_ID = None
REQUEST_WORKER_RUNNING = False

# ========== 房间列表状态 ==========
SHOW_ROOM_LIST = False
SHOW_CREATE_ROOM = False
CREATE_ROOM_NAME = ""
CREATE_ROOM_PASSWORD = ""
CREATE_ROOM_MAP = 0
CREATE_ROOM_NIGHT = False
ROOM_LIST_PAGE = 0
ROOM_LIST_MAX_PER_PAGE = 5
CREATE_FOCUS = "name"

# ========== 缓存 ==========
CACHED_ROOM_STATUS = {"success": True, "status": "waiting", "host": None, "players": [], "player_count": 0, "max_players": 10}
CACHED_ROOM_STATUS_LOCK = threading.Lock()
CACHED_REMOTE_PLAYERS = {}
CACHED_REMOTE_PLAYERS_LOCK = threading.Lock()
CACHED_ROOM_LIST = {}
CACHED_ROOM_LIST_LOCK = threading.Lock()

MERCHANT_ITEMS = [
    {"name": "急救包", "price": 1, "key": "can", "val": 1},
    {"name": "弹药箱", "price": 2, "key": "can", "val": 30},
    {"name": "万能钥匙", "price": 1, "key": "gold", "val": 1}
]

# ========== 聊天室 ==========
CHAT_ENABLED = True
CHAT_MESSAGES = []
CHAT_MAX_MESSAGES = 50
CHAT_INPUT = ""
CHAT_FOCUS = False
CHAT_HAS_NEW_MESSAGE = False
CHAT_DISPLAYED_MESSAGES = set()

CHAT_MENU_RECTS = {"panel": None, "input": None, "send": None, "presets": []}
CHAT_GAME_RECTS = {"panel": None, "input": None, "send": None, "presets": []}

# ========== WebSocket 状态 ==========
WS_APP = None
WS_CONNECTED = False
WS_LOCK = threading.Lock()
WS_RECONNECT_RUNNING = False

# ========== HTTP 工具 ==========
def http_post(path, payload, timeout=6):
    try:
        r = requests.post(SERVER_URL + path, json=payload, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def http_get(path, timeout=6):
    try:
        r = requests.get(SERVER_URL + path, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

# ========== 账号系统 ==========
def http_register(user, password):
    if not user or len(user) < 2:
        return {"success": False, "message": "用户名至少2个字符"}
    if not password or len(password) < 6:
        return {"success": False, "message": "密码至少6位"}
    res = http_post("/api/register", {"user": user, "password": password})
    if res is None:
        return {"success": False, "message": "服务器连接失败"}
    return res

def http_login(user, password):
    if not user or not password:
        return {"success": False, "message": "请输入用户名和密码"}
    res = http_post("/api/login", {"user": user, "password": password})
    if res is None:
        return {"success": False, "message": "服务器连接失败"}
    if res.get("success"):
        global SAVE
        SAVE["money"] = res.get("money", 0)
        SAVE["armor"] = res.get("armor", 0)
        SAVE["dmg"] = res.get("dmg", 0)
        SAVE["ammo"] = res.get("ammo", 0)
        SAVE["tasks"] = res.get("tasks", {"kill": 0, "collect": 0, "extract": 0})
    return res

def push_save():
    global LOGIN_USER
    if not LOGIN_USER:
        return False
    payload = {
        "user": LOGIN_USER,
        "money": SAVE.get("money", 0),
        "armor": SAVE.get("armor", 0),
        "dmg": SAVE.get("dmg", 0),
        "ammo": SAVE.get("ammo", 0),
        "tasks": SAVE.get("tasks", {"kill": 0, "collect": 0, "extract": 0})
    }
    res = http_post("/api/save", payload)
    return bool(res and res.get("success"))

def push_save_async():
    threading.Thread(target=push_save, daemon=True).start()

# ========== 聊天（WebSocket） ==========
class ChatMessage:
    def __init__(self, user, text, timestamp=None, system=False, msg_id=None):
        self.user = user
        self.text = text
        self.timestamp = timestamp or time.time()
        self.system = system
        self.msg_id = msg_id or ""

def chat_add_message(user, text, system=False, timestamp=None, msg_id=None):
    global CHAT_HAS_NEW_MESSAGE, CHAT_DISPLAYED_MESSAGES, CHAT_MESSAGES
    timestamp = timestamp or time.time()
    if msg_id is None:
        msg_id = ""
    if msg_id and msg_id in CHAT_DISPLAYED_MESSAGES:
        return
    msg = ChatMessage(user, text, timestamp, system, msg_id)
    CHAT_MESSAGES.append(msg)
    if msg_id:
        CHAT_DISPLAYED_MESSAGES.add(msg_id)
    if len(CHAT_MESSAGES) > CHAT_MAX_MESSAGES:
        old = CHAT_MESSAGES.pop(0)
        if old.msg_id:
            CHAT_DISPLAYED_MESSAGES.discard(old.msg_id)
    CHAT_HAS_NEW_MESSAGE = True

def chat_add_system_message(text):
    chat_add_message("系统", text, system=True)

def chat_send_message(text):
    global CHAT_INPUT
    if not text or not text.strip() or not LOGIN_USER:
        return
    chat_add_message(LOGIN_USER, text)
    send_ws_text(text)
    CHAT_INPUT = ""

def _ws_on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        return
    msg_id = data.get("msg_id", "")
    user = data.get("user", "未知")
    text = data.get("text", "")
    if not text:
        return
    if msg_id and msg_id in CHAT_DISPLAYED_MESSAGES:
        return
    if data.get("type") == "system":
        chat_add_message(user, text, system=True, msg_id=msg_id, timestamp=data.get("time"))
    else:
        if user == LOGIN_USER:
            if msg_id:
                CHAT_DISPLAYED_MESSAGES.add(msg_id)
            return
        chat_add_message(user, text, msg_id=msg_id, timestamp=data.get("time"))

def _ws_on_error(ws, error):
    global WS_CONNECTED
    WS_CONNECTED = False

def _ws_on_close(ws, code, msg):
    global WS_CONNECTED
    WS_CONNECTED = False

def _ws_on_open(ws):
    global WS_CONNECTED
    WS_CONNECTED = True

def start_websocket():
    global WS_APP
    if not LOGIN_USER:
        return
    if WS_APP is not None and WS_CONNECTED:
        return
    url = f"{WS_URL}/ws/{WS_ROOM}/{LOGIN_USER}"
    WS_APP = websocket.WebSocketApp(
        url,
        on_message=_ws_on_message,
        on_error=_ws_on_error,
        on_close=_ws_on_close,
        on_open=_ws_on_open,
    )
    threading.Thread(target=WS_APP.run_forever, daemon=True).start()

def stop_websocket():
    global WS_APP, WS_CONNECTED
    if WS_APP:
        try:
            WS_APP.close()
        except Exception:
            pass
    WS_APP = None
    WS_CONNECTED = False

def send_ws_text(text):
    def do_send():
        with WS_LOCK:
            if WS_APP and WS_CONNECTED:
                try:
                    WS_APP.send(json.dumps({"text": text}))
                except Exception:
                    pass
    threading.Thread(target=do_send, daemon=True).start()

def _ws_reconnect_worker():
    while WS_RECONNECT_RUNNING:
        try:
            time.sleep(5)
            if LOGIN_USER and not WS_CONNECTED:
                start_websocket()
        except Exception:
            pass

def start_ws_reconnect():
    global WS_RECONNECT_RUNNING
    if not WS_RECONNECT_RUNNING:
        WS_RECONNECT_RUNNING = True
        threading.Thread(target=_ws_reconnect_worker, daemon=True).start()

def stop_ws_reconnect():
    global WS_RECONNECT_RUNNING
    WS_RECONNECT_RUNNING = False

def toggle_chat_focus():
    global CHAT_FOCUS, CHAT_HAS_NEW_MESSAGE
    CHAT_FOCUS = not CHAT_FOCUS
    if CHAT_FOCUS:
        try:
            pygame.key.start_text_input()
        except Exception:
            pass
        CHAT_HAS_NEW_MESSAGE = False
    else:
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

def chat_handle_keydown(event):
    global CHAT_INPUT
    if not CHAT_FOCUS:
        return
    if event.key == pygame.K_ESCAPE:
        toggle_chat_focus()
        return
    if event.key == pygame.K_RETURN:
        if CHAT_INPUT.strip():
            chat_send_message(CHAT_INPUT)
        toggle_chat_focus()
        return
    if event.key == pygame.K_BACKSPACE:
        if CHAT_INPUT:
            CHAT_INPUT = CHAT_INPUT[:-1]

def chat_handle_textinput(text):
    global CHAT_INPUT
    if CHAT_FOCUS and text:
        CHAT_INPUT += text

# ========== 房间管理（HTTP） ==========
def _refresh_room_list_cache():
    global CACHED_ROOM_LIST
    res = http_get("/api/rooms")
    if res and res.get("success"):
        with CACHED_ROOM_LIST_LOCK:
            CACHED_ROOM_LIST = res.get("rooms", {})

def get_available_rooms():
    _refresh_room_list_cache()
    with CACHED_ROOM_LIST_LOCK:
        return CACHED_ROOM_LIST.copy()

def create_room(room_name, password, host, map_idx=0, is_night=False, max_players=10):
    sv = SAVE
    maxhp = 100 + sv.get("armor", 0) * 50
    payload = {
        "name": room_name, "password": password, "host": host,
        "map_idx": map_idx, "is_night": is_night, "max_players": max_players,
        "host_hp": maxhp,
        "host_res": 120 + sv.get("ammo", 0) * 60,
        "host_dmg": 25 + sv.get("dmg", 0) * 10
    }
    res = http_post("/api/room/create", payload)
    if res is None:
        return {"success": False, "message": "服务器连接失败"}
    return res

def join_room(room_id, user, password=""):
    sv = SAVE
    maxhp = 100 + sv.get("armor", 0) * 50
    payload = {
        "room_id": room_id, "user": user, "password": password,
        "hp": maxhp,
        "res": 120 + sv.get("ammo", 0) * 60,
        "dmg": 25 + sv.get("dmg", 0) * 10
    }
    res = http_post("/api/room/join", payload)
    if res is None:
        return {"success": False, "message": "服务器连接失败"}
    return res

def leave_room(room_id, user):
    res = http_post("/api/room/leave", {"room_id": room_id, "user": user})
    return res or {"success": False}

def leave_room_async(room_id, user):
    threading.Thread(target=leave_room, args=(room_id, user), daemon=True).start()

def update_room_player(room_id, user, x, y, angle, hp):
    http_post("/api/room/update", {
        "room_id": room_id, "user": user,
        "x": x, "y": y, "angle": angle, "hp": hp
    })

def update_room_player_async(room_id, user, x, y, angle, hp):
    threading.Thread(target=update_room_player, args=(room_id, user, x, y, angle, hp), daemon=True).start()

def get_room_info(room_id):
    res = http_get(f"/api/room/{room_id}")
    if res and res.get("success"):
        return res.get("room")
    return None

def get_cached_room_status():
    with CACHED_ROOM_STATUS_LOCK:
        return CACHED_ROOM_STATUS.copy()

def get_cached_remote_players():
    with CACHED_REMOTE_PLAYERS_LOCK:
        return CACHED_REMOTE_PLAYERS.copy()

def join_room_success(room_id, room):
    global MULTIPLAYER_MODE, MULTIPLAYER_GAME, REMOTE_PLAYERS, mode
    global CURRENT_ROOM_ID, SHOW_ROOM_LIST, SHOW_CREATE_ROOM
    if not LOGIN_USER:
        return
    CURRENT_ROOM_ID = room_id
    players = room.get("players", [])
    player_names = [p.get("name") for p in players]
    MULTIPLAYER_MODE = True
    with CACHED_REMOTE_PLAYERS_LOCK:
        CACHED_REMOTE_PLAYERS.clear()
    map_idx = room.get("map_idx", 0)
    is_night = room.get("is_night", False)
    apply_config(map_idx, is_night)
    MULTIPLAYER_GAME = new_game(player_names, map_idx)
    for p in players:
        if p.get("name") in MULTIPLAYER_GAME["players"]:
            MULTIPLAYER_GAME["players"][p.get("name")]["x"] = p.get("x", 0)
            MULTIPLAYER_GAME["players"][p.get("name")]["y"] = p.get("y", 0)
            MULTIPLAYER_GAME["players"][p.get("name")]["hp"] = p.get("hp", 100)
    VIEW["a"] = 0.0
    reset_feed()
    SHOW_ROOM_LIST = False
    SHOW_CREATE_ROOM = False
    mode = "multiplayer"

def request_worker():
    global CACHED_ROOM_STATUS, CACHED_REMOTE_PLAYERS
    while REQUEST_WORKER_RUNNING:
        try:
            if LOGIN_USER and SYNC_RUNNING and CURRENT_ROOM_ID:
                room = get_room_info(CURRENT_ROOM_ID)
                if room:
                    players = room.get("players", [])
                    data = {"success": True, "status": room.get("status", "waiting"),
                            "host": room.get("host"), "players": players,
                            "player_count": len(players), "max_players": room.get("max_players", 10)}
                    with CACHED_ROOM_STATUS_LOCK:
                        CACHED_ROOM_STATUS = data
                    remote = {}
                    for p in players:
                        if p.get("name") != LOGIN_USER:
                            remote[p.get("name")] = {'x': p.get('x', 0), 'y': p.get('y', 0),
                                                     'angle': p.get('angle', 0), 'hp': p.get('hp', 100)}
                    with CACHED_REMOTE_PLAYERS_LOCK:
                        CACHED_REMOTE_PLAYERS.clear()
                        CACHED_REMOTE_PLAYERS.update(remote)
            time.sleep(0.8)
        except Exception:
            time.sleep(1)

def start_php_sync():
    global SYNC_RUNNING, REQUEST_WORKER_RUNNING
    if SYNC_RUNNING:
        return
    SYNC_RUNNING = True
    REQUEST_WORKER_RUNNING = True
    threading.Thread(target=request_worker, daemon=True).start()

def stop_php_sync():
    global SYNC_RUNNING, REQUEST_WORKER_RUNNING
    SYNC_RUNNING = False
    REQUEST_WORKER_RUNNING = False

# ========== 登录/登出 ==========
def do_register():
    global login_msg, login_user_text, login_pass_text
    user = login_user_text.strip()
    password = login_pass_text.strip()
    if not user:
        login_msg = "请输入用户名"
        return
    if not password or len(password) < 6:
        login_msg = "密码至少6位"
        return
    result = http_register(user, password)
    if result and result.get('success'):
        login_msg = "注册成功，请登录"
        login_user_text = ""
        login_pass_text = ""
    else:
        login_msg = result.get('message', "注册失败") if result else "网络错误"

def do_login():
    global LOGIN_USER, LOGIN_PASS, login_msg, login_user_text, login_pass_text
    user = login_user_text.strip()
    password = login_pass_text.strip()
    if not user or not password:
        login_msg = "请输入用户名和密码"
        return
    if LOGIN_USER:
        do_logout()
    result = http_login(user, password)
    if result and result.get('success'):
        LOGIN_USER = user
        LOGIN_PASS = password
        login_msg = "登录成功"
        login_user_text = ""
        login_pass_text = ""
        CHAT_DISPLAYED_MESSAGES.clear()
        CHAT_MESSAGES.clear()
        start_php_sync()
        start_websocket()
        start_ws_reconnect()
    else:
        login_msg = result.get('message', "登录失败") if result else "网络错误"

def do_logout():
    global LOGIN_USER, LOGIN_PASS, login_msg, MULTIPLAYER_MODE, MULTIPLAYER_GAME, CURRENT_ROOM_ID, mode, CHAT_FOCUS
    if LOGIN_USER:
        if MULTIPLAYER_MODE and CURRENT_ROOM_ID:
            leave_room_async(CURRENT_ROOM_ID, LOGIN_USER)
        push_save_async()
        stop_php_sync()
        stop_websocket()
        stop_ws_reconnect()
    LOGIN_USER = None
    LOGIN_PASS = ""
    login_msg = "已退出登录"
    MULTIPLAYER_MODE = False
    MULTIPLAYER_GAME = None
    CHAT_MESSAGES.clear()
    CHAT_DISPLAYED_MESSAGES.clear()
    CURRENT_ROOM_ID = None
    CHAT_FOCUS = False
    with CACHED_ROOM_STATUS_LOCK:
        CACHED_ROOM_STATUS = {"success": True, "status": "waiting", "host": None, "players": [], "player_count": 0, "max_players": 10}
    with CACHED_REMOTE_PLAYERS_LOCK:
        CACHED_REMOTE_PLAYERS.clear()
    mode = "menu"

# ========== 字体 ==========
_FONT_CACHE = {}

def get_chinese_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font_paths = [
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/DroidSansFallback.ttf",
        "/system/fonts/DroidSansChinese.ttf",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, size)
                _FONT_CACHE[size] = font
                return font
            except Exception:
                continue
    try:
        font = pygame.font.SysFont("sans", size)
        _FONT_CACHE[size] = font
        return font
    except Exception:
        font = pygame.font.Font(None, size)
        _FONT_CACHE[size] = font
        return font

def draw_text(surface, text, size, color, center=None, topleft=None, midtop=None):
    if not text:
        return
    text = str(text)
    font = get_chinese_font(size)
    try:
        txt_surf = font.render(text, True, color)
    except Exception:
        return
    rect = txt_surf.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif midtop:
        rect.midtop = midtop
    surface.blit(txt_surf, rect)

# ========== 游戏辅助 ==========
def shade(color):
    return tuple(int(c * 0.6) for c in color)

def reset_feed():
    global FEED
    FEED.update({"hp": None, "cans": None, "ammo": None, "med": None, "ehp": None, "ecnt": None,
                 "res": "play", "rl": False, "texts": [], "hit": 0.0, "dmg": 0.0, "muzzle": 0.0, "bob": 0.0})

def add_text(txt):
    FEED["texts"].append([txt, 2.0])

def play(sound_key):
    if sound_key in SND:
        try:
            SND[sound_key].play()
        except Exception:
            pass

def make_ui_assets():
    global MENU_BG
    MENU_BG = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        c = tuple(int(15 + 20 * t) for _ in range(3))
        pygame.draw.line(MENU_BG, c, (0, y), (WIDTH, y))

def make_sounds():
    global SND
    try:
        pygame.mixer.init()
        SND["shoot"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x80' * 100 + b'\x00' * 100 + b'\x80' * 100) * 2))
        SND["hit"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x80' * 50 + b'\x00' * 50) * 3))
        SND["die"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x80' * 200 + b'\x00' * 100) * 2))
        SND["hurt"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x00' * 50 + b'\x80' * 100) * 2))
        SND["pick"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x80' * 30 + b'\x00' * 30) * 5))
        SND["reload"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x80' * 80 + b'\x00' * 80) * 3))
        SND["win"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x80' * 150 + b'\x00' * 50) * 4))
        SND["lose"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x00' * 50 + b'\x80' * 150) * 3))
        SND["buy"] = pygame.mixer.Sound(pygame.sndarray.make_sound((b'\x80' * 40 + b'\x00' * 40) * 4))
    except Exception:
        pass

def draw_panel(surface, rect, alpha=200, border=None, radius=8):
    s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    if isinstance(alpha, int):
        s.fill((10, 15, 20, alpha))
    else:
        s.fill(alpha)
    pygame.draw.rect(s, s.get_at((0, 0)), s.get_rect(), border_radius=radius)
    surface.blit(s, rect.topleft)
    if border:
        pygame.draw.rect(surface, border, rect, 2, border_radius=radius)

def draw_bar(surface, rect, ratio, color):
    pygame.draw.rect(surface, (30, 35, 40), rect, border_radius=4)
    if ratio > 0:
        w = max(2, int(rect.w * ratio))
        pygame.draw.rect(surface, color, (rect.x, rect.y, w, rect.h), border_radius=4)

def draw_overlay(surface, alpha):
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ov.fill((0, 0, 0, alpha))
    surface.blit(ov, (0, 0))

# ========== MAPS ==========
MAPS = [
    {"name": "废弃小镇", "w": 2560, "h": 1440,
     "walls": [(0,0,2560,20),(0,1420,2560,20),(0,0,20,1440),(2540,0,20,1440),
               (400,300,440,40),(1000,240,40,560),(1500,440,600,40),(700,1040,720,40),
               (1960,960,40,440),(360,680,240,240),(1720,120,240,200),(1200,700,200,200),
               (2260,500,40,400),(500,1200,40,200),(1600,1200,300,40),(2100,1100,200,40)],
     "doors": [(1500,350,240,40)],
     "extract": (2100, 80, 380, 380),
     "spawns": [(200,1200),(320,1200),(440,1200),(200,1080),(320,1080),(440,1080),(200,960),(320,960)],
     "enemies": [(860,860),(1400,520),(2240,440),(1240,300),(1700,900),(900,1300),(2300,1200),(600,500)],
     "loots": [(600,480,"can"),(1240,360,"can"),(1840,520,"can"),(1000,1200,"can"),(2300,800,"can"),
               (1500,760,"ammo"),(2160,360,"ammo"),(800,600,"ammo"),(520,1120,"medkit"),(1760,1320,"medkit"),
               (1400,1000,"medkit"),(1450,300,"key"),(1600,250,"can"),(1560,250,"medkit"),(1640,250,"gold")]},
    {"name": "罐头港口", "w": 2000, "h": 2000,
     "walls": [(0,0,2000,20),(0,1980,2000,20),(0,0,20,2000),(1980,0,20,2000),
               (400,400,600,40),(400,400,40,200),(1200,800,40,400),(1200,800,300,40),
               (300,1200,200,40),(1500,1400,300,40),(800,1600,40,300),(1800,600,40,200)],
     "doors": [(800, 400, 40, 60)],
     "extract": (1700, 1700, 200, 200),
     "spawns": [(300,300),(300,500),(500,300),(500,500)],
     "enemies": [(1000,1000),(1200,1200),(800,600),(600,800),(1400,1400),(1600,1600),(400,1800),(1800,400)],
     "loots": [(800,800,"can"),(1000,1000,"can"),(1200,1200,"can"),(1400,1400,"ammo"),(1600,1600,"medkit"),
               (600,600,"key"),(800,1000,"gold"),(1000,800,"can"),(1200,1400,"ammo"),(1400,1200,"medkit")]}
]

THEMES = {
    "day": {"name": "白天", "sky_top": (30,100,200), "sky_bot": (200,220,255),
            "floor_top": (80,140,80), "floor_bot": (30,60,30),
            "wall_base0": (180,160,140), "wall_base1": (160,140,120),
            "fog_dist": 1200, "ambient": 0.9, "fog_color": (200,220,240)},
    "night": {"name": "黑夜", "sky_top": (10,10,30), "sky_bot": (40,30,60),
              "floor_top": (30,25,20), "floor_bot": (10,8,5),
              "wall_base0": (70,65,60), "wall_base1": (50,45,40),
              "fog_dist": 600, "ambient": 0.35, "fog_color": (20,20,30)}
}

PAL_ENEMY = {"H": (200,60,60), "U": (160,80,80), "G": (100,50,50), "L": (120,70,70), "D": (80,40,40)}
PAL_ELITE = {"H": (160,50,200), "U": (130,60,180), "G": (80,40,120), "L": (100,50,150), "D": (60,30,100)}
LOOT_COLORS = {"can": (255,180,50), "ammo": (200,200,80), "medkit": (80,220,80), "key": (200,200,255), "gold": (255,215,0)}

CURRENT_MAP_IDX = 0
IS_NIGHT = False
WALLS = []
WORLD_W = 0
WORLD_H = 0
EXTRACT_ZONE = pygame.Rect(0, 0, 0, 0)
DOORS = []
DOORS_OPEN = []
SKY = None
FLOOR = None

def apply_config(map_idx, is_night):
    global CURRENT_MAP_IDX, IS_NIGHT, WALLS, WORLD_W, WORLD_H, EXTRACT_ZONE, SKY, FLOOR, DOORS, DOORS_OPEN
    CURRENT_MAP_IDX = map_idx % len(MAPS)
    IS_NIGHT = is_night
    m = MAPS[CURRENT_MAP_IDX]
    WORLD_W, WORLD_H = m["w"], m["h"]
    WALLS = [pygame.Rect(*r) for r in m["walls"]]
    DOORS = [pygame.Rect(*d) for d in m.get("doors", [])]
    DOORS_OPEN = [False] * len(DOORS)
    EXTRACT_ZONE = pygame.Rect(*m["extract"])
    if pygame.get_init():
        theme = THEMES["night" if IS_NIGHT else "day"]
        SKY = pygame.Surface((RES_W, RES_H // 2))
        for y in range(RES_H // 2):
            t = y / (RES_H // 2)
            c = tuple(int(theme["sky_top"][i] + (theme["sky_bot"][i] - theme["sky_top"][i]) * t) for i in range(3))
            pygame.draw.line(SKY, c, (0, y), (RES_W, y))
        FLOOR = pygame.Surface((RES_W, RES_H // 2))
        for y in range(RES_H // 2):
            t = 1 - y / (RES_H // 2)
            c = tuple(int(theme["floor_top"][i] + (theme["floor_bot"][i] - theme["floor_top"][i]) * t) for i in range(3))
            pygame.draw.line(FLOOR, c, (0, y), (RES_W, y))

def draw_char(surface, screen_x, top, h, w, pal, zbuf, ty, f):
    bottom = top + h
    half = w // 2
    head_r = h * 0.18
    head_cy = top + h * 0.2
    tw = h * 0.15
    sh_y = top + h * 0.35
    hip_y = top + h * 0.65
    gun_y = top + h * 0.5
    leg_w = h * 0.07
    boot_h = h * 0.08
    for col in range(max(0, screen_x - half), min(RES_W - 1, screen_x + half) + 1):
        if ty >= zbuf[col]:
            continue
        u = col - screen_x
        if abs(u) < head_r:
            dy = math.sqrt(max(0.0, head_r * head_r - u * u))
            c = shade(pal["H"])
            pygame.draw.line(surface, c, (col, int(head_cy - dy)), (col, int(head_cy + dy)))
        if abs(u) < tw:
            c = shade(pal["U"])
            pygame.draw.line(surface, c, (col, int(sh_y)), (col, int(hip_y)))
        if -0.26 * h < u < 0.10 * h:
            c = shade(pal["G"])
            pygame.draw.line(surface, c, (col, int(gun_y)), (col, int(gun_y + 0.04 * h)))
        for lc in (-0.08 * h, 0.08 * h):
            if abs(u - lc) < leg_w:
                c = shade(pal["L"])
                pygame.draw.line(surface, c, (col, int(hip_y)), (col, int(bottom - boot_h)))
                c = shade(pal["D"])
                pygame.draw.line(surface, c, (col, int(bottom - boot_h)), (col, int(bottom)))

def point_collides(x, y, radius=16):
    r = pygame.Rect(int(x - radius), int(y - radius), int(radius * 2), int(radius * 2))
    if any(r.colliderect(w) for w in WALLS):
        return True
    for i, d in enumerate(DOORS):
        if not DOORS_OPEN[i] and r.colliderect(d):
            return True
    return False

def move_with_collision(x, y, dx, dy, speed, dt):
    if dx != 0:
        nx = x + dx * speed * dt
        if not point_collides(nx, y):
            x = nx
    if dy != 0:
        ny = y + dy * speed * dt
        if not point_collides(x, ny):
            y = ny
    return x, y

def angle_diff(a, b):
    d = a - b
    while d > math.pi:
        d -= math.pi * 2
    while d < -math.pi:
        d += math.pi * 2
    return d

def cast_ray(x, y, angle, max_dist=2000):
    dx, dy, px, py, traveled, step = math.cos(angle), math.sin(angle), x, y, 0, 4
    while traveled < max_dist:
        px += dx * step
        py += dy * step
        traveled += step
        if point_collides(px, py, 2):
            return traveled
    return max_dist

def ray_rect_t(x, y, dx, dy, r):
    tmin, tmax = 0.0, 1e9
    if abs(dx) < 1e-9:
        if x < r.x or x > r.x + r.w:
            return None
    else:
        t1, t2 = (r.x - x) / dx, (r.x + r.w - x) / dx
        if t1 > t2:
            t1, t2 = t2, t1
        tmin, tmax = max(tmin, t1), min(tmax, t2)
        if tmin > tmax:
            return None
    if abs(dy) < 1e-9:
        if y < r.y or y > r.y + r.h:
            return None
    else:
        t1, t2 = (r.y - y) / dy, (r.y + r.h - y) / dy
        if t1 > t2:
            t1, t2 = t2, t1
        tmin, tmax = max(tmin, t1), min(tmax, t2)
        if tmin > tmax:
            return None
    return tmin if tmin > 1e-4 else tmax

def raycast(x, y, dx, dy):
    best, side, isdoor = 1e4, 0, False
    for r in WALLS:
        t = ray_rect_t(x, y, dx, dy, r)
        if t is not None and t < best:
            best = t
            isdoor = False
            hx, hy = x + dx * t, y + dy * t
            side = 0 if (abs(hx - r.x) < 0.5 or abs(hx - (r.x + r.w)) < 0.5) else 1
    for i, r in enumerate(DOORS):
        if DOORS_OPEN[i]:
            continue
        t = ray_rect_t(x, y, dx, dy, r)
        if t is not None and t < best:
            best = t
            isdoor = True
            hx, hy = x + dx * t, y + dy * t
            side = 0 if (abs(hx - r.x) < 0.5 or abs(hx - (r.x + r.w)) < 0.5) else 1
    return best, side, isdoor

def render_view(surface, cx, cy, ca, state, my_id, bob=0):
    surface.blit(SKY, (0, 0))
    surface.blit(FLOOR, (0, RES_H // 2))
    dir_x, dir_y = math.cos(ca), math.sin(ca)
    plane_x, plane_y = -dir_y * 0.66, dir_x * 0.66
    zbuf = []
    theme = THEMES["night" if IS_NIGHT else "day"]
    fog_dist = theme["fog_dist"]
    ambient = theme["ambient"]
    if FLASH_ON:
        if IS_NIGHT:
            fog_dist = max(fog_dist, 1400)
            ambient = max(ambient, 0.8)
        else:
            fog_dist *= 1.2
            ambient = min(1.0, ambient * 1.1)
    for x in range(RES_W):
        cam_n = 2 * x / RES_W - 1
        rdx, rdy = dir_x + plane_x * cam_n, dir_y + plane_y * cam_n
        dist, side, isdoor = raycast(cx, cy, rdx, rdy)
        dist = max(0.05, dist)
        zbuf.append(dist)
        wall_h = int(RES_H * 40 / dist)
        top = max(0, RES_H // 2 - wall_h // 2)
        bottom = min(RES_H - 1, RES_H // 2 + wall_h // 2)
        base = (190, 150, 60) if isdoor else (theme["wall_base0"] if side == 0 else theme["wall_base1"])
        f = max(0.15, min(1.0, ambient * 1.8 / (dist / 40 + 1)))
        hx, hy = cx + rdx * dist, cy + rdy * dist
        tex = 0.88 + 0.12 * math.sin((hx + hy) * 0.12)
        r, g2, b = int(base[0] * f * tex), int(base[1] * f * tex), int(base[2] * f * tex)
        fog = min(1.0, dist / fog_dist)
        fog_c = theme["fog_color"]
        pygame.draw.line(surface, (int(r + (fog_c[0] - r) * fog), int(g2 + (fog_c[1] - g2) * fog), int(b + (fog_c[2] - b) * fog)), (x, top), (x, bottom))
    sprites = [(e["x"], e["y"], "e2" if e.get("elite") else "enemy") for e in state.get("enemies", [])]
    sprites += [(l["x"], l["y"], l["k"]) for l in state.get("loots", [])]
    if state.get("merchant"):
        sprites.append((state["merchant"]["x"], state["merchant"]["y"], "merchant"))
    sprites.append((EXTRACT_ZONE.centerx, EXTRACT_ZONE.centery, "extract"))
    sprites.sort(key=lambda s: (s[0] - cx) ** 2 + (s[1] - cy) ** 2, reverse=True)
    inv_det = 1.0 / (plane_x * dir_y - dir_x * plane_y)
    for sx, sy, kind in sprites:
        rel_x, rel_y = sx - cx, sy - cy
        tx = inv_det * (dir_y * rel_x - dir_x * rel_y)
        ty = inv_det * (-plane_y * rel_x + plane_x * rel_y)
        if ty <= 0.1:
            continue
        screen_x = int((RES_W / 2) * (1 + tx / ty))
        wall_h = int(RES_H * 40 / ty)
        bottom = RES_H // 2 + wall_h // 2
        if kind in ("enemy", "e2"):
            h = int(wall_h * 0.9)
            w = max(6, int(h * 0.5))
            top = bottom - h
            f = max(0.15, min(1.0, ambient * 1.8 / (ty / 40 + 1)))
            pal = PAL_ELITE if kind == "e2" else PAL_ENEMY
            draw_char(surface, screen_x, top, h, w, pal, zbuf, ty, f)
        elif kind == "merchant":
            h, w = int(wall_h * 0.8), max(8, int(wall_h * 0.4))
            top = bottom - h
            f = max(0.15, min(1.0, ambient * 1.8 / (ty / 40 + 1)))
            color = (int(255 * f), int(215 * f), int(0 * f))
            half = w // 2
            for col in range(max(0, screen_x - half), min(RES_W - 1, screen_x + half) + 1):
                if ty < zbuf[col]:
                    pygame.draw.line(surface, color, (col, max(0, top)), (col, min(RES_H - 1, bottom)))
        elif kind == "extract":
            h, w, color = int(wall_h * 0.95), max(3, int(wall_h * 0.475)), (80, 220, 130)
            top = bottom - h
            f = max(0.15, min(1.0, ambient * 1.8 / (ty / 40 + 1)))
            fog = min(1.0, ty / fog_dist)
            fog_c = theme["fog_color"]
            color = (int(color[0] * f), int(color[1] * f), int(color[2] * f))
            color = (int(color[0] + (fog_c[0] - color[0]) * fog), int(color[1] + (fog_c[1] - color[1]) * fog), int(color[2] + (fog_c[2] - color[2]) * fog))
            half = w // 2
            for col in range(max(0, screen_x - half), min(RES_W - 1, screen_x + half) + 1):
                if ty < zbuf[col]:
                    pygame.draw.line(surface, color, (col, max(0, top)), (col, min(RES_H - 1, bottom)))
        else:
            h, w, color = int(wall_h * 0.2), max(2, int(wall_h * 0.18)), LOOT_COLORS.get(kind, (255, 255, 255))
            top = bottom - h
            f = max(0.15, min(1.0, ambient * 1.8 / (ty / 40 + 1)))
            fog = min(1.0, ty / fog_dist)
            fog_c = theme["fog_color"]
            color = (int(color[0] * f), int(color[1] * f), int(color[2] * f))
            color = (int(color[0] + (fog_c[0] - color[0]) * fog), int(color[1] + (fog_c[1] - color[1]) * fog), int(color[2] + (fog_c[2] - color[2]) * fog))
            half = w // 2
            for col in range(max(0, screen_x - half), min(RES_W - 1, screen_x + half) + 1):
                if ty < zbuf[col]:
                    pygame.draw.line(surface, color, (col, max(0, top)), (col, min(RES_H - 1, bottom)))
    by = int(bob)
    gx = RES_W // 2
    pygame.draw.rect(surface, (48, 48, 54), (gx - 8, RES_H - 64 + by, 30, 12))
    pygame.draw.rect(surface, (35, 35, 40), (gx + 16, RES_H - 60 + by, 16, 7))
    pygame.draw.rect(surface, (60, 55, 50), (gx - 4, RES_H - 52 + by, 9, 16))
    pygame.draw.circle(surface, (232, 196, 150), (gx - 8, RES_H - 50 + by), 7)
    pygame.draw.circle(surface, (232, 196, 150), (gx + 6, RES_H - 56 + by), 6)

def new_player(x, y, sv=None):
    sv = sv or SAVE
    maxhp = 100 + sv.get("armor", 0) * 50
    tasks = dict(sv.get("tasks", {"kill": 0, "collect": 0, "extract": 0}))
    return {"x": x, "y": y, "a": 0.0, "hp": maxhp, "maxhp": maxhp, "mag": 30, "res": 120 + sv.get("ammo", 0) * 60,
            "cans": 0, "gold": 0, "key": 0, "med": 0, "dmg": 25 + sv.get("dmg", 0) * 10,
            "reload": 0.0, "shoot_cd": 0.0, "med_cd": 0.0,
            "tasks": tasks}

def new_enemy(x, y):
    el = random.random() < 0.25
    return {"x": x, "y": y, "hp": 120 if el else 60, "elite": 1 if el else 0, "sp": 170 if el else 130,
            "dmg": 14 if el else 8, "shoot": random.uniform(0.5, 1.5), "wander": random.uniform(0, math.tau), "wt": random.uniform(0.5, 2.0)}

def add_loot(game, x, y, kind):
    lid = game["next_loot"]
    game["next_loot"] += 1
    game["loots"][lid] = {"x": x, "y": y, "k": kind}

def new_game(pids, map_idx):
    g = {"players": {}, "enemies": [], "loots": {}, "next_loot": 1, "extract": 0.0, "result": "play",
         "end_timer": 0.0, "inputs": {}, "in_zone": False, "doors_open": [False] * len(MAPS[map_idx].get("doors", []))}
    m = MAPS[map_idx]
    for i, pid in enumerate(pids):
        player = new_player(*m["spawns"][i % len(m["spawns"])])
        player["is_host"] = True
        g["players"][pid] = player
    for x, y in m["enemies"]:
        g["enemies"].append(new_enemy(x, y))
    for x, y, k in m["loots"]:
        add_loot(g, x, y, k)
    g["merchant"] = {"x": random.randint(400, m["w"] - 400), "y": random.randint(400, m["h"] - 400)}
    return g

def reset_game(g):
    g.update(new_game(list(g["players"].keys()), CURRENT_MAP_IDX))

def nearest_alive_player(g, x, y):
    best, bd = None, float("inf")
    for pid, p in g["players"].items():
        if p["hp"] > 0:
            d = math.hypot(p["x"] - x, p["y"] - y)
            if d < bd:
                bd, best = d, (pid, p)
    return best

def enemy_wander(e, dt):
    e["wt"] -= dt
    if e["wt"] <= 0:
        e["wt"] = random.uniform(1.0, 3.0)
        e["wander"] = random.uniform(0, math.tau)
    ox, oy = e["x"], e["y"]
    e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(e["wander"]), math.sin(e["wander"]), e.get("sp", 130) * 0.45, dt)
    if math.hypot(e["x"] - ox, e["y"] - oy) < 0.1:
        e["wt"] = 0

def alert_enemies(g, pid, x, y, radius=1000, dur=6):
    for e in g["enemies"]:
        if math.hypot(e["x"] - x, e["y"] - y) < radius:
            e["ap"] = pid
            e["at"] = dur

def server_shoot(g, sid, s):
    ang = s["a"]
    wd = cast_ray(s["x"], s["y"], ang)
    bd, be, bp = wd, None, None
    for e in g["enemies"]:
        dx, dy = e["x"] - s["x"], e["y"] - s["y"]
        d = math.hypot(dx, dy)
        if d > 1 and d <= bd + 10 and abs(angle_diff(math.atan2(dy, dx), ang)) <= math.atan2(18.0, d):
            bd, be, bp = d, e, None
    for pid, p in g["players"].items():
        if pid == sid or p["hp"] <= 0:
            continue
        dx, dy = p["x"] - s["x"], p["y"] - s["y"]
        d = math.hypot(dx, dy)
        if d > 1 and d <= bd + 10 and abs(angle_diff(math.atan2(dy, dx), ang)) <= math.atan2(16.0, d):
            bd, be, bp = d, None, p
    if be:
        be["hp"] -= s.get("dmg", 25)
    elif bp:
        bp["hp"] -= s.get("dmg", 25)
        bp["hp"] = max(0, bp["hp"])

def server_update(g, dt):
    if not g["players"]:
        return
    if g["result"] != "play":
        g["end_timer"] += dt
        if g["end_timer"] > 8.0:
            reset_game(g)
        return
    g["end_timer"] = 0.0
    for pid, p in list(g["players"].items()):
        if p["hp"] <= 0:
            continue
        inp = g["inputs"].get(pid, {})
        p["a"] = inp.get("a", p["a"])
        dx, dy = float(inp.get("dx", 0)), float(inp.get("dy", 0))
        l = math.hypot(dx, dy)
        if l > 0:
            dx /= l
            dy /= l
        spd = 320 * (1.5 if inp.get("sprint") else 1.0)
        p["x"], p["y"] = move_with_collision(p["x"], p["y"], dx, dy, spd, dt)
        p["shoot_cd"], p["med_cd"] = max(0.0, p["shoot_cd"] - dt), max(0.0, p["med_cd"] - dt)
        if p["reload"] > 0:
            p["reload"] -= dt
            if p["reload"] <= 0:
                t = min(30 - p["mag"], p["res"])
                p["mag"] += t
                p["res"] -= t
        if inp.get("reload") and p["reload"] <= 0 and p["mag"] < 30 and p["res"] > 0:
            p["reload"] = 1.4
        if inp.get("med") and p["med_cd"] <= 0:
            if p["med"] > 0 and p["hp"] < p["maxhp"]:
                p["med"] -= 1
                p["hp"] = min(p["maxhp"], p["hp"] + 35)
            p["med_cd"] = 0.5
        if inp.get("use") and p.get("key"):
            for i, od in enumerate(g["doors_open"]):
                if not od and i < len(DOORS):
                    d = DOORS[i]
                    if math.hypot(d.centerx - p["x"], d.centery - p["y"]) < 90:
                        g["doors_open"][i] = True
                        if i < len(DOORS_OPEN):
                            DOORS_OPEN[i] = True
                        break
        if inp.get("shoot") and p["shoot_cd"] <= 0 and p["reload"] <= 0:
            if p["mag"] > 0:
                p["mag"] -= 1
                p["shoot_cd"] = 0.12
                server_shoot(g, pid, p)
                alert_enemies(g, pid, p["x"], p["y"])
                if "tasks" in p:
                    p["tasks"]["kill"] = p["tasks"].get("kill", 0) + 1
            elif p["res"] > 0:
                p["reload"] = 1.4
    for e in g["enemies"][:]:
        if e["hp"] <= 0:
            g["enemies"].remove(e)
            drop = "can" if e.get("elite") and random.random() < 0.6 else random.choice(["ammo", "medkit"])
            add_loot(g, e["x"], e["y"], drop)
            continue
        e["at"] = max(0, e.get("at", 0) - dt)
        tgt = None
        if e.get("at", 0) > 0 and e.get("ap") in g["players"] and g["players"][e["ap"]]["hp"] > 0:
            tgt = (e["ap"], g["players"][e["ap"]])
        else:
            tgt = nearest_alive_player(g, e["x"], e["y"])
        if tgt:
            pid, pl = tgt
            d = math.hypot(pl["x"] - e["x"], pl["y"] - e["y"])
            aggro = 950 if e.get("at", 0) > 0 else 500
            if d < aggro:
                if d > 50:
                    ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                    e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang), e.get("sp", 130), dt)
                e["shoot"] -= dt
                if e["shoot"] <= 0 and d < 430:
                    e["shoot"] = 0.8 + random.uniform(-0.1, 0.2)
                    ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                    if cast_ray(e["x"], e["y"], ang, d + 20) > d - 10:
                        pl["hp"] -= e.get("dmg", 8)
                        pl["hp"] = max(0, pl["hp"])
            else:
                enemy_wander(e, dt)
        else:
            enemy_wander(e, dt)
    for lid, l in list(g["loots"].items()):
        for pid, pp in g["players"].items():
            if pp["hp"] <= 0:
                continue
            if math.hypot(l["x"] - pp["x"], l["y"] - pp["y"]) < 30:
                if l["k"] == "can":
                    pp["cans"] += 1
                    pp["tasks"]["collect"] = pp["tasks"].get("collect", 0) + 1
                elif l["k"] == "ammo":
                    pp["res"] += 30
                elif l["k"] == "medkit":
                    pp["med"] += 1
                elif l["k"] == "key":
                    pp["key"] = 1
                elif l["k"] == "gold":
                    pp["gold"] += 1
                del g["loots"][lid]
                break
    g["in_zone"] = any(p["hp"] > 0 and EXTRACT_ZONE.collidepoint(int(p["x"]), int(p["y"])) for p in g["players"].values())
    any_ext = any(p["hp"] > 0 and p["cans"] >= 3 and EXTRACT_ZONE.collidepoint(int(p["x"]), int(p["y"])) for p in g["players"].values())
    if any_ext:
        g["extract"] += dt
        if g["extract"] >= 3.0:
            g["result"] = "win"
            for pid, p in g["players"].items():
                if p["hp"] > 0:
                    p["tasks"]["extract"] = p["tasks"].get("extract", 0) + 1
    else:
        g["extract"] = max(0.0, g["extract"] - dt * 2.0)
    if not any(p["hp"] > 0 for p in g["players"].values()):
        g["result"] = "lose"

def make_state(g):
    return {"t": "state", "players": [{"id": pid, **p} for pid, p in g["players"].items()],
            "enemies": [{"x": e["x"], "y": e["y"], "hp": e["hp"], "elite": e.get("elite", 0)} for e in g["enemies"]],
            "loots": [{"id": lid, **l} for lid, l in g["loots"].items()], "extract": g["extract"], "result": g["result"],
            "in_zone": g.get("in_zone", False), "doors_open": g.get("doors_open", DOORS_OPEN), "merchant": g.get("merchant")}

def read_input(px, py, dt):
    global VIEW
    if CHAT_FOCUS:
        return {"dx": 0, "dy": 0, "a": VIEW["a"], "shoot": 0, "sprint": 0,
                "use": 0, "reload": 0, "med": 0, "buy": 0}
    jx = TOUCH_JOYSTICK["dx"]
    jy = TOUCH_JOYSTICK["dy"]
    move_x = jx
    move_y = -jy
    a = VIEW["a"]
    dx = math.cos(a) * move_y + math.cos(a + math.pi / 2) * move_x
    dy = math.sin(a) * move_y + math.sin(a + math.pi / 2) * move_x
    l = math.hypot(dx, dy)
    if l > 0:
        dx /= l
        dy /= l
    shoot = 1 if TOUCH_BUTTONS["shoot"]["pressed"] else 0
    reload_ = 1 if TOUCH_BUTTONS["reload"]["pressed"] else 0
    med = 1 if TOUCH_BUTTONS["heal"]["pressed"] else 0
    use_ = 1 if TOUCH_BUTTONS["use"]["pressed"] else 0
    sprint = 1 if TOUCH_BUTTONS["sprint"]["pressed"] else 0
    if shoot:
        FEED["muzzle"] = 0.06
        play("shoot")
    if sprint or move_x or move_y:
        FEED["bob"] += dt * (11 if sprint else 7)
    return {"dx": dx, "dy": dy, "a": a, "shoot": shoot, "sprint": sprint,
            "use": use_, "reload": reload_, "med": med, "buy": 0}

def get_player_from_state(st, pid):
    if not st:
        return None
    for p in st.get("players", []):
        if p.get("id") == pid:
            return p
    return None

def draw_minimap(screen, st, my_id):
    s = min(190 / WORLD_W, 110 / WORLD_H)
    mw, mh = int(WORLD_W * s), int(WORLD_H * s)
    ox, oy = WIDTH - mw - 16, 16
    bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 140))
    screen.blit(bg, (ox, oy))
    for w in WALLS:
        pygame.draw.rect(screen, (120, 130, 140), (ox + w.x * s, oy + w.y * s, max(1, w.w * s), max(1, w.h * s)))
    for i, d in enumerate(DOORS):
        if not DOORS_OPEN[i]:
            pygame.draw.rect(screen, (255, 210, 90), (ox + d.x * s, oy + d.y * s, max(2, d.w * s), max(2, d.h * s)))
    pygame.draw.rect(screen, (80, 220, 130), (ox + EXTRACT_ZONE.x * s, oy + EXTRACT_ZONE.y * s, EXTRACT_ZONE.w * s, EXTRACT_ZONE.h * s))
    if st:
        if st.get("merchant"):
            m = st["merchant"]
            pygame.draw.circle(screen, (255, 215, 0), (ox + int(m["x"] * s), oy + int(m["y"] * s)), 4)
        for l in st.get("loots", []):
            pygame.draw.rect(screen, LOOT_COLORS.get(l["k"], (255, 200, 80)), (ox + l["x"] * s - 1, oy + l["y"] * s - 1, 3, 3))
        for e in st.get("enemies", []):
            pygame.draw.rect(screen, (200, 80, 220) if e.get("elite") else (235, 80, 80), (ox + e["x"] * s - 2, oy + e["y"] * s - 2, 4, 4))
        me = get_player_from_state(st, my_id)
        for p in st.get("players", []):
            px, py = ox + int(p["x"] * s), oy + int(p["y"] * s)
            pygame.draw.circle(screen, (90, 170, 255) if p["id"] == my_id else (200, 200, 255), (px, py), 3)
            if p["id"] == my_id and me:
                pygame.draw.line(screen, (255, 255, 255), (px, py), (px + int(math.cos(me["a"]) * 8), py + int(math.sin(me["a"]) * 8)), 1)
    pygame.draw.rect(screen, (95, 105, 125), (ox - 2, oy - 2, mw + 4, mh + 4), 2, border_radius=6)

def _draw_chat_widget(screen, base_x, base_y, panel_w, panel_h, title, rect_store):
    global CHAT_HAS_NEW_MESSAGE, CHAT_FOCUS
    panel_rect = pygame.Rect(base_x, base_y, panel_w, panel_h)
    input_w = panel_w - 80
    input_rect = pygame.Rect(base_x, base_y + panel_h + 6, input_w, 32)
    send_rect = pygame.Rect(base_x + panel_w - 74, base_y + panel_h + 6, 74, 32)
    rect_store["panel"] = panel_rect
    rect_store["input"] = input_rect
    rect_store["send"] = send_rect

    draw_panel(screen, panel_rect, alpha=175, border=(80, 90, 110))
    status = "已连接" if WS_CONNECTED else "连接中..."
    draw_text(screen, f"{title} [{status}]", 18, (255, 215, 95), topleft=(base_x + 10, base_y + 6))
    recent = CHAT_MESSAGES[-6:]
    for i, msg in enumerate(recent):
        y = base_y + 32 + i * 22
        color = (150, 200, 255) if msg.system else (235, 235, 235)
        name_color = (140, 150, 170) if msg.system else (180, 220, 255)
        name = f"[{msg.user}] " if not msg.system else ""
        draw_text(screen, name, 17, name_color, topleft=(base_x + 10, y))
        name_w = get_chinese_font(17).size(name)[0]
        draw_text(screen, msg.text[:40], 17, color, topleft=(base_x + 10 + name_w, y))

    border = (255, 190, 80) if CHAT_FOCUS else (70, 80, 100)
    pygame.draw.rect(screen, (20, 24, 32), input_rect, border_radius=6)
    pygame.draw.rect(screen, border, input_rect, 2, border_radius=6)
    if CHAT_FOCUS:
        cursor = "|" if int(time.time() * 2) % 2 == 0 else ""
        draw_text(screen, CHAT_INPUT + cursor, 17, (255, 255, 255), topleft=(input_rect.x + 8, input_rect.y + 6))
    else:
        hint = "点此或按回车发言" if not CHAT_HAS_NEW_MESSAGE else "有新消息"
        draw_text(screen, hint, 17, (150, 160, 180), topleft=(input_rect.x + 8, input_rect.y + 6))

    hov = send_rect.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(screen, (60, 150, 90) if hov else (40, 100, 60), send_rect, border_radius=6)
    pygame.draw.rect(screen, (120, 220, 150), send_rect, 2, border_radius=6)
    draw_text(screen, "发送", 17, (255, 255, 255), center=send_rect.center)

    rect_store["presets"] = []
    if CHAT_FOCUS:
        bw, bh = 96, 30
        gap = 6
        px = base_x
        py = base_y - bh - 8
        for i, phrase in enumerate(CHAT_PRESETS):
            r = pygame.Rect(px + i * (bw + gap), py, bw, bh)
            rect_store["presets"].append((r, phrase))
            hov = r.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, (60, 80, 120) if hov else (36, 48, 72), r, border_radius=6)
            pygame.draw.rect(screen, (120, 170, 240), r, 2, border_radius=6)
            draw_text(screen, phrase, 16, (235, 240, 255), center=r.center)

def draw_chat_game(screen):
    if not CHAT_ENABLED or not LOGIN_USER:
        return
    _draw_chat_widget(screen, 16, HEIGHT - 260, 520, 150, "聊天", CHAT_GAME_RECTS)

def draw_chat_menu(screen):
    if not CHAT_ENABLED or not LOGIN_USER:
        return
    panel_w = 520
    panel_h = 150
    base_x = WIDTH - panel_w - 20
    base_y = HEIGHT - panel_h - 40
    _draw_chat_widget(screen, base_x, base_y, panel_w, panel_h, "世界聊天", CHAT_MENU_RECTS)

def draw_world(screen, st, my_id, is_host, dt):
    global LAST_SYNC_TIME
    me = get_player_from_state(st, my_id) if st else None
    if not st or not me:
        screen.fill((15, 18, 22))
        draw_panel(screen, pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 60, 520, 120))
        draw_text(screen, "正在连接服务器...", 32, (235, 240, 245), center=(WIDTH // 2, HEIGHT // 2))
        return
    with CACHED_REMOTE_PLAYERS_LOCK:
        remote_players = CACHED_REMOTE_PLAYERS.copy()
    is_host_player = is_host or (me and me.get("is_host", False))
    FEED["hit"] = max(0, FEED["hit"] - dt)
    FEED["dmg"] = max(0, FEED["dmg"] - dt)
    FEED["muzzle"] = max(0, FEED["muzzle"] - dt)
    ehp = sum(e["hp"] for e in st.get("enemies", []))
    ecnt = len(st.get("enemies", []))
    if FEED["ehp"] is not None:
        if ehp < FEED["ehp"]:
            FEED["hit"] = 0.15
            play("hit")
        if ecnt < FEED["ecnt"]:
            play("die")
            add_text("消灭敌人!")
    FEED["ehp"], FEED["ecnt"] = ehp, ecnt
    if FEED["hp"] is not None and me["hp"] < FEED["hp"]:
        FEED["dmg"] = 0.35
        play("hurt")
    FEED["hp"] = me["hp"]
    if FEED["cans"] is not None:
        if me["cans"] > FEED["cans"]:
            play("pick")
            add_text("+1 罐头")
        if me["res"] > FEED["ammo"]:
            play("pick")
            add_text("+30 弹药")
        if me["med"] > FEED["med"]:
            play("pick")
            add_text("+1 医疗包")
    FEED["cans"], FEED["ammo"], FEED["med"] = me["cans"], me["res"], me["med"]
    if me["reload"] > 0 and not FEED["rl"]:
        play("reload")
    FEED["rl"] = me["reload"] > 0
    res = st.get("result", "play")
    if FEED["res"] != res:
        if res == "win":
            play("win")
            gained = me["cans"] * 100 + me.get("gold", 0) * 300
            tasks = me.get("tasks", {})
            task_reward = 0
            if tasks.get("kill", 0) >= 5:
                task_reward += 200
            if tasks.get("collect", 0) >= 3:
                task_reward += 150
            if tasks.get("extract", 0) >= 1:
                task_reward += 300
            gained += task_reward
            if task_reward > 0:
                add_text(f"任务奖励 +{task_reward} 金币")
            SAVE["money"] += gained
            SAVE["tasks"] = tasks
            push_save_async()
            add_text(f"撤离成功 +{gained} 金币")
        elif res == "lose":
            play("lose")
        FEED["res"] = res
    bob = math.sin(FEED["bob"]) * 4
    render_view(canvas, me["x"], me["y"], VIEW["a"], st, my_id, bob)
    screen.blit(pygame.transform.smoothscale(canvas, (WIDTH, HEIGHT)), (0, 0))
    if FEED["dmg"] > 0:
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((255, 0, 0, int(FEED["dmg"] * 220)))
        screen.blit(ov, (0, 0))
    if FEED["muzzle"] > 0:
        pygame.draw.circle(screen, (255, 220, 120), (WIDTH // 2 + 2, HEIGHT - 170 + int(bob)), 14)
    draw_panel(screen, pygame.Rect(16, 16, 470, 54))
    draw_text(screen, f"地图: {MAPS[CURRENT_MAP_IDX]['name']} ({THEMES['night' if IS_NIGHT else 'day']['name']})", 22, (215, 220, 232), topleft=(32, 30))
    if is_host_player:
        draw_text(screen, "房主", 18, (255, 215, 0), topleft=(WIDTH - 100, HEIGHT - 60))
    draw_panel(screen, pygame.Rect(WIDTH // 2 - 115, 16, 230, 54))
    for i in range(3):
        cx = WIDTH // 2 - 70 + i * 70
        filled = me["cans"] > i
        pygame.draw.circle(screen, (255, 175, 70) if filled else (52, 58, 72), (cx, 43), 15)
        pygame.draw.circle(screen, (255, 215, 150) if filled else (95, 102, 118), (cx, 43), 15, 2)
    if st.get("extract", 0) > 0:
        draw_text(screen, f"撤离中... {st['extract']:.1f}/3.0", 34, (110, 230, 140), center=(WIDTH // 2, 96))
    elif st.get("in_zone") and me["cans"] < 3:
        draw_text(screen, f"还差 {3 - me['cans']} 个罐头才能撤离！", 34, (255, 215, 95), center=(WIDTH // 2, 96))
    for i, tx in enumerate(FEED["texts"][:]):
        tx[1] -= dt
        if tx[1] <= 0:
            FEED["texts"].remove(tx)
            continue
        draw_text(screen, tx[0], 26, (255, 255, 255), center=(WIDTH // 2, 150 + i * 32))
    draw_panel(screen, pygame.Rect(16, HEIGHT - 92, 430, 76))
    ratio = max(0, me["hp"]) / me["maxhp"]
    col = (110, 230, 140) if ratio > 0.5 else (255, 215, 95) if ratio > 0.25 else (255, 90, 90)
    draw_text(screen, "生命", 20, (150, 160, 175), topleft=(32, HEIGHT - 88))
    draw_bar(screen, pygame.Rect(32, HEIGHT - 60, 270, 18), ratio, col)
    draw_text(screen, str(max(0, me["hp"])), 30, col, topleft=(312, HEIGHT - 66))
    draw_text(screen, f"医疗包 x{me['med']}  钥匙 {'有' if me.get('key') else '无'}  金罐头 {me.get('gold', 0)}", 20, (255, 230, 120), topleft=(32, HEIGHT - 36))
    draw_panel(screen, pygame.Rect(WIDTH - 246, HEIGHT - 92, 230, 76))
    if me["reload"] > 0:
        draw_text(screen, "换弹中...", 30, (255, 215, 95), center=(WIDTH - 131, HEIGHT - 54))
    else:
        draw_text(screen, str(me["mag"]), 46, (255, 255, 255), topleft=(WIDTH - 230, HEIGHT - 88))
        draw_text(screen, f"/ {me['res']}", 24, (150, 160, 175), topleft=(WIDTH - 160, HEIGHT - 60))
    draw_text(screen, f"敌人 {len(st.get('enemies', []))}", 20, (235, 140, 140), topleft=(WIDTH - 230, HEIGHT - 36))
    fps = int(1 / dt) if dt > 0 else 0
    draw_text(screen, f"FPS: {fps}", 14, (150, 200, 150), topleft=(WIDTH - 80, 10))
    if MULTIPLAYER_MODE:
        draw_text(screen, f"玩家 {len(remote_players)}", 14, (200, 200, 255), topleft=(WIDTH - 80, 30))
    cx, cy = WIDTH // 2, HEIGHT // 2
    pygame.draw.circle(screen, (240, 240, 240), (cx, cy), 2)
    g, l = 6, 9
    pygame.draw.line(screen, (240, 240, 240), (cx - g - l, cy), (cx - g, cy), 2)
    pygame.draw.line(screen, (240, 240, 240), (cx + g, cy), (cx + g + l, cy), 2)
    pygame.draw.line(screen, (240, 240, 240), (cx, cy - g - l), (cx, cy - g), 2)
    pygame.draw.line(screen, (240, 240, 240), (cx, cy + g), (cx, cy + g + l), 2)
    if FEED["hit"] > 0:
        pygame.draw.line(screen, (255, 80, 80), (cx - 14, cy - 14), (cx - 8, cy - 8), 3)
        pygame.draw.line(screen, (255, 80, 80), (cx + 8, cy - 8), (cx + 14, cy - 14), 3)
        pygame.draw.line(screen, (255, 80, 80), (cx - 14, cy + 14), (cx - 8, cy + 8), 3)
        pygame.draw.line(screen, (255, 80, 80), (cx + 8, cy + 8), (cx + 14, cy + 14), 3)
    draw_minimap(screen, st, my_id)
    draw_chat_game(screen)
    if LOGIN_USER and SYNC_RUNNING and MULTIPLAYER_MODE and CURRENT_ROOM_ID:
        moved = False
        if not hasattr(draw_world, 'last_pos'):
            draw_world.last_pos = (me["x"], me["y"])
            moved = True
        elif abs(me["x"] - draw_world.last_pos[0]) > 10 or abs(me["y"] - draw_world.last_pos[1]) > 10:
            moved = True
            draw_world.last_pos = (me["x"], me["y"])
        if moved:
            current_time = time.time()
            if current_time - LAST_SYNC_TIME > SYNC_INTERVAL:
                LAST_SYNC_TIME = current_time
                update_room_player_async(CURRENT_ROOM_ID, LOGIN_USER, me["x"], me["y"], VIEW["a"], me["hp"])
    res = st.get("result", "play")
    if res in ("win", "lose"):
        draw_overlay(screen, 190)
        win = res == "win"
        bc = (110, 230, 140) if win else (255, 90, 90)
        draw_panel(screen, pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 170, 660, 340), alpha=235, border=bc)
        draw_text(screen, "任务成功" if win else "任务失败", 64, bc, center=(WIDTH // 2, HEIGHT // 2 - 90))
        draw_text(screen, f"罐头 {min(me['cans'], 3)}/3 · 金罐头 {me.get('gold', 0)} · 剩余生命 {max(0, me['hp'])}", 26, (220, 225, 235), center=(WIDTH // 2, HEIGHT // 2 - 10))
        draw_text(screen, "按 ESC 返回主页", 22, (150, 160, 175), center=(WIDTH // 2, HEIGHT // 2 + 90))

def handle_touch_event(event):
    global FLASH_ON
    if event.type == pygame.FINGERDOWN:
        fx = int(event.x * WIDTH)
        fy = int(event.y * HEIGHT)
        fid = event.finger_id
        for key, btn in TOUCH_BUTTONS.items():
            if btn["rect"].collidepoint((fx, fy)):
                btn["pressed"] = True
                if key == "flash":
                    FLASH_ON = not FLASH_ON
                elif key == "chat":
                    toggle_chat_focus()
                return True
        if fx < WIDTH * 0.5 and fy > HEIGHT * 0.4:
            TOUCH_JOYSTICK["active"] = True
            TOUCH_JOYSTICK["touch_id"] = fid
            TOUCH_JOYSTICK["base_x"] = fx
            TOUCH_JOYSTICK["base_y"] = fy
            TOUCH_JOYSTICK["knob_x"] = fx
            TOUCH_JOYSTICK["knob_y"] = fy
            return True
        if fx > WIDTH * 0.5:
            TOUCH_JOYSTICK["look_id"] = fid
            TOUCH_JOYSTICK["look_x"] = fx
            return True
    elif event.type == pygame.FINGERMOTION:
        fx = int(event.x * WIDTH)
        fy = int(event.y * HEIGHT)
        fid = event.finger_id
        if TOUCH_JOYSTICK["active"] and TOUCH_JOYSTICK["touch_id"] == fid:
            dx = fx - TOUCH_JOYSTICK["base_x"]
            dy = fy - TOUCH_JOYSTICK["base_y"]
            dist = math.hypot(dx, dy)
            max_d = TOUCH_JOYSTICK["max_dist"]
            if dist > max_d:
                dx = dx / dist * max_d
                dy = dy / dist * max_d
            TOUCH_JOYSTICK["knob_x"] = TOUCH_JOYSTICK["base_x"] + dx
            TOUCH_JOYSTICK["knob_y"] = TOUCH_JOYSTICK["base_y"] + dy
            TOUCH_JOYSTICK["dx"] = dx / max_d
            TOUCH_JOYSTICK["dy"] = dy / max_d
            return True
        if TOUCH_JOYSTICK.get("look_id") == fid:
            dx = fx - TOUCH_JOYSTICK.get("look_x", fx)
            TOUCH_JOYSTICK["look_x"] = fx
            VIEW["a"] += dx * 0.01
            return True
    elif event.type == pygame.FINGERUP:
        fid = event.finger_id
        if TOUCH_JOYSTICK["active"] and TOUCH_JOYSTICK["touch_id"] == fid:
            TOUCH_JOYSTICK["active"] = False
            TOUCH_JOYSTICK["touch_id"] = None
            TOUCH_JOYSTICK["dx"] = 0
            TOUCH_JOYSTICK["dy"] = 0
            TOUCH_JOYSTICK["knob_x"] = TOUCH_JOYSTICK["base_x"]
            TOUCH_JOYSTICK["knob_y"] = TOUCH_JOYSTICK["base_y"]
            return True
        if TOUCH_JOYSTICK.get("look_id") == fid:
            TOUCH_JOYSTICK["look_id"] = None
            return True
        for key, btn in TOUCH_BUTTONS.items():
            if btn["pressed"]:
                btn["pressed"] = False
                return True
    return False

def draw_touch_controls(screen):
    pygame.draw.circle(screen, (255, 255, 255, 40),
                       (int(TOUCH_JOYSTICK["base_x"]), int(TOUCH_JOYSTICK["base_y"])),
                       TOUCH_JOYSTICK["max_dist"], 3)
    pygame.draw.circle(screen, (255, 200, 100, 180),
                       (int(TOUCH_JOYSTICK["knob_x"]), int(TOUCH_JOYSTICK["knob_y"])), 30)
    for key, btn in TOUCH_BUTTONS.items():
        r = btn["rect"]
        color = btn["color"]
        alpha = 220 if btn["pressed"] else 110
        if key == "chat" and CHAT_FOCUS:
            alpha = 240
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (*color, alpha), s.get_rect())
        pygame.draw.ellipse(s, (*color, 255), s.get_rect(), 3)
        screen.blit(s, r.topleft)
        draw_text(screen, btn["label"], 20, (255, 255, 255), center=r.center)

def menu_buttons():
    return {
        "solo": pygame.Rect(60, 160, 230, 45),
        "join": pygame.Rect(310, 160, 230, 45),
        "room_list": pygame.Rect(60, 215, 480, 45),
        "create_room": pygame.Rect(60, 270, 480, 45),
        "quit": pygame.Rect(60, 325, 480, 45),
        "help": pygame.Rect(60, 380, 480, 45),
        "map_prev": pygame.Rect(700, 190, 50, 40),
        "map_next": pygame.Rect(1090, 190, 50, 40),
        "toggle_night": pygame.Rect(680, 240, 420, 40),
        "buy_armor": pygame.Rect(680, 300, 420, 36),
        "buy_dmg": pygame.Rect(680, 345, 420, 36),
        "buy_ammo": pygame.Rect(680, 390, 420, 36),
        "user_box": pygame.Rect(60, 470, 220, 36),
        "pass_box": pygame.Rect(60, 520, 220, 36),
        "btn_register": pygame.Rect(300, 470, 100, 36),
        "btn_login": pygame.Rect(300, 520, 100, 36),
        "btn_logout": pygame.Rect(300, 470, 100, 36)
    }

def draw_button(screen, rect, text, small=False):
    h = rect.collidepoint(pygame.mouse.get_pos())
    s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(s, (52, 60, 76, 235) if h else (34, 40, 52, 210), s.get_rect(), border_radius=12)
    screen.blit(s, rect.topleft)
    pygame.draw.rect(screen, (255, 190, 80) if h else (90, 100, 120), rect, 2, border_radius=12)
    draw_text(screen, text, 22 if small else 30, (255, 255, 255) if h else (210, 215, 225), center=rect.center)

def draw_room_list(screen):
    global ROOM_LIST_PAGE, SHOW_ROOM_LIST, SHOW_CREATE_ROOM, ALERT_MSG, ALERT_TIME
    rooms = get_available_rooms()
    room_list = list(rooms.items())
    total_pages = max(1, (len(room_list) + ROOM_LIST_MAX_PER_PAGE - 1) // ROOM_LIST_MAX_PER_PAGE)
    start_idx = ROOM_LIST_PAGE * ROOM_LIST_MAX_PER_PAGE
    end_idx = min(start_idx + ROOM_LIST_MAX_PER_PAGE, len(room_list))
    page_rooms = room_list[start_idx:end_idx]
    draw_panel(screen, pygame.Rect(100, 80, 1080, 560), alpha=230, border=(255, 200, 100), radius=15)
    draw_text(screen, "房间列表", 40, (255, 200, 100), center=(WIDTH // 2, 120))
    back_rect = pygame.Rect(120, 90, 80, 35)
    draw_button(screen, back_rect, "返回", small=True)
    if back_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        SHOW_ROOM_LIST = False
        return
    draw_text(screen, f"共 {len(room_list)} 个房间", 18, (200, 200, 200), center=(WIDTH // 2, 155))
    if not page_rooms:
        draw_text(screen, "暂无可用房间", 24, (150, 150, 150), center=(WIDTH // 2, 300))
    else:
        y = 190
        for i, (room_id, room) in enumerate(page_rooms):
            card_rect = pygame.Rect(150, y, 980, 60)
            color = (60, 70, 90) if i % 2 == 0 else (50, 60, 80)
            s = pygame.Surface((card_rect.w, card_rect.h), pygame.SRCALPHA)
            s.fill((color[0], color[1], color[2], 200))
            pygame.draw.rect(s, s.get_at((0, 0)), s.get_rect(), border_radius=8)
            screen.blit(s, card_rect.topleft)
            player_count = len(room.get("players", []))
            max_players = room.get("max_players", 10)
            draw_text(screen, f"{room.get('name', '未命名')}", 20, (255, 255, 255), topleft=(170, y + 8))
            draw_text(screen, f"人数 {player_count}/{max_players}  房主 {room.get('host', '')[:15]}", 16, (200, 200, 200), topleft=(170, y + 32))
            join_btn = pygame.Rect(card_rect.right - 120, y + 12, 100, 36)
            can_join = room.get('status') == 'waiting' and player_count < max_players and LOGIN_USER
            draw_button(screen, join_btn, "加入" if can_join else "已满", small=True)
            if can_join and join_btn.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
                result = join_room(room_id, LOGIN_USER, "")
                if result.get('success'):
                    join_room_success(room_id, result.get('room'))
                else:
                    ALERT_MSG = result.get('message', "加入失败")
                    ALERT_TIME = 3.0
            y += 70
    if total_pages > 1:
        prev_rect = pygame.Rect(350, y + 20, 80, 35)
        next_rect = pygame.Rect(850, y + 20, 80, 35)
        draw_button(screen, prev_rect, "上一页", small=True)
        draw_button(screen, next_rect, "下一页", small=True)
        if prev_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0] and ROOM_LIST_PAGE > 0:
            ROOM_LIST_PAGE -= 1
        if next_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0] and ROOM_LIST_PAGE < total_pages - 1:
            ROOM_LIST_PAGE += 1
        draw_text(screen, f"{ROOM_LIST_PAGE + 1}/{total_pages}", 18, (200, 200, 200), center=(WIDTH // 2, y + 35))

def draw_create_room(screen):
    global SHOW_CREATE_ROOM, SHOW_ROOM_LIST, CREATE_ROOM_NAME, CREATE_ROOM_PASSWORD
    global CREATE_ROOM_MAP, CREATE_ROOM_NIGHT, CREATE_FOCUS, ALERT_MSG, ALERT_TIME
    draw_panel(screen, pygame.Rect(200, 100, 880, 480), alpha=230, border=(255, 200, 100), radius=15)
    draw_text(screen, "创建房间", 40, (255, 200, 100), center=(WIDTH // 2, 140))
    back_rect = pygame.Rect(220, 110, 80, 35)
    draw_button(screen, back_rect, "返回", small=True)
    if back_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        SHOW_CREATE_ROOM = False
        SHOW_ROOM_LIST = True
        return
    draw_text(screen, "房间名称:", 22, (200, 200, 200), topleft=(250, 190))
    name_rect = pygame.Rect(250, 220, 400, 40)
    name_color = (255, 190, 80) if CREATE_FOCUS == "name" else (90, 100, 120)
    pygame.draw.rect(screen, (30, 34, 44), name_rect)
    pygame.draw.rect(screen, name_color, name_rect, 2, border_radius=6)
    draw_text(screen, CREATE_ROOM_NAME or "输入房间名...", 20, (255, 255, 255) if CREATE_ROOM_NAME else (120, 130, 150), topleft=(260, 228))
    if name_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        CREATE_FOCUS = "name"
    draw_text(screen, "房间密码（留空为公开）:", 22, (200, 200, 200), topleft=(250, 280))
    pass_rect = pygame.Rect(250, 310, 400, 40)
    pass_color = (255, 190, 80) if CREATE_FOCUS == "password" else (90, 100, 120)
    pygame.draw.rect(screen, (30, 34, 44), pass_rect)
    pygame.draw.rect(screen, pass_color, pass_rect, 2, border_radius=6)
    draw_text(screen, ("*" * len(CREATE_ROOM_PASSWORD)) or "设置密码...", 20, (255, 255, 255) if CREATE_ROOM_PASSWORD else (120, 130, 150), topleft=(260, 318))
    if pass_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        CREATE_FOCUS = "password"
    draw_text(screen, "选择地图:", 22, (200, 200, 200), topleft=(250, 370))
    map_names = [m["name"] for m in MAPS]
    for i, name in enumerate(map_names):
        btn_rect = pygame.Rect(250 + i * 160, 400, 140, 36)
        is_selected = (i == CREATE_ROOM_MAP)
        color = (255, 190, 80) if is_selected else (50, 60, 80)
        pygame.draw.rect(screen, color, btn_rect, border_radius=8)
        draw_text(screen, name, 18, (255, 255, 255), center=btn_rect.center)
        if btn_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
            CREATE_ROOM_MAP = i
    night_rect = pygame.Rect(700, 370, 180, 40)
    draw_button(screen, night_rect, "黑夜" if CREATE_ROOM_NIGHT else "白天", small=True)
    if night_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        CREATE_ROOM_NIGHT = not CREATE_ROOM_NIGHT
    create_btn = pygame.Rect(400, 470, 200, 45)
    draw_button(screen, create_btn, "创建房间", small=False)
    if create_btn.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        if not CREATE_ROOM_NAME.strip():
            ALERT_MSG = "请输入房间名称"
            ALERT_TIME = 3.0
        elif not LOGIN_USER:
            ALERT_MSG = "请先登录"
            ALERT_TIME = 3.0
        else:
            result = create_room(CREATE_ROOM_NAME.strip(), CREATE_ROOM_PASSWORD, LOGIN_USER, CREATE_ROOM_MAP, CREATE_ROOM_NIGHT)
            if result.get('success'):
                SHOW_CREATE_ROOM = False
                SHOW_ROOM_LIST = False
                join_room_success(result['room_id'], result['room'])
            else:
                ALERT_MSG = result.get('message', "创建失败")
                ALERT_TIME = 3.0

def draw_menu(screen, url):
    global HELP_OPEN, SHOW_ROOM_LIST, SHOW_CREATE_ROOM, ALERT_MSG, ALERT_TIME
    if SHOW_ROOM_LIST:
        draw_room_list(screen)
        return
    if SHOW_CREATE_ROOM:
        draw_create_room(screen)
        return
    if MENU_BG:
        screen.blit(MENU_BG, (0, 0))
    else:
        screen.fill((15, 18, 22))
    draw_text(screen, "八宝粥行动", 72, (0, 0, 0), center=(WIDTH // 2 + 3, 63))
    draw_text(screen, "八宝粥行动", 72, (255, 200, 100), center=(WIDTH // 2, 60))
    draw_text(screen, "BA BAO ZHOU ACTION", 24, (140, 150, 170), center=(WIDTH // 2, 110))
    btns = menu_buttons()
    draw_panel(screen, pygame.Rect(40, 110, 520, 370), alpha=140)
    draw_text(screen, "开始行动", 26, (255, 255, 255), center=(300, 130))
    draw_button(screen, btns["solo"], "单人模式")
    draw_button(screen, btns["join"], "加入游戏")
    draw_button(screen, btns["room_list"], "房间列表")
    draw_button(screen, btns["create_room"], "创建房间")
    draw_button(screen, btns["quit"], "退出游戏")
    draw_button(screen, btns["help"], "操作帮助")
    draw_panel(screen, pygame.Rect(40, 460, 520, 160), alpha=140)
    if not LOGIN_USER:
        ub = btns["user_box"]
        pygame.draw.rect(screen, (30, 34, 44), ub)
        pygame.draw.rect(screen, (255, 190, 80) if login_focus == "user" else (90, 100, 120), ub, 2, border_radius=6)
        draw_text(screen, login_user_text or "用户名", 20, (255, 255, 255) if login_user_text else (120, 130, 150), topleft=(ub.x + 8, ub.y + 8))
        pb = btns["pass_box"]
        pygame.draw.rect(screen, (30, 34, 44), pb)
        pygame.draw.rect(screen, (255, 190, 80) if login_focus == "pass" else (90, 100, 120), pb, 2, border_radius=6)
        draw_text(screen, "*" * len(login_pass_text) or "密码", 20, (255, 255, 255) if login_pass_text else (120, 130, 150), topleft=(pb.x + 8, pb.y + 8))
        draw_button(screen, btns["btn_register"], "注册", small=True)
        draw_button(screen, btns["btn_login"], "登录", small=True)
        if login_msg:
            draw_text(screen, login_msg, 20, (255, 215, 0), center=(300, 590))
    else:
        draw_text(screen, f"已登录：{LOGIN_USER}", 22, (110, 230, 140), topleft=(60, 470))
        draw_button(screen, btns["btn_logout"], "退出登录", small=True)
    draw_panel(screen, pygame.Rect(660, 110, 520, 140), alpha=140)
    draw_text(screen, "战斗设置", 26, (255, 255, 255), center=(920, 130))
    draw_text(screen, MAPS[CURRENT_MAP_IDX]["name"], 30, (255, 255, 255), center=(920, 170))
    draw_button(screen, btns["map_prev"], "<", small=True)
    draw_button(screen, btns["map_next"], ">", small=True)
    draw_button(screen, btns["toggle_night"], f"昼夜：{THEMES['night' if IS_NIGHT else 'day']['name']}", small=True)
    draw_panel(screen, pygame.Rect(660, 270, 520, 190), alpha=140)
    draw_text(screen, "补给商店", 26, (255, 255, 255), topleft=(680, 280))
    draw_text(screen, f"金币：{SAVE.get('money', 0)}", 26, (255, 215, 95), topleft=(920, 280))
    draw_button(screen, btns["buy_armor"], f"护甲+50 · 200币 · Lv{SAVE.get('armor', 0)}", small=True)
    draw_button(screen, btns["buy_dmg"], f"伤害+10 · 300币 · Lv{SAVE.get('dmg', 0)}", small=True)
    draw_button(screen, btns["buy_ammo"], f"备弹+60 · 100币 · Lv{SAVE.get('ammo', 0)}", small=True)
    draw_panel(screen, pygame.Rect(660, 480, 520, 130), alpha=140)
    draw_text(screen, "今日任务", 22, (255, 215, 95), center=(920, 500))
    tasks = SAVE.get("tasks", {})
    draw_text(screen, f"击杀敌人：{min(tasks.get('kill',0),5)}/5", 20, (220, 220, 220), center=(920, 530))
    draw_text(screen, f"收集罐头：{min(tasks.get('collect',0),3)}/3", 20, (220, 220, 220), center=(920, 560))
    draw_text(screen, f"成功撤离：{min(tasks.get('extract',0),1)}/1", 20, (220, 220, 220), center=(920, 590))
    draw_text(screen, f"服务器：{url}", 16, (150, 160, 175), center=(WIDTH // 2, 680))
    draw_chat_menu(screen)
    if HELP_OPEN:
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 200))
        screen.blit(ov, (0, 0))
        rect = pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 220, 600, 440)
        draw_panel(screen, rect, alpha=240, border=(255, 200, 100), radius=15)
        draw_text(screen, "操作指南", 36, (255, 200, 100), center=(WIDTH // 2, HEIGHT // 2 - 180))
        controls = [
            ("左侧摇杆", "移动角色"),
            ("右侧滑动", "转动视角"),
            ("射击", "开火"),
            ("换弹", "换弹"),
            ("治疗", "使用医疗包"),
            ("手电", "开关手电筒"),
            ("互动", "开门/对话"),
            ("疾跑", "冲刺加速"),
            ("聊天键", "打开/关闭聊天"),
            ("回车 / 发送", "发送消息"),
            ("预设短语", "一点即发"),
        ]
        for i, (key, desc) in enumerate(controls):
            y = HEIGHT // 2 - 150 + i * 30
            draw_text(screen, key, 22, (255, 215, 95), topleft=(WIDTH // 2 - 250, y))
            draw_text(screen, desc, 22, (220, 220, 220), topleft=(WIDTH // 2 - 50, y))
        draw_text(screen, "点击任意处关闭", 18, (150, 150, 150), center=(WIDTH // 2, HEIGHT // 2 + 190))
    if ALERT_TIME > 0:
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 200))
        screen.blit(ov, (0, 0))
        rect = pygame.Rect(WIDTH // 2 - 280, HEIGHT // 2 - 100, 560, 200)
        draw_panel(screen, rect, alpha=240, border=(255, 60, 60), radius=15)
        draw_text(screen, "访问受限", 42, (255, 80, 80), center=(WIDTH // 2, HEIGHT // 2 - 40))
        draw_text(screen, ALERT_MSG, 26, (255, 255, 255), center=(WIDTH // 2, HEIGHT // 2 + 20))
        draw_text(screen, f"剩余 {max(0, int(ALERT_TIME) + 1)} 秒", 18, (180, 180, 180), center=(WIDTH // 2, HEIGHT // 2 + 60))

def join_multiplayer_game():
    global MULTIPLAYER_MODE, MULTIPLAYER_GAME, REMOTE_PLAYERS, ALERT_MSG, ALERT_TIME
    if not LOGIN_USER:
        ALERT_MSG = "请先登录账号！"
        ALERT_TIME = 3.0
        return False
    status_data = get_cached_room_status()
    if not status_data or not status_data.get('success'):
        ALERT_MSG = "服务器连接失败"
        ALERT_TIME = 3.0
        return False
    players = status_data.get('players', [])
    for p in players:
        if p.get('name') == LOGIN_USER:
            MULTIPLAYER_MODE = True
            with CACHED_REMOTE_PLAYERS_LOCK:
                CACHED_REMOTE_PLAYERS.clear()
            VIEW["a"] = 0.0
            reset_feed()
            MULTIPLAYER_GAME = new_game([LOGIN_USER], CURRENT_MAP_IDX)
            return True
    ALERT_MSG = "没有可加入的房间"
    ALERT_TIME = 3.0
    return False

def leave_multiplayer_game():
    global MULTIPLAYER_MODE, MULTIPLAYER_GAME, CURRENT_ROOM_ID
    if LOGIN_USER and CURRENT_ROOM_ID:
        leave_room_async(CURRENT_ROOM_ID, LOGIN_USER)
    MULTIPLAYER_MODE = False
    MULTIPLAYER_GAME = None
    CURRENT_ROOM_ID = None

def _handle_chat_click(pos):
    global CHAT_FOCUS
    stores = []
    if mode == "menu":
        stores.append(CHAT_MENU_RECTS)
    elif mode in ("solo", "multiplayer"):
        stores.append(CHAT_GAME_RECTS)
    for store in stores:
        send_rect = store.get("send")
        if send_rect and send_rect.collidepoint(pos) and LOGIN_USER:
            if CHAT_INPUT.strip():
                chat_send_message(CHAT_INPUT)
            toggle_chat_focus()
            return True
        input_rect = store.get("input")
        if input_rect and input_rect.collidepoint(pos) and LOGIN_USER:
            if not CHAT_FOCUS:
                toggle_chat_focus()
            return True
        for r, phrase in store.get("presets", []):
            if r.collidepoint(pos) and LOGIN_USER:
                chat_send_message(phrase)
                if CHAT_FOCUS:
                    toggle_chat_focus()
                return True
    return False

def main():
    global canvas, login_user_text, login_pass_text, login_focus, FLASH_ON, MERCHANT_OPEN, ALERT_TIME, HELP_OPEN
    global MULTIPLAYER_MODE, MULTIPLAYER_GAME, LAST_SYNC_TIME, CURRENT_ROOM_ID
    global SHOW_ROOM_LIST, SHOW_CREATE_ROOM, CREATE_ROOM_NAME, CREATE_ROOM_PASSWORD
    global CREATE_ROOM_MAP, CREATE_ROOM_NIGHT, ROOM_LIST_PAGE, CREATE_FOCUS
    global mode, CHAT_FOCUS

    pygame.init()
    pygame.font.init()
    start_ws_reconnect()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("八宝粥行动 - 手机版")
    clock = pygame.time.Clock()
    canvas = pygame.Surface((RES_W, RES_H))
    pygame.key.start_text_input()
    make_ui_assets()
    make_sounds()
    apply_config(0, False)
    url = SERVER_URL
    mode = "menu"
    solo_game = None
    running = True

    print("[系统] 八宝粥行动 - 手机版")
    print(f"[系统] 服务器: {SERVER_URL}")

    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        if ALERT_TIME > 0:
            ALERT_TIME -= dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                stop_php_sync()
                stop_websocket()
                stop_ws_reconnect()
                if MULTIPLAYER_MODE and LOGIN_USER and CURRENT_ROOM_ID:
                    leave_room_async(CURRENT_ROOM_ID, LOGIN_USER)
            elif ev.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
                if handle_touch_event(ev):
                    continue
            elif ev.type == pygame.KEYDOWN:
                if CHAT_FOCUS:
                    chat_handle_keydown(ev)
                    continue
                if HELP_OPEN and ev.key == pygame.K_ESCAPE:
                    HELP_OPEN = False
                elif mode == "menu" and LOGIN_USER and not SHOW_ROOM_LIST and not SHOW_CREATE_ROOM and not HELP_OPEN:
                    if ev.key == pygame.K_RETURN and CHAT_ENABLED:
                        toggle_chat_focus()
                    elif ev.key == pygame.K_r and CHAT_ENABLED:
                        if WS_CONNECTED:
                            add_text("聊天已连接")
                        else:
                            add_text("聊天重连中...")
                            start_websocket()
                elif mode == "menu" and not LOGIN_USER:
                    if ev.key == pygame.K_TAB:
                        login_focus = "pass" if login_focus == "user" else "user"
                    elif ev.key == pygame.K_BACKSPACE:
                        if login_focus == "user":
                            login_user_text = login_user_text[:-1]
                        else:
                            login_pass_text = login_pass_text[:-1]
                    elif ev.key == pygame.K_RETURN:
                        do_login()
                elif SHOW_CREATE_ROOM:
                    if ev.key == pygame.K_ESCAPE:
                        SHOW_CREATE_ROOM = False
                        SHOW_ROOM_LIST = True
                    elif ev.key == pygame.K_BACKSPACE:
                        if CREATE_FOCUS == "name":
                            CREATE_ROOM_NAME = CREATE_ROOM_NAME[:-1]
                        elif CREATE_FOCUS == "password":
                            CREATE_ROOM_PASSWORD = CREATE_ROOM_PASSWORD[:-1]
                    elif ev.key == pygame.K_TAB:
                        CREATE_FOCUS = "password" if CREATE_FOCUS == "name" else "name"
                elif SHOW_ROOM_LIST:
                    if ev.key == pygame.K_ESCAPE:
                        SHOW_ROOM_LIST = False
                if mode in ("solo", "multiplayer") and ev.key == pygame.K_f:
                    FLASH_ON = not FLASH_ON
                if mode in ("solo", "multiplayer") and ev.key == pygame.K_ESCAPE:
                    if mode == "multiplayer":
                        leave_multiplayer_game()
                    mode = "menu"
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                    reset_feed()
                    MERCHANT_OPEN = False
                if mode == "solo" and solo_game and solo_game["result"] != "play" and ev.key == pygame.K_RETURN:
                    reset_game(solo_game)
                    VIEW["a"] = 0.0
                    reset_feed()
                if mode == "solo" and ev.key == pygame.K_b and MERCHANT_OPEN:
                    p = solo_game["players"][0]
                    if p["cans"] >= 1:
                        p["cans"] -= 1
                        p["med"] += 1
                        play("buy")
                        add_text("购买急救包 -1 罐头")
                if ev.key == pygame.K_RETURN and not CHAT_FOCUS and CHAT_ENABLED and mode in ("solo", "multiplayer"):
                    if LOGIN_USER:
                        toggle_chat_focus()
                    else:
                        chat_add_system_message("请先登录再发言")
                if ev.key == pygame.K_r and not CHAT_FOCUS and not HELP_OPEN and mode in ("solo", "multiplayer"):
                    if WS_CONNECTED:
                        add_text("聊天已连接")
                    else:
                        add_text("聊天重连中...")
                        start_websocket()
                if ev.key == pygame.K_1 and mode in ("solo", "multiplayer"):
                    is_host = False
                    if mode == "solo":
                        is_host = True
                    elif mode == "multiplayer":
                        room_status = get_cached_room_status()
                        if room_status and room_status.get('success'):
                            host = room_status.get('host', '')
                            is_host = (LOGIN_USER == host)
                    if is_host:
                        if mode == "solo":
                            game = solo_game
                            pid = 0
                        else:
                            game = MULTIPLAYER_GAME
                            pid = LOGIN_USER
                        if game and pid in game["players"]:
                            p = game["players"][pid]
                            p["cans"] = 10
                            p["res"] = 500
                            p["med"] = 10
                            p["mag"] = 30
                            p["gold"] = 10
                            p["key"] = 1
                            p["hp"] = p["maxhp"]
                            add_text("已获取全部物资！")
                            if mode == "multiplayer" and CURRENT_ROOM_ID:
                                update_room_player_async(CURRENT_ROOM_ID, LOGIN_USER, p["x"], p["y"], VIEW["a"], p["hp"])
                    else:
                        add_text("只有房主才能使用此功能")
            elif ev.type == pygame.TEXTINPUT:
                if CHAT_FOCUS:
                    chat_handle_textinput(ev.text)
                elif SHOW_CREATE_ROOM:
                    if CREATE_FOCUS == "name":
                        CREATE_ROOM_NAME += ev.text
                    elif CREATE_FOCUS == "password":
                        CREATE_ROOM_PASSWORD += ev.text
                elif mode == "menu" and not LOGIN_USER:
                    if login_focus == "user":
                        login_user_text += ev.text
                    else:
                        login_pass_text += ev.text
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if _handle_chat_click(ev.pos):
                    continue
                if CHAT_FOCUS:
                    toggle_chat_focus()
                    continue
                if HELP_OPEN:
                    HELP_OPEN = False
                elif mode == "menu" and not SHOW_ROOM_LIST and not SHOW_CREATE_ROOM:
                    pos = ev.pos
                    btns = menu_buttons()
                    if btns["user_box"].collidepoint(pos):
                        login_focus = "user"
                    elif btns["pass_box"].collidepoint(pos):
                        login_focus = "pass"
                    elif btns["btn_register"].collidepoint(pos):
                        do_register()
                    elif btns["btn_login"].collidepoint(pos):
                        do_login()
                    elif btns["btn_logout"].collidepoint(pos) and LOGIN_USER:
                        do_logout()
                    elif btns["map_prev"].collidepoint(pos):
                        apply_config(CURRENT_MAP_IDX - 1, IS_NIGHT)
                    elif btns["map_next"].collidepoint(pos):
                        apply_config(CURRENT_MAP_IDX + 1, IS_NIGHT)
                    elif btns["toggle_night"].collidepoint(pos):
                        apply_config(CURRENT_MAP_IDX, not IS_NIGHT)
                    elif btns["buy_armor"].collidepoint(pos) and SAVE["money"] >= 200:
                        SAVE["money"] -= 200
                        SAVE["armor"] += 1
                        push_save_async()
                    elif btns["buy_dmg"].collidepoint(pos) and SAVE["money"] >= 300:
                        SAVE["money"] -= 300
                        SAVE["dmg"] += 1
                        push_save_async()
                    elif btns["buy_ammo"].collidepoint(pos) and SAVE["money"] >= 100:
                        SAVE["money"] -= 100
                        SAVE["ammo"] += 1
                        push_save_async()
                    elif btns["help"].collidepoint(pos):
                        HELP_OPEN = True
                    elif btns["join"].collidepoint(pos):
                        if join_multiplayer_game():
                            mode = "multiplayer"
                    elif btns["room_list"].collidepoint(pos):
                        if LOGIN_USER:
                            SHOW_ROOM_LIST = True
                            SHOW_CREATE_ROOM = False
                            ROOM_LIST_PAGE = 0
                        else:
                            ALERT_MSG = "请先登录"
                            ALERT_TIME = 3.0
                    elif btns["create_room"].collidepoint(pos):
                        if LOGIN_USER:
                            SHOW_CREATE_ROOM = True
                            SHOW_ROOM_LIST = False
                            CREATE_ROOM_NAME = ""
                            CREATE_ROOM_PASSWORD = ""
                            CREATE_ROOM_MAP = 0
                            CREATE_ROOM_NIGHT = False
                            CREATE_FOCUS = "name"
                        else:
                            ALERT_MSG = "请先登录"
                            ALERT_TIME = 3.0
                    elif btns["solo"].collidepoint(pos):
                        if not LOGIN_USER:
                            ALERT_MSG = "请先注册并登录账号！"
                            ALERT_TIME = 3.0
                        else:
                            solo_game = new_game([0], CURRENT_MAP_IDX)
                            VIEW["a"] = 0.0
                            reset_feed()
                            mode = "solo"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                    elif btns["quit"].collidepoint(pos):
                        running = False
                        stop_php_sync()
                        stop_websocket()
                        stop_ws_reconnect()

        if mode == "menu":
            draw_menu(screen, url)
        elif mode == "solo":
            p = solo_game["players"][0]
            m = solo_game.get("merchant")
            if m and math.hypot(m["x"] - p["x"], m["y"] - p["y"]) < 80:
                p["merchant_near"] = True
            else:
                p["merchant_near"] = False
            if p.get("merchant_near") and pygame.key.get_pressed()[pygame.K_e]:
                MERCHANT_OPEN = True
            elif not p.get("merchant_near"):
                MERCHANT_OPEN = False
            solo_game["inputs"][0] = read_input(p["x"], p["y"], dt)
            server_update(solo_game, dt)
            st = make_state(solo_game)
            draw_world(screen, st, 0, True, dt)
            draw_touch_controls(screen)
            if MERCHANT_OPEN:
                draw_overlay(screen, 200)
                draw_panel(screen, pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 150, 400, 300), alpha=240, border=(255, 215, 0))
                draw_text(screen, "黑市商人", 36, (255, 215, 0), center=(WIDTH // 2, HEIGHT // 2 - 100))
                draw_text(screen, f"你的罐头：{p['cans']}  金罐头：{p.get('gold', 0)}", 20, (255, 255, 255), center=(WIDTH // 2, HEIGHT // 2 - 50))
                for i, item in enumerate(MERCHANT_ITEMS):
                    y_pos = HEIGHT // 2 + i * 50
                    can_afford = (item["key"] == "gold" and p.get("gold", 0) >= item["price"]) or (item["key"] != "gold" and p["cans"] >= item["price"])
                    color = (255, 255, 255) if can_afford else (100, 100, 100)
                    draw_text(screen, f"{item['name']} - {item['price']} {'金罐头' if item['key'] == 'gold' else '罐头'}", 24, color, center=(WIDTH // 2, y_pos))
                draw_text(screen, "按 B 购买急救包 (1 罐头)", 18, (200, 200, 200), center=(WIDTH // 2, HEIGHT // 2 + 120))
        elif mode == "multiplayer":
            if MULTIPLAYER_GAME is None:
                MULTIPLAYER_GAME = new_game([LOGIN_USER], CURRENT_MAP_IDX)
            p = MULTIPLAYER_GAME["players"].get(LOGIN_USER)
            if not p or p["hp"] <= 0:
                if MULTIPLAYER_GAME["result"] == "lose":
                    draw_overlay(screen, 200)
                    draw_panel(screen, pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 100, 400, 200), alpha=240, border=(255, 90, 90))
                    draw_text(screen, "你已阵亡", 48, (255, 90, 90), center=(WIDTH // 2, HEIGHT // 2 - 30))
                    draw_text(screen, "按 ESC 返回菜单", 24, (200, 200, 200), center=(WIDTH // 2, HEIGHT // 2 + 40))
                    pygame.display.flip()
                    continue
            inp = read_input(p["x"], p["y"], dt)
            MULTIPLAYER_GAME["inputs"][LOGIN_USER] = inp
            server_update(MULTIPLAYER_GAME, dt)
            with CACHED_REMOTE_PLAYERS_LOCK:
                remote_players = CACHED_REMOTE_PLAYERS.copy()
            st = make_state(MULTIPLAYER_GAME)
            for name, player_data in remote_players.items():
                if name != LOGIN_USER:
                    if not any(pp.get('id') == name for pp in st.get('players', [])):
                        st['players'].append({
                            'id': name,
                            'x': player_data.get('x', 0),
                            'y': player_data.get('y', 0),
                            'a': player_data.get('angle', 0),
                            'hp': player_data.get('hp', 100),
                            'maxhp': 100, 'mag': 30, 'res': 120, 'cans': 0, 'gold': 0,
                            'key': 0, 'med': 0, 'dmg': 25, 'reload': 0, 'shoot_cd': 0, 'med_cd': 0,
                            'tasks': {"kill": 0, "collect": 0, "extract": 0}
                        })
            room_status = get_cached_room_status()
            is_host = False
            if room_status and room_status.get('success'):
                host = room_status.get('host', '')
                is_host = (LOGIN_USER == host)
            draw_world(screen, st, LOGIN_USER, is_host, dt)
            draw_touch_controls(screen)
            if MULTIPLAYER_GAME["result"] != "play":
                if MULTIPLAYER_GAME["result"] == "win":
                    draw_overlay(screen, 180)
                    draw_panel(screen, pygame.Rect(WIDTH // 2 - 250, HEIGHT // 2 - 120, 500, 240), alpha=240, border=(110, 230, 140))
                    draw_text(screen, "团队胜利！", 48, (110, 230, 140), center=(WIDTH // 2, HEIGHT // 2 - 40))
                    draw_text(screen, "按 ESC 返回菜单", 24, (200, 200, 200), center=(WIDTH // 2, HEIGHT // 2 + 40))
                elif MULTIPLAYER_GAME["result"] == "lose":
                    draw_overlay(screen, 180)
                    draw_panel(screen, pygame.Rect(WIDTH // 2 - 250, HEIGHT // 2 - 120, 500, 240), alpha=240, border=(255, 90, 90))
                    draw_text(screen, "团灭", 48, (255, 90, 90), center=(WIDTH // 2, HEIGHT // 2 - 40))
                    draw_text(screen, "按 ESC 返回菜单", 24, (200, 200, 200), center=(WIDTH // 2, HEIGHT // 2 + 40))
            if LOGIN_USER and SYNC_RUNNING and MULTIPLAYER_MODE and CURRENT_ROOM_ID:
                current_time = time.time()
                if current_time - LAST_SYNC_TIME > SYNC_INTERVAL:
                    LAST_SYNC_TIME = current_time
                    update_room_player_async(CURRENT_ROOM_ID, LOGIN_USER, p["x"], p["y"], VIEW["a"], p["hp"])

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()