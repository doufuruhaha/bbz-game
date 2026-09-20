import pygame, sys, os, json, math, random, time, threading
import requests
import websocket

os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

WIDTH, HEIGHT = 1280, 720
RES_W, RES_H = 800, 450
MOUSE_SENS = 0.0022
SERVER_URL = "https://bbz-chat-1.onrender.com"
WS_URL = "wss://bbz-chat-1.onrender.com"
WS_ROOM = "global"

SAVE = {"money": 0, "armor": 0, "dmg": 0, "ammo": 0,
        "tasks": {"kill": 0, "collect": 0, "extract": 0}}

# ==================== 每日任务系统 ====================
TASKS_FILE = "daily_tasks.json"

TASK_POOL = [
    {"id": "sniper_kill_3", "name": "神枪手", "desc": "用狙击枪击杀 3 名敌人",
     "metric": "sniper_kills", "target": 3, "reward": 400},
    {"id": "kill_8", "name": "清道夫", "desc": "击杀 8 名敌人",
     "metric": "kills", "target": 8, "reward": 350},
    {"id": "boss_kill", "name": "屠龙者", "desc": "击杀 1 名重装Boss",
     "metric": "boss_kills", "target": 1, "reward": 600},
    {"id": "shotgun_kill_2", "name": "近战之王", "desc": "用霰弹枪击杀 2 名敌人",
     "metric": "shotgun_kills", "target": 2, "reward": 300},
    {"id": "gold_5", "name": "淘金热", "desc": "收集 5 个金罐头",
     "metric": "gold_cans", "target": 5, "reward": 500},
    {"id": "can_10", "name": "罐头收藏家", "desc": "收集 10 个普通罐头",
     "metric": "cans", "target": 10, "reward": 300},
    {"id": "medkit_3", "name": "医疗储备", "desc": "拾取 3 个医疗包",
     "metric": "medkits", "target": 3, "reward": 250},
    {"id": "no_damage_extract", "name": "完美行动", "desc": "不受伤成功撤离 1 次",
     "metric": "no_damage_extracts", "target": 1, "reward": 700},
    {"id": "night_extract", "name": "夜行者", "desc": "在黑夜地图成功撤离 1 次",
     "metric": "night_extracts", "target": 1, "reward": 500},
    {"id": "extract_2", "name": "常胜将军", "desc": "成功撤离 2 次",
     "metric": "extracts", "target": 2, "reward": 400},
    {"id": "full_backpack", "name": "满载而归", "desc": "背包满时成功撤离 1 次",
     "metric": "full_backpack_extracts", "target": 1, "reward": 450},
]

DAILY_TASKS = None

def today_str():
    return time.strftime("%Y-%m-%d")

def new_task_progress():
    return {"date": today_str(), "tasks": [], "claimed": [], "progress": {}}

def save_daily_tasks(data=None):
    global DAILY_TASKS
    if data is None:
        data = DAILY_TASKS
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_daily_tasks():
    global DAILY_TASKS
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = new_task_progress()
    except Exception:
        data = new_task_progress()
    today = today_str()
    need_refresh = (data.get("date") != today or not data.get("tasks"))
    if need_refresh:
        rng = random.Random(today)
        picked = rng.sample(TASK_POOL, min(3, len(TASK_POOL)))
        old_claimed = data.get("claimed", []) if data.get("date") == today else []
        old_progress = data.get("progress", {}) if data.get("date") == today else {}
        picked_ids = [t["id"] for t in picked]
        data = {
            "date": today, "tasks": picked_ids,
            "claimed": [c for c in old_claimed if c in picked_ids],
            "progress": {tid: old_progress.get(tid, 0) for tid in picked_ids},
        }
        save_daily_tasks(data)
    DAILY_TASKS = data
    return data

def fetch_server_daily_tasks():
    for attempt in range(2):
        try:
            timeout = 30 if attempt == 0 else 15
            r = requests.get(SERVER_URL + "/api/daily_tasks", timeout=timeout)
            if r.status_code != 200:
                continue
            data = r.json()
            if not data.get("success"):
                continue
            return data
        except Exception as e:
            print(f"[任务] 第 {attempt+1} 次拉取失败: {e}")
    return None


def load_daily_tasks_from_server():
    global DAILY_TASKS
    data = fetch_server_daily_tasks()
    today = today_str()
    if data and data.get("tasks"):
        tasks = []
        progress = {}
        for t in data["tasks"]:
            tid = t.get("id")
            if not tid:
                continue
            existing = get_task_def(tid)
            if not existing:
                TASK_POOL.append({
                    "id": tid, "name": t.get("name", tid),
                    "desc": t.get("desc", ""), "metric": t.get("metric", "kills"),
                    "target": int(t.get("target", 1)), "reward": int(t.get("reward", 100)),
                })
            else:
                existing["name"] = t.get("name", existing["name"])
                existing["desc"] = t.get("desc", existing["desc"])
                existing["metric"] = t.get("metric", existing["metric"])
                existing["target"] = int(t.get("target", existing["target"]))
                existing["reward"] = int(t.get("reward", existing["reward"]))
            tasks.append(tid)
            progress[tid] = 0
        old = DAILY_TASKS or {}
        if old.get("date") == today:
            for tid in tasks:
                if tid in old.get("progress", {}):
                    progress[tid] = old["progress"][tid]
        old_claimed = old.get("claimed", []) if old.get("date") == today else []
        DAILY_TASKS = {
            "date": today, "tasks": tasks,
            "claimed": [c for c in old_claimed if c in tasks],
            "progress": progress,
        }
        save_daily_tasks()
        print(f"[任务] 已从服务器加载 {len(tasks)} 个任务")
        return True
    print("[任务] 服务器未布置，使用本地随机任务")
    load_daily_tasks()
    return False


def get_task_def(task_id):
    for t in TASK_POOL:
        if t["id"] == task_id:
            return t
    return None

def task_add_progress(metric, amount=1):
    if not DAILY_TASKS:
        return
    changed = False
    for tid in DAILY_TASKS.get("tasks", []):
        tdef = get_task_def(tid)
        if not tdef or tdef["metric"] != metric:
            continue
        if tid in DAILY_TASKS.get("claimed", []):
            continue
        cur = DAILY_TASKS["progress"].get(tid, 0)
        if cur >= tdef["target"]:
            continue
        DAILY_TASKS["progress"][tid] = min(tdef["target"], cur + amount)
        changed = True
    if changed:
        save_daily_tasks()

def task_is_complete(task_id):
    tdef = get_task_def(task_id)
    if not tdef:
        return False
    return DAILY_TASKS["progress"].get(task_id, 0) >= tdef["target"]

def task_claim(task_id):
    global SAVE
    tdef = get_task_def(task_id)
    if not tdef:
        return False, "任务不存在"
    if task_id in DAILY_TASKS.get("claimed", []):
        return False, "已领取"
    if not task_is_complete(task_id):
        return False, "任务未完成"
    DAILY_TASKS.setdefault("claimed", []).append(task_id)
    save_daily_tasks()
    _rw = tdef["reward"]
    if IS_VIP:
        _rw = _rw * 2
    SAVE["money"] = SAVE.get("money", 0) + _rw
    push_save_async()
    add_text(f"✅ 任务奖励 +{_rw} 金币")
    return True, f"+{tdef['reward']} 金币"

SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "mouse_sens": 0.0022, "master_vol": 0.8, "sfx_vol": 1.0, "music_vol": 0.5,
    "fps_cap": 60, "fog_quality": 1.0, "show_fps": True, "show_minimap": True,
    "sync_rate": 0.15,
    "keys": {"up": "w", "down": "s", "left": "a", "right": "d",
             "sprint": "shift", "shoot": "space", "reload": "r",
             "med": "q", "use": "e", "flash": "f", "shop": "b",
             "chat": "return", "back": "escape"}}
SETTINGS = json.loads(json.dumps(DEFAULT_SETTINGS))
SETTINGS_OPEN = False
SETTINGS_TAB = "general"
SETTINGS_REBIND = None
SETTINGS_MSG = ""
SETTINGS_MSG_TIME = 0.0

def load_settings():
    global SETTINGS
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in data:
                    data[k] = v
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        if kk not in data[k]:
                            data[k][kk] = vv
            SETTINGS = data
            apply_settings()
    except Exception as e:
        print(f"[设置] 读取失败: {e}")

def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(SETTINGS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def apply_settings():
    global MOUSE_SENS
    MOUSE_SENS = SETTINGS.get("mouse_sens", 0.0022)

def get_setting(path, default=None):
    parts = path.split(".")
    d = SETTINGS
    try:
        for p in parts:
            d = d[p]
        return d
    except Exception:
        return default

def set_setting(path, value):
    parts = path.split(".")
    d = SETTINGS
    for p in parts[:-1]:
        d = d[p]
    d[parts[-1]] = value
    apply_settings()

def key_name_to_pygame(name):
    m = {"w": pygame.K_w, "a": pygame.K_a, "s": pygame.K_s, "d": pygame.K_d,
         "shift": pygame.K_LSHIFT, "space": pygame.K_SPACE, "r": pygame.K_r,
         "q": pygame.K_q, "e": pygame.K_e, "f": pygame.K_f, "b": pygame.K_b,
         "return": pygame.K_RETURN, "escape": pygame.K_ESCAPE,
         "1": pygame.K_1, "2": pygame.K_2, "3": pygame.K_3, "4": pygame.K_4,
         "tab": pygame.K_TAB}
    return m.get(name)

def pygame_key_to_name(key):
    inv = {pygame.K_w: "w", pygame.K_a: "a", pygame.K_s: "s", pygame.K_d: "d",
           pygame.K_LSHIFT: "shift", pygame.K_RSHIFT: "shift",
           pygame.K_SPACE: "space", pygame.K_r: "r", pygame.K_q: "q",
           pygame.K_e: "e", pygame.K_f: "f", pygame.K_b: "b",
           pygame.K_RETURN: "return", pygame.K_ESCAPE: "escape",
           pygame.K_1: "1", pygame.K_2: "2", pygame.K_3: "3", pygame.K_4: "4",
           pygame.K_TAB: "tab"}
    return inv.get(key)

def is_action_key(action, key):
    name = get_setting(f"keys.{action}")
    if not name:
        return False
    target = key_name_to_pygame(name)
    return target is not None and key == target

WEAPON_DEFS = {
    "pistol": {"name": "手枪", "icon": "🔫", "dmg": 25, "mag": 12,
               "reserve": 48, "fire_rate": 0.25, "spread": 0.03, "rays": 1,
               "reload": 1.0, "zoom": 1.0},
    "rifle": {"name": "步枪", "icon": "🎯", "dmg": 30, "mag": 30,
              "reserve": 90, "fire_rate": 0.12, "spread": 0.05, "rays": 1,
              "reload": 1.4, "zoom": 1.0},
    "shotgun": {"name": "霰弹枪", "icon": "💥", "dmg": 14, "mag": 6,
                "reserve": 30, "fire_rate": 0.8, "spread": 0.25, "rays": 8,
                "reload": 1.8, "zoom": 1.0},
    "sniper": {"name": "狙击枪", "icon": "🎯", "dmg": 120, "mag": 5,
               "reserve": 20, "fire_rate": 1.2, "spread": 0.005, "rays": 1,
               "reload": 2.2, "zoom": 2.5},
}
WEAPON_ORDER = ["pistol", "rifle", "shotgun", "sniper"]

def get_current_weapon(p):
    wkey = p.get("current_weapon", "pistol")
    return WEAPON_DEFS.get(wkey, WEAPON_DEFS["pistol"]), \
           p["weapons"].get(wkey, {"mag": 0, "reserve": 0})

ACHIEVEMENTS_FILE = "achievements.json"
ACHIEVEMENT_DEFS = {
    "first_kill": ("首杀", "击杀第一个敌人", "🎯", False),
    "kill_10": ("十人斩", "累计击杀 10 名敌人", "🗡", False),
    "kill_boss": ("BOSS终结者", "击杀重装Boss", "💀", False),
    "extract_first": ("活着回来", "首次成功撤离", "🚁", False),
    "gold_1": ("金色传说", "第一次拿到金罐头", "🥇", False),
    "medic": ("战地医生", "使用 20 个医疗包", "💊", False),
    "weapon_master": ("武器大师", "解锁全部 4 把武器", "🔫", False),
    "sniper_kill": ("神枪手", "用狙击枪击杀 5 名敌人", "🎯", False),
    "survivor": ("绝境求生", "以低于 10 点生命值成功撤离", "❤️", False),
    "no_damage": ("完美行动", "整局未受伤成功撤离", "🛡", False),
}

def default_achievements():
    return {"unlocked": {}, "stats": {"total_kills": 0, "total_boss_kills": 0,
            "total_extracts": 0, "total_gold_cans": 0, "total_meds_used": 0,
            "night_extracts": 0, "max_money": 0, "games_played": 0,
            "sniper_kills": 0}}

ACHIEVEMENTS = default_achievements()
ACHIEVEMENT_POPUPS = []
ACHIEVEMENT_OPEN = False

def load_achievements():
    global ACHIEVEMENTS
    try:
        if os.path.exists(ACHIEVEMENTS_FILE):
            with open(ACHIEVEMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = default_achievements()
            base["unlocked"] = data.get("unlocked", {})
            for k in base["stats"]:
                base["stats"][k] = data.get("stats", {}).get(k, 0)
            ACHIEVEMENTS = base
    except Exception:
        pass

def save_achievements():
    try:
        with open(ACHIEVEMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(ACHIEVEMENTS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def unlock_achievement(aid):
    if aid not in ACHIEVEMENT_DEFS:
        return
    if aid in ACHIEVEMENTS["unlocked"]:
        return
    ACHIEVEMENTS["unlocked"][aid] = time.time()
    name, desc, icon, _ = ACHIEVEMENT_DEFS[aid]
    ACHIEVEMENT_POPUPS.append({"name": name, "icon": icon, "desc": desc, "time": 4.0})
    save_achievements()

def check_achievements():
    s = ACHIEVEMENTS["stats"]
    if s["total_kills"] >= 1: unlock_achievement("first_kill")
    if s["total_kills"] >= 10: unlock_achievement("kill_10")
    if s["total_boss_kills"] >= 1: unlock_achievement("kill_boss")
    if s["total_extracts"] >= 1: unlock_achievement("extract_first")
    if s["total_gold_cans"] >= 1: unlock_achievement("gold_1")
    if s["total_meds_used"] >= 20: unlock_achievement("medic")
    if s.get("sniper_kills", 0) >= 5: unlock_achievement("sniper_kill")

def update_achievement_popups(dt):
    for p in ACHIEVEMENT_POPUPS[:]:
        p["time"] -= dt
        if p["time"] <= 0:
            ACHIEVEMENT_POPUPS.remove(p)

REPLAY_DIR = "replays"
if not os.path.isdir(REPLAY_DIR):
    os.makedirs(REPLAY_DIR, exist_ok=True)
CURRENT_REPLAY = None
REPLAY_PLAYBACK = None
REPLAY_PLAYBACK_IDX = 0
REPLAY_PLAYBACK_TIME = 0.0
REPLAY_SPEED = 1.0
REPLAY_PANEL_OPEN = False
REPLAY_LIST = []
REPLAY_LIST_PAGE = 0
REPLAY_LIST_PER_PAGE = 8
_replay_acc = [0.0]


def draw_achievement_popups(screen):
    y = 100
    for p in ACHIEVEMENT_POPUPS[:4]:
        w, h = 340, 70
        x = WIDTH - w - 20
        rect = pygame.Rect(x, y, w, h)
        alpha = 255
        if p["time"] > 3.5:
            alpha = int(255 * (4.0 - p["time"]) / 0.5)
        elif p["time"] < 0.5:
            alpha = int(255 * p["time"] / 0.5)
        alpha = max(0, min(255, alpha))
        s2 = pygame.Surface((w, h), pygame.SRCALPHA)
        s2.fill((20, 25, 35, int(alpha * 0.95)))
        pygame.draw.rect(s2, (255, 215, 100, alpha), s2.get_rect(), 2, border_radius=10)
        screen.blit(s2, rect.topleft)
        draw_text(screen, p["icon"], 40, (255, 255, 255), topleft=(x + 15, y + 12))
        draw_text(screen, "🏅 成就解锁！", 14, (255, 215, 100), topleft=(x + 75, y + 8))
        draw_text(screen, p["name"], 22, (255, 255, 255), topleft=(x + 75, y + 26))
        draw_text(screen, p["desc"], 12, (180, 190, 210), topleft=(x + 75, y + 50))
        y += h + 10

def start_recording(game, my_id):
    global CURRENT_REPLAY
    CURRENT_REPLAY = {"user": my_id, "map_idx": CURRENT_MAP_IDX, "is_night": IS_NIGHT,
                      "start_time": time.time(), "frames": [], "events": []}
    _replay_acc[0] = 0.0

def record_frame(game, my_id, dt):
    global CURRENT_REPLAY
    if CURRENT_REPLAY is None:
        return
    _replay_acc[0] += dt
    if _replay_acc[0] < 0.1:
        return
    _replay_acc[0] = 0.0
    frame = {"t": round(time.time() - CURRENT_REPLAY["start_time"], 2),
             "players": [{"id": pid, "x": round(p["x"], 1), "y": round(p["y"], 1),
                          "a": round(p["a"], 2), "hp": p["hp"]}
                         for pid, p in game["players"].items()],
             "enemies": [{"x": round(e["x"], 1), "y": round(e["y"], 1),
                          "hp": e["hp"], "type": e.get("type", "rusher")}
                         for e in game["enemies"]],
             "loots": [{"id": lid, "x": l["x"], "y": l["y"], "k": l["k"]}
                       for lid, l in game["loots"].items()]}
    CURRENT_REPLAY["frames"].append(frame)

def stop_recording(result="win", gained=0):
    global CURRENT_REPLAY
    if CURRENT_REPLAY is None:
        return
    CURRENT_REPLAY["result"] = result
    CURRENT_REPLAY["gained"] = gained
    CURRENT_REPLAY["duration"] = time.time() - CURRENT_REPLAY["start_time"]
    fname = f"{CURRENT_REPLAY['user']}_{int(CURRENT_REPLAY['start_time'])}.bbz"
    try:
        with open(os.path.join(REPLAY_DIR, fname), "w", encoding="utf-8") as f:
            json.dump(CURRENT_REPLAY, f, ensure_ascii=False)
    except Exception:
        pass
    CURRENT_REPLAY = None

def list_replays():
    global REPLAY_LIST
    REPLAY_LIST = []
    try:
        for f in sorted(os.listdir(REPLAY_DIR), reverse=True):
            if not f.endswith(".bbz"):
                continue
            path = os.path.join(REPLAY_DIR, f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                REPLAY_LIST.append({"file": f, "path": path,
                                    "user": data.get("user", "?"),
                                    "map_idx": data.get("map_idx", 0),
                                    "is_night": data.get("is_night", False),
                                    "result": data.get("result", "?"),
                                    "duration": data.get("duration", 0),
                                    "frames": len(data.get("frames", [])),
                                    "gained": data.get("gained", 0)})
            except Exception:
                pass
    except Exception:
        pass

def start_playback(path):
    global REPLAY_PLAYBACK, REPLAY_PLAYBACK_IDX, REPLAY_PLAYBACK_TIME
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False
    REPLAY_PLAYBACK = data
    REPLAY_PLAYBACK_IDX = 0
    REPLAY_PLAYBACK_TIME = 0.0
    return True

def delete_replay(path):
    try:
        os.remove(path)
        list_replays()
        return True
    except Exception:
        return False

def update_playback(dt):
    global REPLAY_PLAYBACK_IDX, REPLAY_PLAYBACK_TIME
    if REPLAY_PLAYBACK is None:
        return
    frames = REPLAY_PLAYBACK.get("frames", [])
    if not frames:
        return
    REPLAY_PLAYBACK_TIME += dt * REPLAY_SPEED
    while REPLAY_PLAYBACK_IDX < len(frames) - 1:
        nxt = frames[REPLAY_PLAYBACK_IDX + 1]
        if nxt.get("t", 0) <= REPLAY_PLAYBACK_TIME:
            REPLAY_PLAYBACK_IDX += 1
        else:
            break

FRIENDS_FILE = "friends.json"
FRIENDS = {"list": []}
FRIENDS_OPEN = False
FRIEND_INPUT = ""
FRIEND_FOCUS = False

def load_friends():
    global FRIENDS
    try:
        if os.path.exists(FRIENDS_FILE):
            with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
                FRIENDS = json.load(f)
    except Exception:
        pass

def save_friends():
    try:
        with open(FRIENDS_FILE, "w", encoding="utf-8") as f:
            json.dump(FRIENDS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

VIEW = {"a": 0.0}
FLASH_ON = False
FLASH_BATTERY = 100.0
FLASH_BATTERY_MAX = 100.0
FLASH_DRAIN_RATE = 4.0
FLASH_CONE_ANGLE = math.radians(35)
FLASH_CONE_INNER = 0.6

BACKPACK_OPEN = False
GOD_MENU_OPEN = False
SHOP_VIP_OPEN = False
SHOP_VIP_SELECTED = "month"
SHOP_VIP_RECTS = {}
GOD_MENU_RECTS = {}
MORE_MENU_OPEN = False
IS_VIP = False
VIP_LEVEL = 0
VIP_EXPIRE = 0
ITEM_META = {
    "ammo": {"name": "弹药", "icon": "🔸", "stack": 120},
    "medkit": {"name": "医疗包", "icon": "💊", "stack": 5},
    "can": {"name": "罐头", "icon": "🥫", "stack": 5},
    "gold": {"name": "金罐头", "icon": "🥇", "stack": 3},
    "key": {"name": "钥匙", "icon": "🔑", "stack": 1},
    "battery": {"name": "电池", "icon": "🔋", "stack": 3},
}

canvas = None
MENU_BG = None
SND = {}
FEED = {"hp": None, "cans": None, "ammo": None, "med": None, "ehp": None,
        "ecnt": None, "res": "play", "rl": False, "texts": [], "hit": 0.0,
        "dmg": 0.0, "muzzle": 0.0, "bob": 0.0}

IS_VIP = False          # 当前账号是否 VIP
VIP_LEVEL = 0
VIP_EXPIRE = 0
LOGIN_USER = None
LOGIN_PASS = ""
login_user_text = ""
login_pass_text = ""
login_focus = "user"
login_msg = ""
ALERT_MSG = ""
ALERT_TIME = 0.0
HELP_OPEN = False
SHOP_OPEN = False
mode = "menu"
MERCHANT_OPEN = False

CURRENT_GAME = {"solo": None, "multi": None}
SHOP_ITEMS = [
    {"key": "ammo", "name": "弹药 x15", "price": 50, "desc": "所有武器备弹 +15"},
    {"key": "med", "name": "医疗包 x1", "price": 100, "desc": "治疗包 +1"},
    {"key": "armor", "name": "护甲 +50", "price": 200, "desc": "最大生命 +50"},
    {"key": "dmg", "name": "伤害 +5", "price": 300, "desc": "所有武器伤害 +5"},
    {"key": "key", "name": "万能钥匙", "price": 500, "desc": "可以打开门"},
    {"key": "gold", "name": "金罐头 x1", "price": 1000, "desc": "价值 300 金币"},
]

SYNC_RUNNING = False
LAST_SYNC_TIME = 0
SYNC_INTERVAL = 0.15
MULTIPLAYER_MODE = False
MULTIPLAYER_GAME = None
CURRENT_ROOM_ID = None
REQUEST_WORKER_RUNNING = False

REMOTE_SMOOTH = {}
REMOTE_SMOOTH_LOCK = threading.Lock()
CACHED_REMOTE_PLAYERS = {}
CACHED_REMOTE_PLAYERS_LOCK = threading.Lock()
CACHED_ROOM_STATUS = {"success": True, "status": "waiting", "host": None,
                      "players": [], "player_count": 0, "max_players": 10}
CACHED_ROOM_STATUS_LOCK = threading.Lock()
CACHED_ROOM_LIST = {}
CACHED_ROOM_LIST_LOCK = threading.Lock()

SHOW_ROOM_LIST = False
SHOW_CREATE_ROOM = False
CREATE_ROOM_NAME = ""
CREATE_ROOM_PASSWORD = ""
CREATE_ROOM_MAP = 0
CREATE_ROOM_NIGHT = False
ROOM_LIST_PAGE = 0
ROOM_LIST_MAX_PER_PAGE = 5
CREATE_FOCUS = "name"

CHAT_MESSAGES = []
CHAT_INPUT = ""
CHAT_FOCUS = False
CHAT_HAS_NEW_MESSAGE = False
CHAT_DISPLAYED_MESSAGES = set()
CHAT_MENU_RECTS = {"panel": None, "input": None, "send": None}
CHAT_GAME_RECTS = {"panel": None, "input": None, "send": None}

WS_APP = None
WS_CONNECTED = False
WS_LOCK = threading.Lock()
WS_RECONNECT_RUNNING = False

KEY_STATE = {"w": False, "a": False, "s": False, "d": False,
             "shift": False, "space": False, "r": False, "e": False, "q": False}

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
        global SAVE, IS_VIP, VIP_LEVEL, VIP_EXPIRE
        SAVE["money"] = res.get("money", 0)
        SAVE["armor"] = res.get("armor", 0)
        SAVE["dmg"] = res.get("dmg", 0)
        SAVE["ammo"] = res.get("ammo", 0)
        SAVE["tasks"] = res.get("tasks", {"kill": 0, "collect": 0, "extract": 0})
        IS_VIP = bool(res.get("is_vip", False))
        VIP_LEVEL = int(res.get("vip_level", 0))
        VIP_EXPIRE = int(res.get("vip_expire", 0))
    return res

def push_save():
    global LOGIN_USER
    if not LOGIN_USER:
        return False
    payload = {"user": LOGIN_USER, "money": SAVE.get("money", 0),
               "armor": SAVE.get("armor", 0), "dmg": SAVE.get("dmg", 0),
               "ammo": SAVE.get("ammo", 0), "tasks": SAVE.get("tasks", {})}
    res = http_post("/api/save", payload)
    return bool(res and res.get("success"))

def push_save_async():
    threading.Thread(target=push_save, daemon=True).start()

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
    if len(CHAT_MESSAGES) > 50:
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
    if data.get("type") == "room_state":
        players = data.get("players", [])
        remote = {}
        for p in players:
            if p.get("name") != LOGIN_USER:
                remote[p.get("name")] = {
                    'x': p.get('x', 0), 'y': p.get('y', 0),
                    'angle': p.get('angle', 0), 'hp': p.get('hp', 100),
                    'reload': p.get('reload', False),
                    'shoot': p.get('shoot', False),
                    'sprint': p.get('sprint', False)}
        with CACHED_REMOTE_PLAYERS_LOCK:
            CACHED_REMOTE_PLAYERS.clear()
            CACHED_REMOTE_PLAYERS.update(remote)
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
    WS_APP = websocket.WebSocketApp(url, on_message=_ws_on_message,
                                     on_error=_ws_on_error,
                                     on_close=_ws_on_close, on_open=_ws_on_open)
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

def smooth_remote_players(dt):
    with CACHED_REMOTE_PLAYERS_LOCK:
        target = CACHED_REMOTE_PLAYERS.copy()
    with REMOTE_SMOOTH_LOCK:
        for name in list(REMOTE_SMOOTH.keys()):
            if name not in target:
                del REMOTE_SMOOTH[name]
        for name, t in target.items():
            if name not in REMOTE_SMOOTH:
                REMOTE_SMOOTH[name] = {
                    "x": t["x"], "y": t["y"], "a": t.get("angle", 0), "hp": t.get("hp", 100),
                    "tx": t["x"], "ty": t["y"], "ta": t.get("angle", 0), "thp": t.get("hp", 100),
                    "reload": False, "shoot": False, "sprint": False}
            s = REMOTE_SMOOTH[name]
            s["tx"] = t["x"]; s["ty"] = t["y"]
            s["ta"] = t.get("angle", 0); s["thp"] = t.get("hp", 100)
            s["reload"] = t.get("reload", False)
            s["shoot"] = t.get("shoot", False)
            s["sprint"] = t.get("sprint", False)
        lerp = min(1.0, dt * 8.0)
        for name, s in REMOTE_SMOOTH.items():
            s["x"] += (s["tx"] - s["x"]) * lerp
            s["y"] += (s["ty"] - s["y"]) * lerp
            s["hp"] += (s["thp"] - s["hp"]) * lerp
            da = (s["ta"] - s["a"])
            while da > math.pi: da -= math.pi * 2
            while da < -math.pi: da += math.pi * 2
            s["a"] += da * lerp

def get_smoothed_remote():
    with REMOTE_SMOOTH_LOCK:
        return {k: dict(v) for k, v in REMOTE_SMOOTH.items()}

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
    payload = {"name": room_name, "password": password, "host": host,
               "map_idx": map_idx, "is_night": is_night, "max_players": max_players,
               "host_hp": maxhp, "host_res": 120 + sv.get("ammo", 0) * 60,
               "host_dmg": 25 + sv.get("dmg", 0) * 10}
    res = http_post("/api/room/create", payload)
    if res is None:
        return {"success": False, "message": "服务器连接失败"}
    return res

def join_room(room_id, user, password=""):
    sv = SAVE
    maxhp = 100 + sv.get("armor", 0) * 50
    payload = {"room_id": room_id, "user": user, "password": password,
               "hp": maxhp, "res": 120 + sv.get("ammo", 0) * 60,
               "dmg": 25 + sv.get("dmg", 0) * 10}
    res = http_post("/api/room/join", payload)
    if res is None:
        return {"success": False, "message": "服务器连接失败"}
    return res

def leave_room(room_id, user):
    res = http_post("/api/room/leave", {"room_id": room_id, "user": user})
    return res or {"success": False}

def leave_room_async(room_id, user):
    threading.Thread(target=leave_room, args=(room_id, user), daemon=True).start()

def update_room_player(room_id, user, x, y, angle, hp, reload=False, shoot=False, sprint=False):
    http_post("/api/room/update", {"room_id": room_id, "user": user,
                                    "x": x, "y": y, "angle": angle, "hp": hp,
                                    "reload": reload, "shoot": shoot, "sprint": sprint})

def update_room_player_async(room_id, user, x, y, angle, hp, reload=False, shoot=False, sprint=False):
    threading.Thread(target=update_room_player,
                     args=(room_id, user, x, y, angle, hp, reload, shoot, sprint),
                     daemon=True).start()

def get_room_info(room_id):
    res = http_get(f"/api/room/{room_id}")
    if res and res.get("success"):
        return res.get("room")
    return None

def get_cached_room_status():
    with CACHED_ROOM_STATUS_LOCK:
        return CACHED_ROOM_STATUS.copy()

def join_room_success(room_id, room):
    global MULTIPLAYER_MODE, MULTIPLAYER_GAME, mode
    global CURRENT_ROOM_ID, SHOW_ROOM_LIST, SHOW_CREATE_ROOM
    if not LOGIN_USER:
        return
    CURRENT_ROOM_ID = room_id
    players = room.get("players", [])
    player_names = [p.get("name") for p in players]
    MULTIPLAYER_MODE = True
    with CACHED_REMOTE_PLAYERS_LOCK:
        CACHED_REMOTE_PLAYERS.clear()
    with REMOTE_SMOOTH_LOCK:
        REMOTE_SMOOTH.clear()
    map_idx = room.get("map_idx", 0)
    is_night = room.get("is_night", False)
    apply_config(map_idx, is_night)
    MULTIPLAYER_GAME = new_game(player_names, map_idx)
    CURRENT_GAME["multi"] = MULTIPLAYER_GAME
    start_recording(MULTIPLAYER_GAME, LOGIN_USER)
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
                            "player_count": len(players),
                            "max_players": room.get("max_players", 10)}
                    with CACHED_ROOM_STATUS_LOCK:
                        CACHED_ROOM_STATUS = data
                    if not WS_CONNECTED:
                        remote = {}
                        for p in players:
                            if p.get("name") != LOGIN_USER:
                                remote[p.get("name")] = {
                                    'x': p.get('x', 0), 'y': p.get('y', 0),
                                    'angle': p.get('angle', 0), 'hp': p.get('hp', 100),
                                    'reload': p.get('reload', False),
                                    'shoot': p.get('shoot', False),
                                    'sprint': p.get('sprint', False)}
                        with CACHED_REMOTE_PLAYERS_LOCK:
                            CACHED_REMOTE_PLAYERS.clear()
                            CACHED_REMOTE_PLAYERS.update(remote)
            time.sleep(0.5)
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

def do_register():
    global login_msg, login_user_text, login_pass_text
    user = login_user_text.strip()
    password = login_pass_text.strip()
    if not user:
        login_msg = "请输入用户名"; return
    if not password or len(password) < 6:
        login_msg = "密码至少6位"; return
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
        login_msg = "请输入用户名和密码"; return
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
        load_daily_tasks_from_server()
    else:
        login_msg = result.get('message', "登录失败") if result else "网络错误"

def do_logout():
    global LOGIN_USER, LOGIN_PASS, login_msg, MULTIPLAYER_MODE, MULTIPLAYER_GAME, CURRENT_ROOM_ID, mode, CHAT_FOCUS
    global IS_VIP, VIP_LEVEL, VIP_EXPIRE
    if LOGIN_USER:
        if MULTIPLAYER_MODE and CURRENT_ROOM_ID:
            leave_room_async(CURRENT_ROOM_ID, LOGIN_USER)
        push_save_async()
        stop_php_sync()
        stop_websocket()
        stop_ws_reconnect()
    LOGIN_USER = None
    LOGIN_PASS = ""
    IS_VIP = False
    VIP_LEVEL = 0
    VIP_EXPIRE = 0
    login_msg = "已退出登录"
    MULTIPLAYER_MODE = False
    MULTIPLAYER_GAME = None
    CHAT_MESSAGES.clear()
    CHAT_DISPLAYED_MESSAGES.clear()
    CURRENT_ROOM_ID = None
    CHAT_FOCUS = False
    with CACHED_ROOM_STATUS_LOCK:
        CACHED_ROOM_STATUS = {"success": True, "status": "waiting", "host": None,
                              "players": [], "player_count": 0, "max_players": 10}
    with CACHED_REMOTE_PLAYERS_LOCK:
        CACHED_REMOTE_PLAYERS.clear()
    with REMOTE_SMOOTH_LOCK:
        REMOTE_SMOOTH.clear()
    mode = "menu"

_FONT_CACHE = {}
def get_chinese_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font_paths = ["/system/fonts/NotoSansCJK-Regular.ttc",
                  "/system/fonts/DroidSansFallback.ttf",
                  "C:/Windows/Fonts/simhei.ttf",
                  "C:/Windows/Fonts/msyh.ttc"]
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

def shade(color):
    return tuple(int(c * 0.6) for c in color)

def reset_feed():
    global FEED
    FEED.update({"hp": None, "cans": None, "ammo": None, "med": None, "ehp": None,
                 "ecnt": None, "res": "play", "rl": False, "texts": [],
                 "hit": 0.0, "dmg": 0.0, "muzzle": 0.0, "bob": 0.0})

def add_text(txt):
    FEED["texts"].append([txt, 2.0])

def play(sound_key):
    if sound_key in SND:
        try:
            SND[sound_key].set_volume(SETTINGS.get("sfx_vol", 1.0) * SETTINGS.get("master_vol", 1.0))
            SND[sound_key].play()
        except Exception:
            pass

def resource_path(relative):
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, relative)

def make_ui_assets():
    global MENU_BG
    print("[封面] MEIPASS:", getattr(sys, "_MEIPASS", "无"))
    print("[封面] 当前目录:", os.path.abspath("."))
    candidates = ["menu_bg.jpg", "menu_bg.png", "menu_bg.jpeg"]
    loaded = False
    for name in candidates:
        p = resource_path(name)
        print(f"[封面] 尝试: {p}, 存在: {os.path.exists(p)}")
        if os.path.exists(p):
            try:
                img = pygame.image.load(p)
                if img.get_alpha() is not None:
                    img = img.convert_alpha()
                else:
                    img = img.convert()
                iw, ih = img.get_size()
                scale = max(WIDTH / iw, HEIGHT / ih)
                nw, nh = int(iw * scale), int(ih * scale)
                img = pygame.transform.smoothscale(img, (nw, nh))
                MENU_BG = pygame.Surface((WIDTH, HEIGHT))
                MENU_BG.fill((15, 18, 22))
                MENU_BG.blit(img, ((WIDTH - nw) // 2, (HEIGHT - nh) // 2))
                dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                dark.fill((0, 0, 0, 110))
                MENU_BG.blit(dark, (0, 0))
                loaded = True
                print(f"[封面] 加载成功: {p} 尺寸 {img.get_size()}")
                break
            except Exception as e:
                print(f"[封面] 加载失败: {p} 错误 {e}")
    if not loaded:
        print("[封面] 未找到任何图片，使用渐变背景")
        MENU_BG = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / HEIGHT
            c = tuple(int(15 + 20 * t) for _ in range(3))
            pygame.draw.line(MENU_BG, c, (0, y), (WIDTH, y))

def make_sounds():
    global SND
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    except Exception:
        return
    try:
        import numpy as np
    except Exception:
        return

    def tone(freq, ms, vol=0.35, decay=True):
        n = int(22050 * ms / 1000.0)
        if n <= 0:
            n = 1
        t = np.linspace(0, ms / 1000.0, n, False)
        wave = np.sin(freq * 2 * np.pi * t)
        if decay:
            wave *= np.linspace(1.0, 0.0, n)
        wave = (wave * vol * 32767).astype(np.int16)
        try:
            return pygame.sndarray.make_sound(wave)
        except Exception:
            return None

    try:
        SND["shoot"]  = tone(880, 60, 0.30)
        SND["hit"]    = tone(520, 50, 0.35)
        SND["die"]    = tone(220, 200, 0.40)
        SND["hurt"]   = tone(160, 150, 0.40)
        SND["pick"]   = tone(1200, 40, 0.25)
        SND["reload"] = tone(400, 90, 0.25)
        SND["win"]    = tone(660, 260, 0.35)
        SND["lose"]   = tone(180, 320, 0.35)
        SND["buy"]    = tone(1000, 70, 0.25)
        SND = {k: v for k, v in SND.items() if v is not None}
    except Exception:
        SND.clear()

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

def inv_total(p):
    total = 0
    for k, n in p["inventory"].items():
        if n <= 0:
            continue
        stack = ITEM_META.get(k, {}).get("stack", 1)
        total += math.ceil(n / stack)
    return total

def inv_add(p, kind, amount=1):
    meta = ITEM_META.get(kind)
    if not meta:
        return False
    stack = meta["stack"]
    cur = p["inventory"].get(kind, 0)
    new_slots = math.ceil((cur + amount) / stack)
    old_slots = math.ceil(cur / stack) if cur > 0 else 0
    if inv_total(p) + (new_slots - old_slots) > p["inv_max"]:
        add_text("🎒 背包已满！")
        return False
    p["inventory"][kind] = cur + amount
    return True

def inv_use(p, kind):
    if p["inventory"].get(kind, 0) <= 0:
        add_text(f"没有 {ITEM_META[kind]['name']}")
        return False
    global FLASH_BATTERY
    if kind == "medkit":
        if p["hp"] >= p["maxhp"]:
            add_text("生命值已满"); return False
        p["hp"] = min(p["maxhp"], p["hp"] + 35)
        p["inventory"]["medkit"] -= 1
        ACHIEVEMENTS["stats"]["total_meds_used"] += 1
        add_text("+35 生命")
        play("pick")
        return True
    elif kind == "battery":
        FLASH_BATTERY = min(FLASH_BATTERY_MAX, FLASH_BATTERY + 50)
        p["inventory"]["battery"] -= 1
        add_text("🔋 +50% 电量")
        play("pick")
        return True
    return False

SHOP_CLICK_FLAG = {"pressed": False}

def buy_shop_item(item_key, price):
    global SAVE
    if SAVE.get("money", 0) < price:
        add_text("金币不足！"); return False
    p = None
    if mode == "solo":
        g = CURRENT_GAME.get("solo")
        if g:
            p = g["players"].get(0)
    elif mode == "multiplayer":
        g = CURRENT_GAME.get("multi")
        if g and LOGIN_USER:
            p = g["players"].get(LOGIN_USER)
    if not p:
        add_text("找不到玩家"); return False
    SAVE["money"] -= price
    if item_key == "ammo":
        for wk in p["weapons"]:
            p["weapons"][wk]["reserve"] += 15
        add_text("+15 弹药（所有武器）")
    elif item_key == "med":
        p["inventory"]["medkit"] = p["inventory"].get("medkit", 0) + 1
        add_text("+1 医疗包")
    elif item_key == "armor":
        p["maxhp"] += 50; p["hp"] += 50; add_text("+50 最大生命")
    elif item_key == "dmg":
        p["dmg"] += 5; add_text("+5 伤害")
    elif item_key == "key":
        p["key"] = 1; add_text("获得万能钥匙")
    elif item_key == "gold":
        p["gold"] += 1; add_text("+1 金罐头")
    play("buy")
    push_save_async()
    return True

def draw_shop(screen, me):
    draw_overlay(screen, 200)
    panel = pygame.Rect(WIDTH // 2 - 320, HEIGHT // 2 - 260, 640, 520)
    draw_panel(screen, panel, alpha=245, border=(255, 215, 0), radius=15)
    draw_text(screen, "战场商店", 44, (255, 215, 0), center=(WIDTH // 2, HEIGHT // 2 - 220))
    draw_text(screen, f"你的金币：{SAVE.get('money', 0)}", 26, (255, 255, 255), center=(WIDTH // 2, HEIGHT // 2 - 170))
    mp = pygame.mouse.get_pos()
    mpress = pygame.mouse.get_pressed()[0]
    for i, item in enumerate(SHOP_ITEMS):
        y = HEIGHT // 2 - 110 + i * 62
        rect = pygame.Rect(WIDTH // 2 - 290, y, 580, 52)
        can_buy = SAVE.get("money", 0) >= item["price"]
        hover = rect.collidepoint(mp)
        color = (60, 130, 90) if hover and can_buy else ((40, 100, 60) if can_buy else (70, 40, 40))
        pygame.draw.rect(screen, color, rect, border_radius=8)
        pygame.draw.rect(screen, (120, 220, 150) if can_buy else (150, 90, 90), rect, 2, border_radius=8)
        draw_text(screen, item["name"], 26, (255, 255, 255), topleft=(rect.x + 20, rect.y + 12))
        draw_text(screen, item["desc"], 18, (180, 190, 210), topleft=(rect.x + 200, rect.y + 18))
        draw_text(screen, f"{item['price']} 币", 22, (255, 215, 95) if can_buy else (150, 120, 120),
                  topleft=(rect.right - 110, rect.y + 14))
        if hover and mpress and can_buy and not SHOP_CLICK_FLAG["pressed"]:
            buy_shop_item(item["key"], item["price"])
            SHOP_CLICK_FLAG["pressed"] = True
    if not mpress:
        SHOP_CLICK_FLAG["pressed"] = False
    draw_text(screen, "按 B 关闭商店", 18, (150, 160, 180), center=(WIDTH // 2, HEIGHT // 2 + 230))

def draw_backpack(screen, me):
    if not BACKPACK_OPEN:
        return
    draw_overlay(screen, 220)
    panel = pygame.Rect(WIDTH // 2 - 420, HEIGHT // 2 - 280, 840, 560)
    draw_panel(screen, panel, alpha=245, border=(180, 220, 100), radius=15)
    draw_text(screen, "🎒 背包", 40, (180, 220, 100), center=(WIDTH // 2, panel.y + 40))
    used = inv_total(me)
    draw_text(screen, f"容量 {used} / {me['inv_max']}", 20, (200, 200, 200), center=(WIDTH // 2, panel.y + 78))
    bar = pygame.Rect(panel.centerx - 200, panel.y + 100, 400, 10)
    color = (180, 220, 100) if used < me["inv_max"] else (255, 90, 90)
    draw_bar(screen, bar, used / max(1, me["inv_max"]), color)
    y = panel.y + 140
    x = panel.x + 40
    bw = 360
    for k, meta in ITEM_META.items():
        n = me["inventory"].get(k, 0)
        if n <= 0 and k not in ("ammo", "medkit"):
            continue
        rect = pygame.Rect(x, y, bw, 60)
        pygame.draw.rect(screen, (30, 40, 55), rect, border_radius=10)
        pygame.draw.rect(screen, (120, 140, 100), rect, 2, border_radius=10)
        draw_text(screen, meta["icon"], 32, (255, 255, 255), topleft=(x + 15, y + 12))
        draw_text(screen, meta["name"], 22, (255, 255, 255), topleft=(x + 65, y + 8))
        draw_text(screen, f"× {n}", 20, (200, 220, 150), topleft=(x + 65, y + 32))
        if k in ("medkit", "battery") and n > 0:
            ub = pygame.Rect(x + bw - 100, y + 12, 80, 36)
            draw_button(screen, ub, "使用", small=True)
            if ub.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
                inv_use(me, k)
        y += 70
        if y > panel.bottom - 80:
            y = panel.y + 140
            x += bw + 30
            if x > panel.right - bw:
                break
    draw_text(screen, "TAB 关闭", 16, (150, 160, 175), center=(WIDTH // 2, panel.bottom - 12))

def draw_button(screen, rect, text, small=False):
    h = rect.collidepoint(pygame.mouse.get_pos())
    s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(s, (52, 60, 76, 235) if h else (34, 40, 52, 210), s.get_rect(), border_radius=12)
    screen.blit(s, rect.topleft)
    pygame.draw.rect(screen, (255, 190, 80) if h else (90, 100, 120), rect, 2, border_radius=12)
    draw_text(screen, text, 22 if small else 30, (255, 255, 255) if h else (210, 215, 225), center=rect.center)

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
               (1400,1000,"medkit"),(1450,300,"key"),(1600,250,"can"),(1560,250,"medkit"),(1640,250,"gold"),
               (500,800,"battery"),(2000,700,"battery"),
               (500, 700, "weapon_rifle"), (2200, 1300, "weapon_shotgun")]},
    {"name": "罐头港口", "w": 2000, "h": 2000,
     "walls": [(0,0,2000,20),(0,1980,2000,20),(0,0,20,2000),(1980,0,20,2000),
               (400,400,600,40),(400,400,40,200),(1200,800,40,400),(1200,800,300,40),
               (300,1200,200,40),(1500,1400,300,40),(800,1600,40,300),(1800,600,40,200)],
     "doors": [(800, 400, 40, 60)],
     "extract": (1700, 1700, 200, 200),
     "spawns": [(300,300),(300,500),(500,300),(500,500)],
     "enemies": [(1000,1000),(1200,1200),(800,600),(600,800),(1400,1400),(1600,1600),(400,1800),(1800,400)],
     "loots": [(800,800,"can"),(1000,1000,"can"),(1200,1200,"can"),(1400,1400,"ammo"),(1600,1600,"medkit"),
               (600,600,"key"),(800,1000,"gold"),(1000,800,"can"),(1200,1400,"ammo"),(1400,1200,"medkit"),
               (500,900,"battery"),(1500,500,"battery"),
               (1700, 300, "weapon_sniper"), (300, 1700, "weapon_shotgun")]}
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
LOOT_COLORS = {"can": (255,180,50), "ammo": (200,200,80), "medkit": (80,220,80),
               "key": (200,200,255), "gold": (255,215,0), "battery": (255,255,120),
               "weapon_pistol": (180,180,180), "weapon_rifle": (100,200,100),
               "weapon_shotgun": (255,120,50), "weapon_sniper": (200,100,255)}

ENEMY_TYPES = {
    "rusher": {"name": "冲锋兵", "hp": 45, "sp": 240, "dmg": 12,
               "fire_rate": 0.5, "prefer_cover": False, "shoot_dist": 220,
               "color": {"H": (220, 80, 80), "U": (180, 60, 60), "G": (120, 40, 40), "L": (150, 70, 70), "D": (90, 40, 40)}},
    "sniper": {"name": "狙击手", "hp": 55, "sp": 100, "dmg": 28,
               "fire_rate": 2.2, "prefer_cover": True, "shoot_dist": 800,
               "color": {"H": (170, 100, 220), "U": (140, 80, 190), "G": (80, 40, 120), "L": (100, 60, 150), "D": (60, 30, 90)}},
    "thrower": {"name": "投掷手", "hp": 70, "sp": 130, "dmg": 0,
                "fire_rate": 2.5, "prefer_cover": True, "shoot_dist": 420,
                "color": {"H": (100, 210, 110), "U": (80, 170, 80), "G": (40, 110, 40), "L": (60, 140, 60), "D": (30, 80, 30)}},
    "boss": {"name": "重装Boss", "hp": 220, "sp": 0, "dmg": 14,
             "fire_rate": 0.7, "prefer_cover": False, "shoot_dist": 620,
             "color": {"H": (255, 40, 40), "U": (210, 20, 20), "G": (150, 10, 10), "L": (190, 30, 30), "D": (100, 10, 10)}},
}

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
    while d > math.pi: d -= math.pi * 2
    while d < -math.pi: d += math.pi * 2
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
        if t1 > t2: t1, t2 = t2, t1
        tmin, tmax = max(tmin, t1), min(tmax, t2)
        if tmin > tmax: return None
    if abs(dy) < 1e-9:
        if y < r.y or y > r.y + r.h:
            return None
    else:
        t1, t2 = (r.y - y) / dy, (r.y + r.h - y) / dy
        if t1 > t2: t1, t2 = t2, t1
        tmin, tmax = max(tmin, t1), min(tmax, t2)
        if tmin > tmax: return None
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
    zoom_factor = 0.66
    if state.get("zoom_active"):
        zoom_factor = 0.66 / state.get("zoom_level", 1.0)
    plane_x, plane_y = -dir_y * zoom_factor, dir_x * zoom_factor
    zbuf = []
    theme = THEMES["night" if IS_NIGHT else "day"]
    fog_dist = theme["fog_dist"] * SETTINGS.get("fog_quality", 1.0)
    ambient = theme["ambient"]
    flash_on = FLASH_ON and FLASH_BATTERY > 0
    if flash_on:
        fog_dist *= 1.1
        ambient = min(1.0, ambient + 0.15)
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
        if flash_on:
            cam_limit = min(1.5, math.tan(FLASH_CONE_ANGLE) / 0.66)
            if abs(cam_n) < cam_limit * FLASH_CONE_INNER:
                cone_factor = 1.0
            elif abs(cam_n) < cam_limit:
                t = (abs(cam_n) - cam_limit * FLASH_CONE_INNER) / (cam_limit * (1 - FLASH_CONE_INNER))
                cone_factor = 1.0 - 0.4 * t
            else:
                cone_factor = 0.35
            f = f * (0.4 + 0.6 * cone_factor)
        hx, hy = cx + rdx * dist, cy + rdy * dist
        tex = 0.88 + 0.12 * math.sin((hx + hy) * 0.12)
        r, g2, b = int(base[0] * f * tex), int(base[1] * f * tex), int(base[2] * f * tex)
        fog = min(1.0, dist / fog_dist)
        fog_c = theme["fog_color"]
        pygame.draw.line(surface,
            (int(r + (fog_c[0] - r) * fog), int(g2 + (fog_c[1] - g2) * fog), int(b + (fog_c[2] - b) * fog)),
            (x, top), (x, bottom))
    sprites = [(e["x"], e["y"], "e2" if e.get("elite") else "enemy", e) for e in state.get("enemies", [])]
    sprites += [(l["x"], l["y"], l["k"], l) for l in state.get("loots", [])]
    if state.get("merchant"):
        sprites.append((state["merchant"]["x"], state["merchant"]["y"], "merchant", None))
    sprites.append((EXTRACT_ZONE.centerx, EXTRACT_ZONE.centery, "extract", None))
    sprites.sort(key=lambda s: (s[0] - cx) ** 2 + (s[1] - cy) ** 2, reverse=True)
    inv_det = 1.0 / (plane_x * dir_y - dir_x * plane_y)
    for sx, sy, kind, obj in sprites:
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
            pal = (obj.get("palette") if obj else None) or (PAL_ELITE if kind == "e2" else PAL_ENEMY)
            draw_char(surface, screen_x, top, h, w, pal, zbuf, ty, f)
            if obj and obj.get("type") == "boss" and ty < 800:
                draw_text(surface, "💀 撤离点守卫", 16, (255, 60, 60), center=(screen_x, max(0, top - 20)))
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
            color = (int(color[0] + (fog_c[0] - color[0]) * fog),
                     int(color[1] + (fog_c[1] - color[1]) * fog),
                     int(color[2] + (fog_c[2] - color[2]) * fog))
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
            color = (int(color[0] + (fog_c[0] - color[0]) * fog),
                     int(color[1] + (fog_c[1] - color[1]) * fog),
                     int(color[2] + (fog_c[2] - color[2]) * fog))
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
    _vip = bool(IS_VIP)
    maxhp = 100 + sv.get("armor", 0) * 50
    if _vip:
        maxhp = int(maxhp * 1.5)
    tasks = dict(sv.get("tasks", {"kill": 0, "collect": 0, "extract": 0}))
    weapons = {}
    for wkey, wdef in WEAPON_DEFS.items():
        weapons[wkey] = {"mag": wdef["mag"], "reserve": wdef["reserve"]}
        if _vip:
            weapons[wkey]["mag"] = wdef["mag"] * 2
            weapons[wkey]["reserve"] = wdef["reserve"] * 5
    # VIP：出生自带全部武器；普通玩家只带手枪
    _equipped = ["pistol", "rifle", "shotgun", "sniper"] if _vip else ["pistol"]
    _base_dmg = 25 + sv.get("dmg", 0) * 10
    if _vip:
        _base_dmg = int(_base_dmg * 1.5)
    _inv_max = 20
    if _vip:
        _inv_max = 40
    return {
        "x": x, "y": y, "a": 0.0, "hp": maxhp, "maxhp": maxhp,
        "dmg": _base_dmg,
        "weapons": weapons,
        "current_weapon": "pistol",
        "equipped": list(_equipped),
        "is_vip": _vip,
        "zoom": False,
        "mag": weapons["pistol"]["mag"],
        "res": weapons["pistol"]["reserve"],
        "cans": 0, "gold": 0, "key": 0, "med": 0,
        "reload": 0.0, "shoot_cd": 0.0, "med_cd": 0.0,
        "tasks": tasks,
        "inventory": {"ammo": 30, "medkit": 1, "can": 0, "gold": 0, "key": 0, "battery": 0},
        "inv_max": _inv_max,
        "hotbar": ["medkit", None, None, None, None],
        "last_kill_weapon": None,
    }

def new_enemy(x, y, etype=None):
    if etype is None:
        r = random.random()
        if r < 0.05:
            etype = "boss"
        elif r < 0.60:
            etype = "rusher"
        elif r < 0.85:
            etype = "sniper"
        else:
            etype = "thrower"
    info = ENEMY_TYPES.get(etype, ENEMY_TYPES["rusher"])
    return {"type": etype, "name": info["name"], "x": x, "y": y,
            "hp": info["hp"], "maxhp": info["hp"],
            "elite": 1 if etype in ("sniper", "thrower", "boss") else 0,
            "sp": info["sp"], "dmg": info["dmg"], "fire_rate": info["fire_rate"],
            "shoot_dist": info["shoot_dist"], "prefer_cover": info["prefer_cover"],
            "palette": info["color"],
            "shoot": random.uniform(0.5, 1.5), "wander": random.uniform(0, math.tau),
            "wt": random.uniform(0.5, 2.0), "patrol": gen_patrol_path(x, y, 250, 3),
            "patrol_idx": 0, "patrol_wait": 0.0, "cover_target": None, "cover_timer": 0.0}

def gen_patrol_path(x, y, radius=250, points=3):
    path = [(x, y)]
    for _ in range(points):
        ang = random.uniform(0, math.tau)
        dist = random.uniform(radius * 0.5, radius)
        px = x + math.cos(ang) * dist
        py = y + math.sin(ang) * dist
        if not point_collides(px, py, 24):
            path.append((px, py))
    return path

def find_cover(enemy, threat_x, threat_y):
    ex, ey = enemy["x"], enemy["y"]
    best = None
    best_score = -1e9
    for ang in range(0, 360, 45):
        rad = math.radians(ang)
        cx = ex + math.cos(rad) * 70
        cy = ey + math.sin(rad) * 70
        if point_collides(cx, cy, 26):
            continue
        dx, dy = threat_x - cx, threat_y - cy
        dist = math.hypot(dx, dy)
        if dist < 1:
            continue
        hit = cast_ray(threat_x, threat_y, math.atan2(dy, dx), dist + 30)
        blocked = hit < dist - 10
        if not blocked:
            continue
        own_dist = math.hypot(cx - ex, cy - ey)
        if own_dist > 200:
            continue
        score = -own_dist + (200 if blocked else 0)
        if score > best_score:
            best_score = score
            best = (cx, cy)
    return best

def add_loot(game, x, y, kind):
    lid = game["next_loot"]
    game["next_loot"] += 1
    game["loots"][lid] = {"x": x, "y": y, "k": kind}

def new_game(pids, map_idx):
    g = {"players": {}, "enemies": [], "loots": {}, "next_loot": 1, "extract": 0.0,
         "result": "play", "end_timer": 0.0, "inputs": {}, "in_zone": False,
         "doors_open": [False] * len(MAPS[map_idx].get("doors", [])),
         "start_time": time.time(), "no_damage": True}
    m = MAPS[map_idx]
    for i, pid in enumerate(pids):
        player = new_player(*m["spawns"][i % len(m["spawns"])])
        player["is_host"] = True
        g["players"][pid] = player
    for i, (x, y) in enumerate(m["enemies"]):
        if i == len(m["enemies"]) - 1:
            ex, ey = EXTRACT_ZONE.centerx, EXTRACT_ZONE.centery
            e = new_enemy(ex, ey, "boss")
            e["patrol"] = [(ex, ey)]
            e["patrol_idx"] = 0
            g["enemies"].append(e)
            continue
        g["enemies"].append(new_enemy(x, y))
    for x, y, k in m["loots"]:
        add_loot(g, x, y, k)
    g["merchant"] = {"x": random.randint(400, m["w"] - 400),
                     "y": random.randint(400, m["h"] - 400)}
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
    e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(e["wander"]), math.sin(e["wander"]),
                                          e.get("sp", 130) * 0.45, dt)
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
        if sid in g["players"]:
            g["players"][sid]["last_kill_weapon"] = s.get("weapon", "pistol")
    elif bp:
        _dmg = s.get("dmg", 25)
        if bp.get("shield", 0) > 0:
            _abs = min(bp["shield"], _dmg)
            bp["shield"] -= _abs
            _dmg -= _abs
        bp["hp"] -= _dmg
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
        sprinting = bool(inp.get("sprint"))
        _base_speed = p.get("move_speed", 320)
        spd = _base_speed * (1.5 if sprinting else 1.0)
        used = inv_total(p)
        if used >= p["inv_max"]:
            spd *= 0.7
        elif used >= p["inv_max"] * 0.8:
            spd *= 0.9
        p["x"], p["y"] = move_with_collision(p["x"], p["y"], dx, dy, spd, dt)
        p["shoot_cd"], p["med_cd"] = max(0.0, p["shoot_cd"] - dt), max(0.0, p["med_cd"] - dt)
        p["zoom"] = bool(inp.get("zoom", 0))
        wdef, wstate = get_current_weapon(p)
        if p["reload"] > 0:
            p["reload"] -= dt
            if p["reload"] <= 0:
                need = wdef["mag"] - wstate["mag"]
                take = min(need, wstate["reserve"])
                wstate["mag"] += take
                wstate["reserve"] -= take
                p["mag"] = wstate["mag"]
                p["res"] = wstate["reserve"]
        if inp.get("reload") and p["reload"] <= 0 and wstate["mag"] < wdef["mag"] and wstate["reserve"] > 0:
            _rm = p.get("reload_mult", 1.0)
            p["reload"] = wdef["reload"] * _rm
        if inp.get("med") and p["med_cd"] <= 0:
            if p["inventory"].get("medkit", 0) > 0 and p["hp"] < p["maxhp"]:
                p["inventory"]["medkit"] -= 1
                _heal = 70 if p.get("is_vip") else 35
                p["hp"] = min(p["maxhp"], p["hp"] + _heal)
                ACHIEVEMENTS["stats"]["total_meds_used"] += 1
                add_text(f"+{_heal} 生命")
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
            if wstate["mag"] > 0:
                wstate["mag"] -= 1
                p["mag"] = wstate["mag"]
                p["res"] = wstate["reserve"]
                p["shoot_cd"] = wdef["fire_rate"]
                for _ in range(wdef["rays"]):
                    spread = random.uniform(-wdef["spread"], wdef["spread"])
                    fake = {"x": p["x"], "y": p["y"], "a": p["a"] + spread,
                            "dmg": wdef["dmg"] + p.get("dmg", 0) - 25,
                            "weapon": p.get("current_weapon", "pistol")}
                    server_shoot(g, pid, fake)
                alert_enemies(g, pid, p["x"], p["y"], radius=800, dur=6)
            elif wstate["reserve"] > 0:
                p["reload"] = wdef["reload"]
    for e in g["enemies"][:]:
        if e["hp"] <= 0:
            g["enemies"].remove(e)
            if e.get("type") == "boss":
                add_loot(g, e["x"], e["y"], "weapon_sniper")
            elif e.get("elite") and random.random() < 0.4:
                add_loot(g, e["x"], e["y"], "weapon_shotgun")
            elif random.random() < 0.15:
                add_loot(g, e["x"], e["y"], "weapon_rifle")
            else:
                drop = "can" if e.get("elite") and random.random() < 0.6 else random.choice(["ammo", "medkit"])
                add_loot(g, e["x"], e["y"], drop)
            if LOGIN_USER:
                ACHIEVEMENTS["stats"]["total_kills"] += 1
                if e.get("type") == "boss":
                    ACHIEVEMENTS["stats"]["total_boss_kills"] += 1
                    add_text("💀 BOSS 已被击杀！")
                check_achievements()
                task_add_progress("kills", 1)
                for _pid2, _pp2 in g["players"].items():
                    if _pp2.get("is_vip") and _pp2["hp"] > 0:
                        _pp2["hp"] = min(_pp2["maxhp"], _pp2["hp"] + 5)
                if e.get("type") == "boss":
                    task_add_progress("boss_kills", 1)
                for pid_k, pp_k in g["players"].items():
                    wk = pp_k.get("last_kill_weapon")
                    if wk == "sniper":
                        task_add_progress("sniper_kills", 1)
                        ACHIEVEMENTS["stats"]["sniper_kills"] = ACHIEVEMENTS["stats"].get("sniper_kills", 0) + 1
                    elif wk == "shotgun":
                        task_add_progress("shotgun_kills", 1)
                    pp_k["last_kill_weapon"] = None
            continue
        e["at"] = max(0, e.get("at", 0) - dt)
        if e.get("cover_timer", 0) > 0:
            e["cover_timer"] -= dt
        tgt = None
        if e.get("at", 0) > 0 and e.get("ap") in g["players"] and g["players"][e["ap"]]["hp"] > 0:
            tgt = (e["ap"], g["players"][e["ap"]])
        else:
            tgt = nearest_alive_player(g, e["x"], e["y"])
        if tgt:
            pid, pl = tgt
            d = math.hypot(pl["x"] - e["x"], pl["y"] - e["y"])
            aggro = 950 if e.get("at", 0) > 0 else 500
            etype = e.get("type", "rusher")
            if d < aggro:
                shoot_dist = e.get("shoot_dist", 400)
                fire_rate = e.get("fire_rate", 0.8)
                if etype == "boss":
                    if d < shoot_dist:
                        e["shoot"] -= dt
                        if e["shoot"] <= 0:
                            e["shoot"] = fire_rate + random.uniform(-0.1, 0.2)
                            ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                            if cast_ray(e["x"], e["y"], ang, d + 20) > d - 10:
                                pl["hp"] -= e.get("dmg", 8)
                                pl["hp"] = max(0, pl["hp"])
                                g["no_damage"] = False
                    continue
                if e.get("prefer_cover") and e.get("cover_timer", 0) <= 0 and d < aggro:
                    cover = find_cover(e, pl["x"], pl["y"])
                    if cover:
                        e["cover_target"] = cover
                        e["cover_timer"] = random.uniform(2.0, 4.0)
                if e.get("cover_target") and e.get("cover_timer", 0) > 0:
                    cx, cy = e["cover_target"]
                    if math.hypot(cx - e["x"], cy - e["y"]) > 30:
                        ang = math.atan2(cy - e["y"], cx - e["x"])
                        e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang),
                                                              e.get("sp", 130) * 1.2, dt)
                    if d < shoot_dist:
                        e["shoot"] -= dt
                        if e["shoot"] <= 0:
                            e["shoot"] = fire_rate + random.uniform(-0.1, 0.2)
                            ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                            if cast_ray(e["x"], e["y"], ang, d + 20) > d - 10:
                                pl["hp"] -= e.get("dmg", 8)
                                pl["hp"] = max(0, pl["hp"])
                                g["no_damage"] = False
                else:
                    if etype == "rusher":
                        if d > 60:
                            ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                            e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang),
                                                                  e.get("sp", 130), dt)
                    elif etype == "sniper":
                        if d < 250:
                            ang = math.atan2(e["y"] - pl["y"], e["x"] - pl["x"])
                            e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang),
                                                                  e.get("sp", 130), dt)
                        elif d > 700:
                            ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                            e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang),
                                                                  e.get("sp", 130), dt)
                    elif etype == "thrower":
                        if d < 200:
                            ang = math.atan2(e["y"] - pl["y"], e["x"] - pl["x"])
                            e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang),
                                                                  e.get("sp", 130), dt)
                        elif d > 450:
                            ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                            e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang),
                                                                  e.get("sp", 130), dt)
                    if d < shoot_dist:
                        e["shoot"] -= dt
                        if e["shoot"] <= 0:
                            e["shoot"] = fire_rate + random.uniform(-0.1, 0.2)
                            ang = math.atan2(pl["y"] - e["y"], pl["x"] - e["x"])
                            if cast_ray(e["x"], e["y"], ang, d + 20) > d - 10:
                                pl["hp"] -= e.get("dmg", 8)
                                pl["hp"] = max(0, pl["hp"])
                                g["no_damage"] = False
            else:
                patrol = e.get("patrol") or []
                if len(patrol) >= 2:
                    if e.get("patrol_wait", 0) > 0:
                        e["patrol_wait"] -= dt
                    else:
                        tgt_pt = patrol[e["patrol_idx"] % len(patrol)]
                        dxp, dyp = tgt_pt[0] - e["x"], tgt_pt[1] - e["y"]
                        dist_p = math.hypot(dxp, dyp)
                        if dist_p < 20:
                            e["patrol_idx"] = (e["patrol_idx"] + 1) % len(patrol)
                            e["patrol_wait"] = random.uniform(0.5, 1.5)
                        else:
                            ang = math.atan2(dyp, dxp)
                            e["x"], e["y"] = move_with_collision(e["x"], e["y"], math.cos(ang), math.sin(ang),
                                                                  e.get("sp", 130) * 0.5, dt)
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
                    if inv_add(pp, "can", 1):
                        pp["cans"] += 1
                        pp["tasks"]["collect"] = pp["tasks"].get("collect", 0) + 1
                        add_text("🥫 +1 罐头")
                        task_add_progress("cans", 1)
                    else:
                        continue
                elif l["k"] == "ammo":
                    if inv_add(pp, "ammo", 30):
                        add_text("🔸 +30 弹药")
                    else:
                        continue
                elif l["k"] == "medkit":
                    if inv_add(pp, "medkit", 1):
                        add_text("💊 +1 医疗包")
                        task_add_progress("medkits", 1)
                    else:
                        continue
                elif l["k"] == "key":
                    if inv_add(pp, "key", 1):
                        pp["key"] = 1
                        add_text("🔑 获得万能钥匙")
                    else:
                        continue
                elif l["k"] == "gold":
                    if inv_add(pp, "gold", 1):
                        pp["gold"] += 1
                        ACHIEVEMENTS["stats"]["total_gold_cans"] += 1
                        check_achievements()
                        add_text("🥇 +1 金罐头")
                        task_add_progress("gold_cans", 1)
                    else:
                        continue
                elif l["k"] == "battery":
                    if inv_add(pp, "battery", 1):
                        add_text("🔋 +1 电池")
                    else:
                        continue
                elif l["k"].startswith("weapon_"):
                    wkey = l["k"][7:]
                    if wkey in WEAPON_DEFS:
                        if wkey not in pp["equipped"]:
                            pp["equipped"].append(wkey)
                            add_text(f"🔫 解锁 {WEAPON_DEFS[wkey]['name']}")
                            pp["current_weapon"] = wkey
                            wdef2, wstate2 = get_current_weapon(pp)
                            wstate2["mag"] = wdef2["mag"]
                            wstate2["reserve"] = wdef2["reserve"]
                            pp["mag"] = wstate2["mag"]
                            pp["res"] = wstate2["reserve"]
                            if len(pp["equipped"]) >= 4:
                                unlock_achievement("weapon_master")
                        else:
                            wstate2 = pp["weapons"][wkey]
                            wstate2["reserve"] += WEAPON_DEFS[wkey]["reserve"] // 2
                            add_text(f"🔫 {WEAPON_DEFS[wkey]['name']} 备弹 +")
                    else:
                        continue
                del g["loots"][lid]
                break
    g["in_zone"] = any(p["hp"] > 0 and EXTRACT_ZONE.collidepoint(int(p["x"]), int(p["y"]))
                        for p in g["players"].values())
    any_ext = any(p["hp"] > 0 and p["cans"] >= 3 and EXTRACT_ZONE.collidepoint(int(p["x"]), int(p["y"]))
                  for p in g["players"].values())
    if any_ext:
        g["extract"] += dt
        if g["extract"] >= 3.0:
            g["result"] = "win"
            for pid, p in g["players"].items():
                if p["hp"] > 0:
                    p["tasks"]["extract"] = p["tasks"].get("extract", 0) + 1
                    task_add_progress("extracts", 1)
                    if g.get("no_damage"):
                        task_add_progress("no_damage_extracts", 1)
                    if IS_NIGHT:
                        task_add_progress("night_extracts", 1)
                    if inv_total(p) >= p["inv_max"]:
                        task_add_progress("full_backpack_extracts", 1)
    else:
        g["extract"] = max(0.0, g["extract"] - dt * 2.0)
    if not any(p["hp"] > 0 for p in g["players"].values()):
        g["result"] = "lose"

def make_state(g):
    return {"t": "state",
            "players": [{"id": pid, **p} for pid, p in g["players"].items()],
            "enemies": [{"x": e["x"], "y": e["y"], "hp": e["hp"], "elite": e.get("elite", 0),
                         "type": e.get("type", "rusher"), "palette": e.get("palette")}
                        for e in g["enemies"]],
            "loots": [{"id": lid, **l} for lid, l in g["loots"].items()],
            "extract": g["extract"], "result": g["result"],
            "in_zone": g.get("in_zone", False),
            "doors_open": g.get("doors_open", DOORS_OPEN),
            "merchant": g.get("merchant")}

def read_input(px, py, dt):
    global VIEW, FLASH_ON, MERCHANT_OPEN
    if CHAT_FOCUS or SHOP_OPEN or BACKPACK_OPEN:
        return {"dx": 0, "dy": 0, "a": VIEW["a"], "shoot": 0, "sprint": 0,
                "use": 0, "reload": 0, "med": 0, "buy": 0, "zoom": 0}
    move_x, move_y = 0.0, 0.0
    if KEY_STATE["w"]: move_y += 1
    if KEY_STATE["s"]: move_y -= 1
    if KEY_STATE["a"]: move_x -= 1
    if KEY_STATE["d"]: move_x += 1
    a = VIEW["a"]
    dx = math.cos(a) * move_y + math.cos(a + math.pi / 2) * move_x
    dy = math.sin(a) * move_y + math.sin(a + math.pi / 2) * move_x
    l = math.hypot(dx, dy)
    if l > 0:
        dx /= l
        dy /= l
    mouse_pressed = pygame.mouse.get_pressed()[0]
    shoot = 1 if (KEY_STATE["space"] or mouse_pressed) else 0
    reload_ = 1 if KEY_STATE["r"] else 0
    med = 1 if KEY_STATE["q"] else 0
    use_ = 1 if KEY_STATE["e"] else 0
    sprint = 1 if KEY_STATE["shift"] else 0
    zoom = 1 if pygame.mouse.get_pressed()[2] else 0
    if shoot:
        FEED["muzzle"] = 0.06
        play("shoot")
    if sprint or move_x or move_y:
        FEED["bob"] += dt * (11 if sprint else 7)
    return {"dx": dx, "dy": dy, "a": a, "shoot": shoot, "sprint": sprint,
            "use": use_, "reload": reload_, "med": med, "buy": 0, "zoom": zoom}

def get_player_from_state(st, pid):
    if not st:
        return None
    for p in st.get("players", []):
        if p.get("id") == pid:
            return p
    return None

def draw_minimap(screen, st, my_id):
    if not SETTINGS.get("show_minimap", True):
        return
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
    pygame.draw.rect(screen, (80, 220, 130),
                     (ox + EXTRACT_ZONE.x * s, oy + EXTRACT_ZONE.y * s, EXTRACT_ZONE.w * s, EXTRACT_ZONE.h * s))
    if st:
        if st.get("merchant"):
            m = st["merchant"]
            pygame.draw.circle(screen, (255, 215, 0), (ox + int(m["x"] * s), oy + int(m["y"] * s)), 4)
        for l in st.get("loots", []):
            pygame.draw.rect(screen, LOOT_COLORS.get(l["k"], (255, 200, 80)),
                             (ox + l["x"] * s - 1, oy + l["y"] * s - 1, 3, 3))
        for e in st.get("enemies", []):
            pal = e.get("palette") or PAL_ENEMY
            col = pal["H"]
            if e.get("type") == "boss":
                col = (255, 40, 40)
            pygame.draw.rect(screen, col, (ox + e["x"] * s - 2, oy + e["y"] * s - 2, 4, 4))
        me = get_player_from_state(st, my_id)
        for p in st.get("players", []):
            px, py = ox + int(p["x"] * s), oy + int(p["y"] * s)
            pygame.draw.circle(screen, (90, 170, 255) if p["id"] == my_id else (200, 200, 255), (px, py), 3)
            if p["id"] == my_id and me:
                pygame.draw.line(screen, (255, 255, 255), (px, py),
                                 (px + int(math.cos(me["a"]) * 8), py + int(math.sin(me["a"]) * 8)), 1)
    pygame.draw.rect(screen, (95, 105, 125), (ox - 2, oy - 2, mw + 4, mh + 4), 2, border_radius=6)

def _draw_chat_widget(screen, base_x, base_y, panel_w, panel_h, title, rect_store):
    global CHAT_HAS_NEW_MESSAGE, CHAT_FOCUS
    panel_rect = pygame.Rect(base_x, base_y, panel_w, panel_h)
    input_rect = pygame.Rect(base_x, base_y + panel_h + 6, panel_w - 80, 32)
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
        hint = "按回车发言" if not CHAT_HAS_NEW_MESSAGE else "有新消息"
        draw_text(screen, hint, 17, (150, 160, 180), topleft=(input_rect.x + 8, input_rect.y + 6))
    hov = send_rect.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(screen, (60, 150, 90) if hov else (40, 100, 60), send_rect, border_radius=6)
    pygame.draw.rect(screen, (120, 220, 150), send_rect, 2, border_radius=6)
    draw_text(screen, "发送", 17, (255, 255, 255), center=send_rect.center)

def draw_chat_game(screen):
    if not LOGIN_USER:
        return
    _draw_chat_widget(screen, 16, HEIGHT - 260, 520, 150, "聊天", CHAT_GAME_RECTS)

def draw_chat_menu(screen):
    if not LOGIN_USER:
        return
    _draw_chat_widget(screen, WIDTH - 540, HEIGHT - 190, 520, 150, "世界聊天", CHAT_MENU_RECTS)

def draw_world(screen, st, my_id, is_host, dt, game_state=None):
    global LAST_SYNC_TIME
    me = get_player_from_state(st, my_id) if st else None
    if not st or not me:
        screen.fill((15, 18, 22))
        draw_panel(screen, pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 60, 520, 120))
        draw_text(screen, "正在连接服务器...", 32, (235, 240, 245), center=(WIDTH // 2, HEIGHT // 2))
        return
    smooth_remote_players(dt)
    smoothed = get_smoothed_remote()
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
    if FEED["cans"] is not None and me["cans"] > FEED["cans"]:
        play("pick")
    FEED["cans"] = me["cans"]
    if me["reload"] > 0 and not FEED["rl"]:
        play("reload")
    FEED["rl"] = me["reload"] > 0
    res = st.get("result", "play")
    if FEED["res"] != res:
        if res == "win":
            play("win")
            gained = me["cans"] * 100 + me.get("gold", 0) * 300
            if me.get("is_vip"):
                gained = int(gained * 2)      # VIP：撤离收益翻倍（只乘一次）
            tasks = me.get("tasks", {})
            task_reward = 0
            if tasks.get("kill", 0) >= 5: task_reward += 200
            if tasks.get("collect", 0) >= 3: task_reward += 150
            if tasks.get("extract", 0) >= 1: task_reward += 300
            gained += task_reward
            SAVE["money"] += gained
            SAVE["tasks"] = tasks
            push_save_async()
            add_text(f"撤离成功 +{gained} 金币")
            ACHIEVEMENTS["stats"]["total_extracts"] += 1
            ACHIEVEMENTS["stats"]["games_played"] += 1
            ACHIEVEMENTS["stats"]["total_gold_cans"] += me.get("gold", 0)
            ACHIEVEMENTS["stats"]["max_money"] = max(ACHIEVEMENTS["stats"]["max_money"], SAVE["money"])
            if IS_NIGHT: ACHIEVEMENTS["stats"]["night_extracts"] += 1
            if me["hp"] <= 10: unlock_achievement("survivor")
            if game_state and game_state.get("no_damage"): unlock_achievement("no_damage")
            check_achievements()
            save_achievements()
            stop_recording("win", gained)
        elif res == "lose":
            play("lose")
            stop_recording("lose", 0)
        FEED["res"] = res
    bob = math.sin(FEED["bob"]) * 4
    st_view = dict(st)
    st_view["players"] = list(st.get("players", []))
    existing_ids = {p.get("id") for p in st_view["players"]}
    for name, s in smoothed.items():
        replaced = False
        for i, p in enumerate(st_view["players"]):
            if p.get("id") == name:
                st_view["players"][i] = {**p, "x": s["x"], "y": s["y"], "a": s["a"], "hp": s["hp"]}
                replaced = True
                break
        if not replaced and name not in existing_ids:
            st_view["players"].append({
                "id": name, "x": s["x"], "y": s["y"], "a": s["a"], "hp": s["hp"],
                "maxhp": 100, "mag": 30, "res": 120, "cans": 0, "gold": 0,
                "key": 0, "med": 0, "dmg": 25, "reload": 0, "shoot_cd": 0, "med_cd": 0,
                "tasks": {"kill": 0, "collect": 0, "extract": 0}})
            existing_ids.add(name)
    st_view["zoom_active"] = False
    st_view["zoom_level"] = 1.0
    if me and me.get("zoom"):
        wdef_z, _ = get_current_weapon(me)
        st_view["zoom_active"] = True
        st_view["zoom_level"] = wdef_z.get("zoom", 1.0)
    render_view(canvas, me["x"], me["y"], VIEW["a"], st_view, my_id, bob)
    screen.blit(pygame.transform.smoothscale(canvas, (WIDTH, HEIGHT)), (0, 0))
    if FEED["dmg"] > 0:
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((255, 0, 0, int(FEED["dmg"] * 220)))
        screen.blit(ov, (0, 0))
    if FEED["muzzle"] > 0:
        pygame.draw.circle(screen, (255, 220, 120), (WIDTH // 2 + 2, HEIGHT - 170 + int(bob)), 14)
    draw_panel(screen, pygame.Rect(16, 16, 470, 54))
    draw_text(screen, f"地图: {MAPS[CURRENT_MAP_IDX]['name']} ({THEMES['night' if IS_NIGHT else 'day']['name']})",
              22, (215, 220, 232), topleft=(32, 30))
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
    if me.get("is_vip"):
        draw_text(screen, "👑 VIP", 18, (255, 215, 100), topleft=(WIDTH - 120, HEIGHT - 96))
    ratio = max(0, me["hp"]) / me["maxhp"]
    col = (110, 230, 140) if ratio > 0.5 else (255, 215, 95) if ratio > 0.25 else (255, 90, 90)
    draw_text(screen, "生命", 20, (150, 160, 175), topleft=(32, HEIGHT - 88))
    draw_bar(screen, pygame.Rect(32, HEIGHT - 60, 270, 18), ratio, col)
    draw_text(screen, str(max(0, me["hp"])), 30, col, topleft=(312, HEIGHT - 66))
    draw_text(screen, f"医疗包 x{me['inventory'].get('medkit', 0)}  金罐头 {me.get('gold', 0)}",
              20, (255, 230, 120), topleft=(32, HEIGHT - 36))
    draw_panel(screen, pygame.Rect(WIDTH - 246, HEIGHT - 100, 230, 84))
    wdef, wstate = get_current_weapon(me)
    draw_text(screen, f"{wdef['icon']} {wdef['name']}", 18, (255, 215, 95), topleft=(WIDTH - 230, HEIGHT - 96))
    if me["reload"] > 0:
        draw_text(screen, "换弹中...", 30, (255, 215, 95), center=(WIDTH - 131, HEIGHT - 54))
    else:
        draw_text(screen, str(wstate["mag"]), 42, (255, 255, 255), topleft=(WIDTH - 230, HEIGHT - 76))
        draw_text(screen, f"/ {wstate['reserve']}", 22, (150, 160, 175), topleft=(WIDTH - 160, HEIGHT - 52))
    draw_text(screen, f"敌人 {len(st.get('enemies', []))}", 18, (235, 140, 140), topleft=(WIDTH - 230, HEIGHT - 28))
    draw_panel(screen, pygame.Rect(WIDTH // 2 - 200, HEIGHT - 40, 400, 32))
    for i, wk in enumerate(WEAPON_ORDER):
        x = WIDTH // 2 - 170 + i * 90
        sel = (wk == me.get("current_weapon", "pistol"))
        has = wk in me.get("equipped", [])
        c = (255, 215, 95) if sel else ((200, 220, 200) if has else (80, 90, 100))
        draw_text(screen, f"{i+1} {WEAPON_DEFS[wk]['name']}", 14, c, topleft=(x, HEIGHT - 36))
    if FLASH_ON:
        bx, by = WIDTH - 246, 100
        draw_panel(screen, pygame.Rect(bx, by, 230, 44))
        ratio_f = FLASH_BATTERY / FLASH_BATTERY_MAX
        col_f = (255, 220, 100) if ratio_f > 0.3 else (255, 90, 90)
        draw_text(screen, "🔦", 22, col_f, topleft=(bx + 10, by + 8))
        draw_bar(screen, pygame.Rect(bx + 45, by + 14, 150, 14), ratio_f, col_f)
        draw_text(screen, f"{int(FLASH_BATTERY)}%", 16, col_f, topleft=(bx + 200, by + 12))
    used = inv_total(me)
    draw_text(screen, f"🎒 {used}/{me['inv_max']}", 14, (180, 220, 150), topleft=(WIDTH - 230, 152))
    if SETTINGS.get("show_fps", True):
        fps = int(1 / dt) if dt > 0 else 0
        draw_text(screen, f"FPS: {fps}", 14, (150, 200, 150), topleft=(WIDTH - 80, 10))
    cx, cy = WIDTH // 2, HEIGHT // 2
    pygame.draw.circle(screen, (240, 240, 240), (cx, cy), 2)
    g, l = 6, 9
    pygame.draw.line(screen, (240, 240, 240), (cx - g - l, cy), (cx - g, cy), 2)
    pygame.draw.line(screen, (240, 240, 240), (cx + g, cy), (cx + g + l, cy), 2)
    pygame.draw.line(screen, (240, 240, 240), (cx, cy - g - l), (cx, cy - g), 2)
    pygame.draw.line(screen, (240, 240, 240), (cx, cy + g), (cx, cy + g + l), 2)
    draw_minimap(screen, st_view, my_id)
    draw_chat_game(screen)
    if LOGIN_USER and SYNC_RUNNING and MULTIPLAYER_MODE and CURRENT_ROOM_ID:
        current_time = time.time()
        if current_time - LAST_SYNC_TIME > SETTINGS.get("sync_rate", SYNC_INTERVAL):
            LAST_SYNC_TIME = current_time
            update_room_player_async(CURRENT_ROOM_ID, LOGIN_USER, me["x"], me["y"], VIEW["a"], me["hp"],
                                      reload=(me["reload"] > 0), shoot=(FEED["muzzle"] > 0),
                                      sprint=KEY_STATE["shift"])
    res = st.get("result", "play")
    if res in ("win", "lose"):
        draw_overlay(screen, 190)
        win = res == "win"
        bc = (110, 230, 140) if win else (255, 90, 90)
        draw_panel(screen, pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 170, 660, 340), alpha=235, border=bc)
        draw_text(screen, "任务成功" if win else "任务失败", 64, bc, center=(WIDTH // 2, HEIGHT // 2 - 90))
        draw_text(screen, f"罐头 {min(me['cans'], 3)}/3 · 金罐头 {me.get('gold', 0)} · 剩余生命 {max(0, me['hp'])}",
                  26, (220, 225, 235), center=(WIDTH // 2, HEIGHT // 2 - 10))
        draw_text(screen, "按 ESC 返回主页", 22, (150, 160, 175), center=(WIDTH // 2, HEIGHT // 2 + 90))
    if SHOP_OPEN:
        draw_shop(screen, me)
    if BACKPACK_OPEN:
        draw_backpack(screen, me)
    draw_achievement_popups(screen)

def menu_buttons():
    return {
        "solo": pygame.Rect(60, 160, 230, 45),
        "join": pygame.Rect(310, 160, 230, 45),
        "room_list": pygame.Rect(60, 215, 480, 45),
        "create_room": pygame.Rect(60, 270, 480, 45),
        "quit": pygame.Rect(60, 325, 230, 45),
        "help": pygame.Rect(310, 325, 230, 45),
        "settings": pygame.Rect(60, 380, 230, 45),
        "achievements": pygame.Rect(310, 380, 230, 45),
        "replays": pygame.Rect(60, 435, 230, 35),
        "friends": pygame.Rect(310, 435, 230, 35),
        "map_prev": pygame.Rect(700, 190, 50, 40),
        "map_next": pygame.Rect(1090, 190, 50, 40),
        "toggle_night": pygame.Rect(680, 240, 420, 40),
        "buy_armor": pygame.Rect(680, 300, 420, 36),
        "buy_dmg": pygame.Rect(680, 345, 420, 36),
        "buy_ammo": pygame.Rect(680, 390, 420, 36),
        "user_box": pygame.Rect(60, 490, 220, 36),
        "pass_box": pygame.Rect(60, 540, 220, 36),
        "btn_register": pygame.Rect(300, 490, 100, 36),
        "btn_login": pygame.Rect(300, 540, 100, 36),
        "btn_logout": pygame.Rect(300, 490, 100, 36),
        "more": pygame.Rect(60, 380, 230, 45),
        "sub_achievements": pygame.Rect(0, 0, 0, 0),
        "sub_replays": pygame.Rect(0, 0, 0, 0),
        "sub_friends": pygame.Rect(0, 0, 0, 0),
        "sub_buy_vip": pygame.Rect(0, 0, 0, 0),
        "sub_settings": pygame.Rect(0, 0, 0, 0),
        "sub_close": pygame.Rect(0, 0, 0, 0)}

def more_menu_rects():
    """更多功能面板的固定按钮坐标（绘制与点击共用）"""
    panel = pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 240, 520, 480)
    items = ["sub_achievements", "sub_replays", "sub_friends",
             "sub_buy_vip", "sub_settings"]
    rects = {}
    y = panel.y + 110
    for key in items:
        rects[key] = pygame.Rect(panel.x + 60, y, 400, 52)
        y += 62
    rects["sub_close"] = pygame.Rect(panel.right - 60, panel.y + 16, 44, 44)
    rects["__panel__"] = panel
    return rects

def _draw_more_panel(screen, btns=None):
    """⋯ 更多功能 弹出面板（使用固定坐标，保证可点击）"""
    draw_overlay(screen, 180)
    rects = more_menu_rects()
    panel = rects["__panel__"]
    draw_panel(screen, panel, alpha=245, border=(255, 200, 100), radius=15)
    draw_text(screen, "⋯ 更多功能", 36, (255, 200, 100),
              center=(WIDTH // 2, panel.y + 40))

    close_rect = rects["sub_close"]
    hov_close = close_rect.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(screen, (180, 60, 60) if hov_close else (120, 40, 40),
                     close_rect, border_radius=8)
    draw_text(screen, "X", 28, (255, 255, 255), center=close_rect.center)

    items = [
        ("sub_achievements", "🏅 成就"),
        ("sub_replays",      "🎬 回放"),
        ("sub_friends",      "👥 好友"),
        ("sub_buy_vip",      "👑 购买 VIP"),
        ("sub_settings",     "⚙ 设置"),
    ]
    for key, label in items:
        r = rects[key]
        hov = r.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, (60, 90, 140) if hov else (40, 55, 80),
                         r, border_radius=10)
        pygame.draw.rect(screen, (120, 180, 255) if hov else (90, 110, 150),
                         r, 2, border_radius=10)
        draw_text(screen, label, 26, (255, 255, 255), center=r.center)

    if IS_VIP:
        draw_text(screen, f"👑 VIP {LOGIN_USER}", 20, (255, 215, 100),
                  center=(WIDTH // 2, panel.bottom - 60))
    else:
        draw_text(screen, "开通 VIP 享 1.5 倍伤害 / 双倍收益",
                  18, (180, 190, 210), center=(WIDTH // 2, panel.bottom - 60))

def draw_slider(screen, panel, y, label, path, vmin, vmax, step, fmt="{:.2f}"):
    val = get_setting(path, vmin)
    draw_text(screen, label, 24, (220, 225, 235), topleft=(panel.x + 60, y + 10))
    bar = pygame.Rect(panel.x + 320, y + 16, 380, 10)
    pygame.draw.rect(screen, (40, 46, 58), bar, border_radius=5)
    ratio = (val - vmin) / (vmax - vmin) if vmax > vmin else 0
    ratio = max(0, min(1, ratio))
    pygame.draw.rect(screen, (255, 190, 80), (bar.x, bar.y, int(bar.w * ratio), bar.h), border_radius=5)
    pygame.draw.circle(screen, (255, 230, 150), (bar.x + int(bar.w * ratio), bar.centery), 10)
    draw_text(screen, fmt.format(val), 20, (255, 255, 255), topleft=(bar.right + 20, y + 6))
    mouse = pygame.mouse.get_pos()
    if pygame.Rect(bar.x - 10, bar.y - 14, bar.w + 20, bar.h + 28).collidepoint(mouse) and pygame.mouse.get_pressed()[0]:
        r = max(0, min(1, (mouse[0] - bar.x) / bar.w))
        new_val = round((vmin + (vmax - vmin) * r) / step) * step
        set_setting(path, max(vmin, min(vmax, new_val)))

def draw_toggle(screen, panel, y, label, path):
    val = bool(get_setting(path, False))
    draw_text(screen, label, 24, (220, 225, 235), topleft=(panel.x + 60, y + 10))
    box = pygame.Rect(panel.x + 320, y + 4, 80, 36)
    pygame.draw.rect(screen, (60, 180, 100) if val else (90, 60, 60), box, border_radius=18)
    knob_x = box.right - 20 if val else box.x + 20
    pygame.draw.circle(screen, (255, 255, 255), (knob_x, box.centery), 14)
    draw_text(screen, "开" if val else "关", 20, (255, 255, 255), topleft=(box.right + 20, y + 8))
    if box.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        set_setting(path, not val)

def draw_settings(screen):
    global SETTINGS_TAB, SETTINGS_REBIND, SETTINGS_OPEN
    draw_overlay(screen, 210)
    panel = pygame.Rect(WIDTH // 2 - 480, HEIGHT // 2 - 320, 960, 640)
    draw_panel(screen, panel, alpha=245, border=(255, 200, 100), radius=15)
    draw_text(screen, "设置", 40, (255, 200, 100), center=(WIDTH // 2, panel.y + 40))
    close_rect = pygame.Rect(panel.right - 60, panel.y + 16, 44, 44)
    hov = close_rect.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(screen, (180, 60, 60) if hov else (120, 40, 40), close_rect, border_radius=8)
    draw_text(screen, "X", 28, (255, 255, 255), center=close_rect.center)
    if hov and pygame.mouse.get_pressed()[0]:
        SETTINGS_OPEN = False
        save_settings()
        return
    tabs = [("general", "常规"), ("controls", "按键"), ("audio", "音频"), ("video", "画面")]
    tab_y = panel.y + 80
    tab_x = panel.x + 30
    for key, name in tabs:
        r = pygame.Rect(tab_x, tab_y, 140, 42)
        active = (SETTINGS_TAB == key)
        pygame.draw.rect(screen, (255, 190, 80) if active else (50, 60, 80), r, border_radius=8)
        draw_text(screen, name, 22, (255, 255, 255), center=r.center)
        if r.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
            SETTINGS_TAB = key
            SETTINGS_REBIND = None
        tab_x += 150
    content_y = panel.y + 150
    if SETTINGS_TAB == "general":
        draw_slider(screen, panel, content_y, "鼠标灵敏度", "mouse_sens", 0.0005, 0.01, 0.0001, "{:.4f}")
        draw_toggle(screen, panel, content_y + 70, "显示 FPS", "show_fps")
        draw_toggle(screen, panel, content_y + 140, "显示小地图", "show_minimap")
    elif SETTINGS_TAB == "controls":
        actions = [("up", "前进"), ("down", "后退"), ("left", "左移"), ("right", "右移"),
                   ("sprint", "疾跑"), ("shoot", "射击"), ("reload", "换弹"),
                   ("med", "医疗包"), ("use", "使用/开门"), ("flash", "手电筒"),
                   ("shop", "商店"), ("chat", "聊天")]
        col_w = 420
        for i, (akey, aname) in enumerate(actions):
            col = i % 2
            row = i // 2
            x = panel.x + 60 + col * (col_w + 60)
            y = content_y + row * 60
            draw_text(screen, aname, 22, (220, 225, 235), topleft=(x, y + 10))
            bind_rect = pygame.Rect(x + 180, y, 200, 44)
            is_rebinding = (SETTINGS_REBIND == akey)
            pygame.draw.rect(screen, (255, 190, 80) if is_rebinding else (60, 70, 90), bind_rect, border_radius=8)
            pygame.draw.rect(screen, (255, 220, 120) if is_rebinding else (120, 130, 150), bind_rect, 2, border_radius=8)
            kname = get_setting(f"keys.{akey}", "")
            label = "按下按键..." if is_rebinding else kname.upper()
            draw_text(screen, label, 20, (255, 255, 255), center=bind_rect.center)
            if bind_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
                SETTINGS_REBIND = akey
    elif SETTINGS_TAB == "audio":
        draw_slider(screen, panel, content_y, "主音量", "master_vol", 0.0, 1.0, 0.05)
        draw_slider(screen, panel, content_y + 70, "音效音量", "sfx_vol", 0.0, 1.0, 0.05)
    elif SETTINGS_TAB == "video":
        draw_slider(screen, panel, content_y, "雾距离倍率", "fog_quality", 0.5, 1.5, 0.1, "{:.1f}x")
        draw_slider(screen, panel, content_y + 70, "同步频率(秒)", "sync_rate", 0.05, 0.5, 0.05, "{:.2f}s")
    draw_text(screen, "按 ESC 保存并关闭", 18, (150, 160, 175), center=(WIDTH // 2, panel.bottom - 15))

def draw_room_list(screen):
    global ROOM_LIST_PAGE, SHOW_ROOM_LIST, ALERT_MSG, ALERT_TIME
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
            pc = len(room.get("players", []))
            mx = room.get("max_players", 10)
            draw_text(screen, f"{room.get('name', '未命名')}", 20, (255, 255, 255), topleft=(170, y + 8))
            draw_text(screen, f"人数 {pc}/{mx}  房主 {room.get('host', '')[:15]}",
                      16, (200, 200, 200), topleft=(170, y + 32))
            join_btn = pygame.Rect(card_rect.right - 120, y + 12, 100, 36)
            can_join = room.get('status') == 'waiting' and pc < mx and LOGIN_USER
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
    pygame.draw.rect(screen, (30, 34, 44), name_rect)
    pygame.draw.rect(screen, (255, 190, 80) if CREATE_FOCUS == "name" else (90, 100, 120), name_rect, 2, border_radius=6)
    draw_text(screen, CREATE_ROOM_NAME or "输入房间名...", 20,
              (255, 255, 255) if CREATE_ROOM_NAME else (120, 130, 150), topleft=(260, 228))
    if name_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        CREATE_FOCUS = "name"
    draw_text(screen, "房间密码（留空为公开）:", 22, (200, 200, 200), topleft=(250, 280))
    pass_rect = pygame.Rect(250, 310, 400, 40)
    pygame.draw.rect(screen, (30, 34, 44), pass_rect)
    pygame.draw.rect(screen, (255, 190, 80) if CREATE_FOCUS == "password" else (90, 100, 120), pass_rect, 2, border_radius=6)
    draw_text(screen, ("*" * len(CREATE_ROOM_PASSWORD)) or "设置密码...", 20,
              (255, 255, 255) if CREATE_ROOM_PASSWORD else (120, 130, 150), topleft=(260, 318))
    if pass_rect.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
        CREATE_FOCUS = "password"
    draw_text(screen, "选择地图:", 22, (200, 200, 200), topleft=(250, 370))
    for i, name in enumerate([m["name"] for m in MAPS]):
        btn_rect = pygame.Rect(250 + i * 160, 400, 140, 36)
        sel = (i == CREATE_ROOM_MAP)
        pygame.draw.rect(screen, (255, 190, 80) if sel else (50, 60, 80), btn_rect, border_radius=8)
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
            result = create_room(CREATE_ROOM_NAME.strip(), CREATE_ROOM_PASSWORD, LOGIN_USER,
                                  CREATE_ROOM_MAP, CREATE_ROOM_NIGHT)
            if result.get('success'):
                SHOW_CREATE_ROOM = False
                SHOW_ROOM_LIST = False
                join_room_success(result['room_id'], result['room'])
            else:
                ALERT_MSG = result.get('message', "创建失败")
                ALERT_TIME = 3.0

def draw_achievement_panel(screen):
    if not ACHIEVEMENT_OPEN:
        return
    draw_overlay(screen, 220)
    panel = pygame.Rect(WIDTH // 2 - 480, HEIGHT // 2 - 340, 960, 680)
    draw_panel(screen, panel, alpha=245, border=(255, 200, 100), radius=15)
    draw_text(screen, "🏅 成就", 40, (255, 200, 100), center=(WIDTH // 2, panel.y + 40))
    total = len(ACHIEVEMENT_DEFS)
    unlocked = len(ACHIEVEMENTS["unlocked"])
    draw_text(screen, f"已解锁 {unlocked} / {total}", 22, (220, 225, 235), center=(WIDTH // 2, panel.y + 78))
    ids = list(ACHIEVEMENT_DEFS.keys())
    for i, aid in enumerate(ids):
        col = i % 2
        row = i // 2
        x = panel.x + 40 + col * 460
        y = panel.y + 130 + row * 60
        if y + 60 > panel.bottom - 60:
            break
        name, desc, icon, hidden = ACHIEVEMENT_DEFS[aid]
        done = aid in ACHIEVEMENTS["unlocked"]
        rect = pygame.Rect(x, y, 440, 52)
        pygame.draw.rect(screen, (35, 45, 60) if done else (25, 30, 40), rect, border_radius=8)
        pygame.draw.rect(screen, (255, 215, 100) if done else (60, 70, 90), rect, 2, border_radius=8)
        draw_text(screen, icon, 30, (255, 255, 255) if done else (100, 110, 130), topleft=(x + 10, y + 6))
        nc = (255, 215, 100) if done else (150, 160, 180)
        draw_text(screen, name, 20, nc, topleft=(x + 55, y + 6))
        draw_text(screen, desc, 14, (150, 160, 180), topleft=(x + 55, y + 28))
    draw_text(screen, "按 K 关闭", 18, (150, 160, 175), center=(WIDTH // 2, panel.bottom - 30))

def draw_replay_panel(screen):
    global REPLAY_PANEL_OPEN, REPLAY_LIST_PAGE
    if not REPLAY_PANEL_OPEN:
        return
    draw_overlay(screen, 220)
    panel = pygame.Rect(WIDTH // 2 - 500, HEIGHT // 2 - 340, 1000, 680)
    draw_panel(screen, panel, alpha=245, border=(100, 180, 255), radius=15)
    draw_text(screen, "🎬 战斗回放", 40, (100, 180, 255), center=(WIDTH // 2, panel.y + 40))
    list_replays()
    total = len(REPLAY_LIST)
    draw_text(screen, f"共 {total} 个回放", 18, (200, 200, 200), center=(WIDTH // 2, panel.y + 75))
    if total == 0:
        draw_text(screen, "暂无回放", 22, (150, 150, 150), center=(WIDTH // 2, panel.y + 200))
    else:
        total_pages_rp = max(1, (total + REPLAY_LIST_PER_PAGE - 1) // REPLAY_LIST_PER_PAGE)
        if REPLAY_LIST_PAGE >= total_pages_rp:
            REPLAY_LIST_PAGE = 0
        start = REPLAY_LIST_PAGE * REPLAY_LIST_PER_PAGE
        end = min(start + REPLAY_LIST_PER_PAGE, total)
        y = panel.y + 100
        for i in range(start, end):
            if i >= len(REPLAY_LIST):
                break
            r = REPLAY_LIST[i]
            card = pygame.Rect(panel.x + 40, y, 920, 56)
            done = (r["result"] == "win")
            pygame.draw.rect(screen, (40, 60, 80) if done else (60, 40, 40), card, border_radius=8)
            pygame.draw.rect(screen, (110, 230, 140) if done else (255, 90, 90), card, 2, border_radius=8)
            draw_text(screen, "🏆" if done else "💀", 26, (255, 255, 255), topleft=(card.x + 12, card.y + 14))
            map_name = MAPS[r["map_idx"]]["name"] if r["map_idx"] < len(MAPS) else "?"
            night = "🌙" if r["is_night"] else "☀"
            draw_text(screen, f"{r['user']}", 20, (255, 255, 255), topleft=(card.x + 60, card.y + 8))
            draw_text(screen, f"{night} {map_name} · {r['duration']:.1f}s · {r['frames']}帧 · +{r['gained']}币",
                      16, (180, 190, 210), topleft=(card.x + 60, card.y + 32))
            pb = pygame.Rect(card.right - 220, card.y + 10, 90, 36)
            draw_button(screen, pb, "▶ 播放", small=True)
            if pb.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
                if start_playback(r["path"]):
                    REPLAY_PANEL_OPEN = False
                    if REPLAY_PLAYBACK is not None:
                        apply_config(REPLAY_PLAYBACK.get("map_idx", 0),
                                     REPLAY_PLAYBACK.get("is_night", False))
            db = pygame.Rect(card.right - 120, card.y + 10, 90, 36)
            pygame.draw.rect(screen, (120, 40, 40), db, border_radius=8)
            pygame.draw.rect(screen, (200, 80, 80), db, 2, border_radius=8)
            draw_text(screen, "🗑 删除", 16, (255, 255, 255), center=db.center)
            if db.collidepoint(pygame.mouse.get_pos()) and pygame.mouse.get_pressed()[0]:
                delete_replay(r["path"])
            y += 64
    draw_text(screen, "按 P 关闭", 18, (150, 160, 175), center=(WIDTH // 2, panel.bottom - 15))

def draw_replay_playback(screen):
    if REPLAY_PLAYBACK is None:
        return
    frames = REPLAY_PLAYBACK.get("frames", [])
    if not frames:
        screen.fill((0, 0, 0))
        return
    idx = min(REPLAY_PLAYBACK_IDX, len(frames) - 1)
    f = frames[idx]
    st_view = {
        "players": [{"id": p["id"], "x": p["x"], "y": p["y"], "a": p["a"], "hp": p["hp"],
                     "maxhp": 100, "mag": 30, "res": 120, "cans": 0, "gold": 0,
                     "key": 0, "med": 0, "dmg": 25, "reload": 0, "shoot_cd": 0, "med_cd": 0,
                     "tasks": {"kill": 0, "collect": 0, "extract": 0}} for p in f.get("players", [])],
        "enemies": [{"x": e["x"], "y": e["y"], "hp": e["hp"], "elite": 0,
                     "type": e.get("type", "rusher")} for e in f.get("enemies", [])],
        "loots": [{"id": l["id"], "x": l["x"], "y": l["y"], "k": l["k"]} for l in f.get("loots", [])],
        "extract": 0, "result": "play", "in_zone": False,
        "doors_open": DOORS_OPEN, "merchant": None,
        "zoom_active": False, "zoom_level": 1.0}
    my_id = REPLAY_PLAYBACK.get("user", "?")
    me = None
    for p in st_view["players"]:
        if p["id"] == my_id:
            me = p
            break
    if me is None and st_view["players"]:
        me = st_view["players"][0]
    if me is None:
        screen.fill((0, 0, 0))
        return
    render_view(canvas, me["x"], me["y"], me["a"], st_view, my_id, 0)
    screen.blit(pygame.transform.smoothscale(canvas, (WIDTH, HEIGHT)), (0, 0))
    draw_panel(screen, pygame.Rect(16, 16, 600, 60))
    draw_text(screen, f"🎬 回放中 · {my_id}", 22, (100, 180, 255), topleft=(32, 22))
    draw_text(screen, f"时间 {REPLAY_PLAYBACK_TIME:.1f}s / {REPLAY_PLAYBACK.get('duration', 0):.1f}s",
              18, (200, 200, 200), topleft=(32, 48))
    total_dur = max(0.1, REPLAY_PLAYBACK.get("duration", 1))
    bar = pygame.Rect(WIDTH // 2 - 300, HEIGHT - 60, 600, 10)
    draw_bar(screen, bar, min(1.0, REPLAY_PLAYBACK_TIME / total_dur), (100, 180, 255))
    draw_text(screen, "1/2/4 倍速 · ← → 快退/快进 · ESC 退出",
              16, (200, 200, 200), center=(WIDTH // 2, HEIGHT - 30))

def draw_friends_panel(screen):
    draw_overlay(screen, 220)
    panel = pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 120, 600, 240)
    draw_panel(screen, panel, alpha=245, border=(120, 200, 255), radius=15)
    draw_text(screen, "👥 好友功能", 44, (120, 200, 255), center=(WIDTH // 2, HEIGHT // 2 - 50))
    draw_text(screen, "暂未开放，敬请期待！", 26, (200, 200, 200), center=(WIDTH // 2, HEIGHT // 2 + 10))
    draw_text(screen, "按 O 关闭", 18, (150, 160, 175), center=(WIDTH // 2, HEIGHT // 2 + 70))

def draw_menu(screen, url):
    global HELP_OPEN, SHOW_ROOM_LIST, SHOW_CREATE_ROOM, ALERT_MSG, ALERT_TIME, SETTINGS_OPEN
    global ACHIEVEMENT_OPEN, REPLAY_PANEL_OPEN, FRIENDS_OPEN, FRIEND_FOCUS
    if SHOW_ROOM_LIST:
        draw_room_list(screen)
        return
    if SHOW_CREATE_ROOM:
        draw_create_room(screen)
        return
    if HELP_OPEN and SETTINGS_OPEN:
        SETTINGS_OPEN = False
    if MENU_BG:
        screen.blit(MENU_BG, (0, 0))
    else:
        screen.fill((15, 18, 22))
    for ox, oy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,-2),(-2,2),(2,2)]:
        draw_text(screen, "八宝粥行动", 72, (0, 0, 0), center=(WIDTH // 2 + ox, 60 + oy))
    draw_text(screen, "八宝粥行动", 72, (255, 200, 100), center=(WIDTH // 2, 60))
    draw_text(screen, "BA BAO ZHOU ACTION", 24, (220, 225, 235), center=(WIDTH // 2, 110))
    btns = menu_buttons()
    draw_panel(screen, pygame.Rect(40, 110, 520, 380), alpha=140)
    draw_text(screen, "开始行动", 26, (255, 255, 255), center=(300, 130))
    draw_button(screen, btns["solo"], "单人模式")
    draw_button(screen, btns["join"], "加入游戏")
    draw_button(screen, btns["room_list"], "房间列表")
    draw_button(screen, btns["create_room"], "创建房间")
    draw_button(screen, btns["quit"], "退出游戏", small=True)
    draw_button(screen, btns["help"], "操作帮助", small=True)
    draw_button(screen, btns["more"], "⋯ 更多功能", small=True)
    draw_button(screen, btns["achievements"], "🏅 成就", small=True)
    draw_button(screen, btns["replays"], "🎬 回放", small=True)
    draw_button(screen, btns["friends"], "👥 好友", small=True)
    draw_panel(screen, pygame.Rect(40, 500, 520, 140), alpha=140)
    if not LOGIN_USER:
        ub = btns["user_box"]
        pygame.draw.rect(screen, (30, 34, 44), ub)
        pygame.draw.rect(screen, (255, 190, 80) if login_focus == "user" else (90, 100, 120), ub, 2, border_radius=6)
        draw_text(screen, login_user_text or "用户名", 20,
                  (255, 255, 255) if login_user_text else (120, 130, 150), topleft=(ub.x + 8, ub.y + 8))
        pb = btns["pass_box"]
        pygame.draw.rect(screen, (30, 34, 44), pb)
        pygame.draw.rect(screen, (255, 190, 80) if login_focus == "pass" else (90, 100, 120), pb, 2, border_radius=6)
        draw_text(screen, "*" * len(login_pass_text) or "密码", 20,
                  (255, 255, 255) if login_pass_text else (120, 130, 150), topleft=(pb.x + 8, pb.y + 8))
        draw_button(screen, btns["btn_register"], "注册", small=True)
        draw_button(screen, btns["btn_login"], "登录", small=True)
        if login_msg:
            draw_text(screen, login_msg, 20, (255, 215, 0), center=(300, 610))
    else:
        name_col = (255, 215, 100) if IS_VIP else (110, 230, 140)
        name_txt = f"👑 VIP {LOGIN_USER}" if IS_VIP else f"已登录：{LOGIN_USER}"
        draw_text(screen, name_txt, 22, name_col, topleft=(60, 510))
        draw_button(screen, btns["btn_logout"], "退出登录", small=True)
        ach = len(ACHIEVEMENTS["unlocked"])
        draw_text(screen, f"🏅 成就 {ach}/{len(ACHIEVEMENT_DEFS)}", 18, (255, 215, 100), topleft=(60, 545))
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
    draw_button(screen, btns["buy_dmg"], f"伤害+5 · 300币 · Lv{SAVE.get('dmg', 0)}", small=True)
    draw_button(screen, btns["buy_ammo"], f"备弹+15 · 100币 · Lv{SAVE.get('ammo', 0)}", small=True)
    draw_panel(screen, pygame.Rect(660, 480, 520, 150), alpha=140)
    draw_text(screen, "📋 每日任务", 22, (255, 215, 95), center=(920, 498))
    if DAILY_TASKS:
        for i, tid in enumerate(DAILY_TASKS.get("tasks", [])[:3]):
            tdef = get_task_def(tid)
            if not tdef:
                continue
            y = 520 + i * 36
            cur = DAILY_TASKS["progress"].get(tid, 0)
            done = cur >= tdef["target"]
            claimed = tid in DAILY_TASKS.get("claimed", [])
            col = (110, 230, 140) if claimed else ((255, 215, 95) if done else (200, 200, 200))
            draw_text(screen, f"{tdef['name']}：{tdef['desc']}", 15, col, topleft=(680, y + 4))
            draw_text(screen, f"{cur}/{tdef['target']}", 15, (180, 200, 180), topleft=(1030, y + 4))
            btn = pygame.Rect(1100, y, 60, 28)
            if claimed:
                pygame.draw.rect(screen, (60, 70, 60), btn, border_radius=6)
                draw_text(screen, "已领", 13, (140, 160, 140), center=btn.center)
            elif done:
                hov = btn.collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(screen, (60, 180, 100) if hov else (40, 130, 70), btn, border_radius=6)
                pygame.draw.rect(screen, (140, 230, 160), btn, 2, border_radius=6)
                draw_text(screen, "领取", 13, (255, 255, 255), center=btn.center)
            else:
                pygame.draw.rect(screen, (50, 55, 65), btn, border_radius=6)
                draw_text(screen, "未完成", 12, (120, 130, 145), center=btn.center)
    else:
        draw_text(screen, "加载中...", 18, (150, 150, 150), center=(920, 540))
    draw_text(screen, f"服务器：{url}", 16, (150, 160, 175), center=(WIDTH // 2, 700))
    draw_chat_menu(screen)
    if HELP_OPEN:
        draw_overlay(screen, 200)
        rect = pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 240, 600, 480)
        draw_panel(screen, rect, alpha=240, border=(255, 200, 100), radius=15)
        draw_text(screen, "操作指南", 36, (255, 200, 100), center=(WIDTH // 2, HEIGHT // 2 - 200))
        controls = [("W / A / S / D", "移动"), ("鼠标", "视角"),
                    ("左键/空格", "射击"), ("右键", "开镜"),
                    ("1~4", "切换武器"), ("R", "换弹"),
                    ("Q", "医疗包"), ("F", "手电筒"), ("E", "开门"),
                    ("Shift", "疾跑"), ("B", "商店"), ("TAB", "背包"),
                    ("回车", "聊天"), ("K", "成就"), ("P", "回放"),
                    ("O", "好友"), ("ESC", "返回")]
        for i, (key, desc) in enumerate(controls):
            y = HEIGHT // 2 - 160 + i * 24
            draw_text(screen, key, 18, (255, 215, 95), topleft=(WIDTH // 2 - 250, y))
            draw_text(screen, desc, 18, (220, 220, 220), topleft=(WIDTH // 2 - 50, y))
        draw_text(screen, "点击任意处关闭", 18, (150, 150, 150), center=(WIDTH // 2, HEIGHT // 2 + 210))
    if MORE_MENU_OPEN:
        _draw_more_panel(screen, btns)
    if SETTINGS_OPEN:
        draw_settings(screen)
    if ACHIEVEMENT_OPEN:
        draw_achievement_panel(screen)
    if REPLAY_PANEL_OPEN:
        draw_replay_panel(screen)
    if FRIENDS_OPEN:
        draw_friends_panel(screen)
    if ALERT_TIME > 0:
        draw_overlay(screen, 200)
        rect = pygame.Rect(WIDTH // 2 - 280, HEIGHT // 2 - 100, 560, 200)
        msg = ALERT_MSG or ""
        if "未开放" in msg or "暂未" in msg:
            title = "敬请期待"
            border_col = (255, 200, 100)
            title_col = (255, 215, 100)
        elif "请先登录" in msg or "登录" in msg:
            title = "需要登录"
            border_col = (255, 200, 100)
            title_col = (255, 215, 100)
        elif "已满" in msg or "失败" in msg or "错误" in msg or "不足" in msg:
            title = "操作失败"
            border_col = (255, 60, 60)
            title_col = (255, 80, 80)
        else:
            title = "提示"
            border_col = (120, 180, 255)
            title_col = (150, 200, 255)
        draw_panel(screen, rect, alpha=240, border=border_col, radius=15)
        draw_text(screen, title, 42, title_col, center=(WIDTH // 2, HEIGHT // 2 - 40))
        draw_text(screen, msg, 26, (255, 255, 255), center=(WIDTH // 2, HEIGHT // 2 + 20))
        draw_text(screen, f"剩余 {max(0, int(ALERT_TIME) + 1)} 秒", 18, (180, 180, 180),
                  center=(WIDTH // 2, HEIGHT // 2 + 60))
    draw_achievement_popups(screen)

def join_multiplayer_game():
    global MULTIPLAYER_MODE, MULTIPLAYER_GAME, ALERT_MSG, ALERT_TIME
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
            with REMOTE_SMOOTH_LOCK:
                REMOTE_SMOOTH.clear()
            VIEW["a"] = 0.0
            reset_feed()
            MULTIPLAYER_GAME = new_game([LOGIN_USER], CURRENT_MAP_IDX)
            CURRENT_GAME["multi"] = MULTIPLAYER_GAME
            start_recording(MULTIPLAYER_GAME, LOGIN_USER)
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

def main():
    global SHOP_VIP_OPEN, SHOP_VIP_SELECTED, VIP_LEVEL, VIP_EXPIRE, GOD_MENU_OPEN, MORE_MENU_OPEN
    global IS_VIP
    global canvas, login_user_text, login_pass_text, login_focus, FLASH_ON, MERCHANT_OPEN, ALERT_TIME, HELP_OPEN
    global MULTIPLAYER_MODE, MULTIPLAYER_GAME, LAST_SYNC_TIME, CURRENT_ROOM_ID
    global SHOW_ROOM_LIST, SHOW_CREATE_ROOM, CREATE_ROOM_NAME, CREATE_ROOM_PASSWORD
    global CREATE_ROOM_MAP, CREATE_ROOM_NIGHT, ROOM_LIST_PAGE, CREATE_FOCUS
    global mode, CHAT_FOCUS, SHOP_OPEN, SETTINGS_OPEN, SETTINGS_TAB, SETTINGS_REBIND
    global ACHIEVEMENT_OPEN, REPLAY_PANEL_OPEN, REPLAY_PLAYBACK, REPLAY_PLAYBACK_TIME, REPLAY_SPEED
    global BACKPACK_OPEN, FLASH_BATTERY, FRIENDS_OPEN, FRIEND_INPUT, FRIEND_FOCUS

    pygame.init()
    pygame.font.init()
    load_settings()
    load_achievements()
    load_friends()
    load_daily_tasks()
    start_ws_reconnect()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("八宝粥行动")
    clock = pygame.time.Clock()
    canvas = pygame.Surface((RES_W, RES_H))
    pygame.key.start_text_input()
    make_ui_assets()
    make_sounds()
    apply_settings()
    apply_config(0, False)
    url = SERVER_URL
    mode = "menu"
    solo_game = None
    running = True

    print("[系统] 八宝粥行动")
    print(f"[系统] 服务器: {SERVER_URL}")

    while running:
        dt = min(clock.tick(SETTINGS.get("fps_cap", 60)) / 1000.0, 0.05)
        if ALERT_TIME > 0:
            ALERT_TIME -= dt
        update_achievement_popups(dt)

        if FLASH_ON and mode in ("solo", "multiplayer"):
            if not IS_VIP:
                FLASH_BATTERY = max(0.0, FLASH_BATTERY - FLASH_DRAIN_RATE * dt)
            if FLASH_BATTERY <= 0:
                FLASH_ON = False
                add_text("🔦 手电筒没电了！")

        if REPLAY_PLAYBACK is not None:
            update_playback(dt)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        REPLAY_PLAYBACK = None
                    elif ev.key == pygame.K_1:
                        REPLAY_SPEED = 1.0
                    elif ev.key == pygame.K_2:
                        REPLAY_SPEED = 2.0
                    elif ev.key == pygame.K_4:
                        REPLAY_SPEED = 4.0
                    elif ev.key == pygame.K_LEFT:
                        REPLAY_PLAYBACK_TIME = max(0, REPLAY_PLAYBACK_TIME - 5)
                    elif ev.key == pygame.K_RIGHT:
                        REPLAY_PLAYBACK_TIME += 5
            draw_replay_playback(screen)
            pygame.display.flip()
            continue

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                stop_php_sync()
                stop_websocket()
                stop_ws_reconnect()
                save_settings()
                save_achievements()
                save_friends()
                if MULTIPLAYER_MODE and LOGIN_USER and CURRENT_ROOM_ID:
                    leave_room_async(CURRENT_ROOM_ID, LOGIN_USER)
            elif ev.type == pygame.KEYDOWN:
                typing_mode = (
                    CHAT_FOCUS or
                    FRIEND_FOCUS or
                    (not LOGIN_USER and mode == "menu") or
                    (SHOW_CREATE_ROOM and (CREATE_FOCUS == "name" or CREATE_FOCUS == "password"))
                )
                if SETTINGS_OPEN:
                    if SETTINGS_REBIND is not None:
                        if ev.key == pygame.K_ESCAPE:
                            SETTINGS_REBIND = None
                        else:
                            name = pygame_key_to_name(ev.key)
                            if name:
                                conflict = None
                                for ak, av in SETTINGS["keys"].items():
                                    if av == name and ak != SETTINGS_REBIND:
                                        conflict = ak
                                        break
                                if not conflict:
                                    SETTINGS["keys"][SETTINGS_REBIND] = name
                                    SETTINGS_REBIND = None
                        continue
                    if ev.key == pygame.K_ESCAPE:
                        SETTINGS_OPEN = False
                        save_settings()
                        continue
                if FRIENDS_OPEN and FRIEND_FOCUS:
                    if ev.key == pygame.K_BACKSPACE:
                        FRIEND_INPUT = FRIEND_INPUT[:-1]
                        continue
                    if ev.key == pygame.K_RETURN:
                        if FRIEND_INPUT.strip():
                            nm = FRIEND_INPUT.strip()
                            if nm == LOGIN_USER:
                                add_text("不能加自己")
                            elif nm in FRIENDS["list"]:
                                add_text("已经是好友了")
                            else:
                                FRIENDS["list"].append(nm)
                                save_friends()
                                add_text(f"✅ 已添加好友 {nm}")
                            FRIEND_INPUT = ""
                        continue
                    if ev.key == pygame.K_ESCAPE:
                        FRIENDS_OPEN = False
                        FRIEND_FOCUS = False
                        continue
                if CHAT_FOCUS:
                    chat_handle_keydown(ev)
                    continue
                if not typing_mode:
                    if mode == "menu":
                        if ev.key == pygame.K_k:
                            ACHIEVEMENT_OPEN = not ACHIEVEMENT_OPEN
                            continue
                        if ev.key == pygame.K_p:
                            REPLAY_PANEL_OPEN = not REPLAY_PANEL_OPEN
                            continue
                        if ev.key == pygame.K_o:
                            FRIENDS_OPEN = not FRIENDS_OPEN
                            FRIEND_FOCUS = False
                            continue
                    if mode in ("solo", "multiplayer"):
                        if ev.key == pygame.K_TAB:
                            BACKPACK_OPEN = not BACKPACK_OPEN
                            continue
                        if ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                            wkey = WEAPON_ORDER[ev.key - pygame.K_1]
                            g = CURRENT_GAME.get("solo") if mode == "solo" else CURRENT_GAME.get("multi")
                            if g:
                                p = g["players"].get(0) if mode == "solo" else g["players"].get(LOGIN_USER)
                                if p and wkey in p.get("equipped", []):
                                    p["current_weapon"] = wkey
                                    wdef2, wstate2 = get_current_weapon(p)
                                    p["mag"] = wstate2["mag"]
                                    p["res"] = wstate2["reserve"]
                                    add_text(f"切换到 {wdef2['name']}")
                                    play("reload")
                            continue
                if mode in ("solo", "multiplayer"):
                    if is_action_key("up", ev.key): KEY_STATE["w"] = True
                    elif is_action_key("left", ev.key): KEY_STATE["a"] = True
                    elif is_action_key("down", ev.key): KEY_STATE["s"] = True
                    elif is_action_key("right", ev.key): KEY_STATE["d"] = True
                    elif is_action_key("sprint", ev.key): KEY_STATE["shift"] = True
                    elif is_action_key("shoot", ev.key): KEY_STATE["space"] = True
                    elif is_action_key("reload", ev.key): KEY_STATE["r"] = True
                    elif is_action_key("use", ev.key): KEY_STATE["e"] = True
                    elif is_action_key("med", ev.key): KEY_STATE["q"] = True
                    elif is_action_key("flash", ev.key): FLASH_ON = not FLASH_ON
                    elif is_action_key("shop", ev.key):
                        SHOP_OPEN = not SHOP_OPEN
                        if SHOP_OPEN:
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                        else:
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                    elif is_action_key("back", ev.key):
                        if SHOP_OPEN:
                            SHOP_OPEN = False
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                        elif BACKPACK_OPEN:
                            BACKPACK_OPEN = False
                        else:
                            if mode == "multiplayer":
                                leave_multiplayer_game()
                            mode = "menu"
                            reset_feed()
                            MERCHANT_OPEN = False
                            SHOP_OPEN = False
                            BACKPACK_OPEN = False
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                if MORE_MENU_OPEN and ev.key == pygame.K_ESCAPE:
                    MORE_MENU_OPEN = False
                elif HELP_OPEN and ev.key == pygame.K_ESCAPE:
                    HELP_OPEN = False
                elif mode == "menu" and LOGIN_USER and not SHOW_ROOM_LIST and not SHOW_CREATE_ROOM and not HELP_OPEN and not SETTINGS_OPEN:
                    if is_action_key("chat", ev.key):
                        toggle_chat_focus()
                elif mode == "menu" and not LOGIN_USER:
                    if ev.key == pygame.K_TAB:
                        login_focus = "pass" if login_focus == "user" else "user"
                    elif ev.key == pygame.K_BACKSPACE:
                        if login_focus == "user": login_user_text = login_user_text[:-1]
                        else: login_pass_text = login_pass_text[:-1]
                    elif ev.key == pygame.K_RETURN:
                        do_login()
                elif SHOW_CREATE_ROOM:
                    if ev.key == pygame.K_ESCAPE:
                        SHOW_CREATE_ROOM = False
                        SHOW_ROOM_LIST = True
                    elif ev.key == pygame.K_BACKSPACE:
                        if CREATE_FOCUS == "name": CREATE_ROOM_NAME = CREATE_ROOM_NAME[:-1]
                        elif CREATE_FOCUS == "password": CREATE_ROOM_PASSWORD = CREATE_ROOM_PASSWORD[:-1]
                    elif ev.key == pygame.K_TAB:
                        CREATE_FOCUS = "password" if CREATE_FOCUS == "name" else "name"
                elif SHOW_ROOM_LIST:
                    if ev.key == pygame.K_ESCAPE:
                        SHOW_ROOM_LIST = False
                if mode == "solo" and solo_game and solo_game["result"] != "play" and ev.key == pygame.K_RETURN:
                    reset_game(solo_game)
                    VIEW["a"] = 0.0
                    reset_feed()
                    start_recording(solo_game, LOGIN_USER or "guest")
            elif ev.type == pygame.KEYUP:
                if is_action_key("up", ev.key): KEY_STATE["w"] = False
                elif is_action_key("left", ev.key): KEY_STATE["a"] = False
                elif is_action_key("down", ev.key): KEY_STATE["s"] = False
                elif is_action_key("right", ev.key): KEY_STATE["d"] = False
                elif is_action_key("sprint", ev.key): KEY_STATE["shift"] = False
                elif is_action_key("shoot", ev.key): KEY_STATE["space"] = False
                elif is_action_key("reload", ev.key): KEY_STATE["r"] = False
                elif is_action_key("use", ev.key): KEY_STATE["e"] = False
                elif is_action_key("med", ev.key): KEY_STATE["q"] = False
            elif ev.type == pygame.MOUSEMOTION:
                if mode in ("solo", "multiplayer") and not CHAT_FOCUS and not SHOP_OPEN and not SETTINGS_OPEN and not BACKPACK_OPEN:
                    dx, dy = ev.rel
                    VIEW["a"] += dx * MOUSE_SENS
            elif ev.type == pygame.TEXTINPUT:
                if CHAT_FOCUS:
                    chat_handle_textinput(ev.text)
                elif FRIENDS_OPEN and FRIEND_FOCUS:
                    FRIEND_INPUT += ev.text
                elif SHOW_CREATE_ROOM:
                    if CREATE_FOCUS == "name": CREATE_ROOM_NAME += ev.text
                    elif CREATE_FOCUS == "password": CREATE_ROOM_PASSWORD += ev.text
                elif mode == "menu" and not LOGIN_USER:
                    if login_focus == "user": login_user_text += ev.text
                    else: login_pass_text += ev.text
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if SETTINGS_OPEN or ACHIEVEMENT_OPEN or REPLAY_PANEL_OPEN or FRIENDS_OPEN or BACKPACK_OPEN:
                    continue
                pos = ev.pos
                stores = []
                if mode == "menu":
                    stores.append(CHAT_MENU_RECTS)
                elif mode in ("solo", "multiplayer"):
                    stores.append(CHAT_GAME_RECTS)
                handled = False
                for store in stores:
                    sr = store.get("send")
                    if sr and sr.collidepoint(pos) and LOGIN_USER:
                        if CHAT_INPUT.strip():
                            chat_send_message(CHAT_INPUT)
                        toggle_chat_focus()
                        handled = True
                        break
                    ir = store.get("input")
                    if ir and ir.collidepoint(pos) and LOGIN_USER:
                        if not CHAT_FOCUS:
                            toggle_chat_focus()
                        handled = True
                        break
                if handled:
                    continue
                if CHAT_FOCUS:
                    toggle_chat_focus()
                    continue
                if HELP_OPEN:
                    HELP_OPEN = False
                elif mode == "menu" and not SHOW_ROOM_LIST and not SHOW_CREATE_ROOM:
                    btns = menu_buttons()
                    if btns["user_box"].collidepoint(pos): login_focus = "user"
                    elif btns["pass_box"].collidepoint(pos): login_focus = "pass"
                    elif btns["btn_register"].collidepoint(pos): do_register()
                    elif btns["btn_login"].collidepoint(pos): do_login()
                    elif btns["btn_logout"].collidepoint(pos) and LOGIN_USER: do_logout()
                    elif btns["map_prev"].collidepoint(pos): apply_config(CURRENT_MAP_IDX - 1, IS_NIGHT)
                    elif btns["map_next"].collidepoint(pos): apply_config(CURRENT_MAP_IDX + 1, IS_NIGHT)
                    elif btns["toggle_night"].collidepoint(pos): apply_config(CURRENT_MAP_IDX, not IS_NIGHT)
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
                    elif DAILY_TASKS and any(
                        pygame.Rect(1100, 520 + i * 36, 60, 28).collidepoint(pos)
                        for i in range(len(DAILY_TASKS.get("tasks", [])[:3]))
                    ):
                        for i, tid in enumerate(DAILY_TASKS.get("tasks", [])[:3]):
                            btn = pygame.Rect(1100, 520 + i * 36, 60, 28)
                            if btn.collidepoint(pos):
                                ok, msg = task_claim(tid)
                                if not ok:
                                    add_text(f"❌ {msg}")
                                break
                    elif btns["more"].collidepoint(pos):
                        MORE_MENU_OPEN = True
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                    elif MORE_MENU_OPEN and more_menu_rects()["sub_achievements"].collidepoint(pos):
                        ACHIEVEMENT_OPEN = True
                        MORE_MENU_OPEN = False
                    elif MORE_MENU_OPEN and more_menu_rects()["sub_replays"].collidepoint(pos):
                        REPLAY_PANEL_OPEN = True
                        MORE_MENU_OPEN = False
                    elif MORE_MENU_OPEN and more_menu_rects()["sub_friends"].collidepoint(pos):
                        FRIENDS_OPEN = True
                        MORE_MENU_OPEN = False
                    elif MORE_MENU_OPEN and more_menu_rects()["sub_buy_vip"].collidepoint(pos):
                        IS_VIP = not IS_VIP
                        MORE_MENU_OPEN = False
                        if IS_VIP:
                            ALERT_MSG = "VIP 已开通！享受 1.5 倍伤害 / 双倍收益 / 全武器"
                        else:
                            ALERT_MSG = "VIP 已关闭"
                        ALERT_TIME = 2.0
                    elif MORE_MENU_OPEN and more_menu_rects()["sub_settings"].collidepoint(pos):
                        HELP_OPEN = False
                        SETTINGS_OPEN = True
                        SETTINGS_TAB = "general"
                        SETTINGS_REBIND = None
                        MORE_MENU_OPEN = False
                    elif MORE_MENU_OPEN and more_menu_rects()["sub_close"].collidepoint(pos):
                        MORE_MENU_OPEN = False
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                    elif btns["help"].collidepoint(pos):
                        SETTINGS_OPEN = False
                        HELP_OPEN = True
                    elif btns["achievements"].collidepoint(pos):
                        ACHIEVEMENT_OPEN = True
                    elif btns["replays"].collidepoint(pos):
                        REPLAY_PANEL_OPEN = True
                    elif btns["friends"].collidepoint(pos):
                        FRIENDS_OPEN = True
                    elif btns["join"].collidepoint(pos):
                        if join_multiplayer_game():
                            mode = "multiplayer"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
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
                            CURRENT_GAME["solo"] = solo_game
                            start_recording(solo_game, LOGIN_USER)
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
                        save_settings()
                        save_achievements()
                        save_friends()

        if mode == "menu":
            draw_menu(screen, url)
        elif mode == "solo":
            p = solo_game["players"][0]
            m = solo_game.get("merchant")
            if m and math.hypot(m["x"] - p["x"], m["y"] - p["y"]) < 80:
                p["merchant_near"] = True
            else:
                p["merchant_near"] = False
            if p.get("merchant_near") and KEY_STATE["e"]:
                MERCHANT_OPEN = True
            elif not p.get("merchant_near"):
                MERCHANT_OPEN = False
            solo_game["inputs"][0] = read_input(p["x"], p["y"], dt)
            if not SHOP_OPEN and not BACKPACK_OPEN:
                server_update(solo_game, dt)
                record_frame(solo_game, LOGIN_USER or "guest", dt)
            st = make_state(solo_game)
            draw_world(screen, st, 0, True, dt, solo_game)
        elif mode == "multiplayer":
            if MULTIPLAYER_GAME is None:
                MULTIPLAYER_GAME = new_game([LOGIN_USER], CURRENT_MAP_IDX)
                CURRENT_GAME["multi"] = MULTIPLAYER_GAME
                start_recording(MULTIPLAYER_GAME, LOGIN_USER)
            p = MULTIPLAYER_GAME["players"].get(LOGIN_USER)
            if not p or p["hp"] <= 0:
                if MULTIPLAYER_GAME["result"] == "lose":
                    draw_overlay(screen, 200)
                    draw_panel(screen, pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 100, 400, 200),
                               alpha=240, border=(255, 90, 90))
                    draw_text(screen, "你已阵亡", 48, (255, 90, 90), center=(WIDTH // 2, HEIGHT // 2 - 30))
                    draw_text(screen, "按 ESC 返回菜单", 24, (200, 200, 200), center=(WIDTH // 2, HEIGHT // 2 + 40))
                    pygame.display.flip()
                    continue
            inp = read_input(p["x"], p["y"], dt)
            MULTIPLAYER_GAME["inputs"][LOGIN_USER] = inp
            if not SHOP_OPEN and not BACKPACK_OPEN:
                server_update(MULTIPLAYER_GAME, dt)
                record_frame(MULTIPLAYER_GAME, LOGIN_USER, dt)
            st = make_state(MULTIPLAYER_GAME)
            room_status = get_cached_room_status()
            is_host = False
            if room_status and room_status.get('success'):
                is_host = (LOGIN_USER == room_status.get('host', ''))
            draw_world(screen, st, LOGIN_USER, is_host, dt, MULTIPLAYER_GAME)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
