# -*- coding: utf-8 -*-
"""Игровая логика: меню, ангар, раунды, бонусы, мины/дым/лазер, HUD."""
import math
import json
import os
import random
import time
import pygame
from settings import (SCREEN_W, SCREEN_H, FPS, TITLE, COL_TEXT, COL_DIM,
                      COL_P1, COL_P2, COL_GOLD, ROUNDS_TO_WIN, ROUND_BANNER_T,
                      ROUND_PAUSE_T, CHASSIS, HULL, WEAPONS, PERKS, ELEMENTS,
                      CURSES, BLESSINGS, ENEMY_EFFECTS,
                      TANK_RADIUS, BULLET_BOUNCES,
                      SPECTATE_T,
                      ALLY_COLOR, BOSS_COLOR, BOSS_BUILD, BOSS_HP_MULT,
                      BOSS_SCALE, TEAM_FOE_COLOR, TEAM_ALLY_COLOR,
                      BOT_COLORS, BOT_NAMES, MODE_NAMES,
                      BULLET_DAMAGE,
                      POWERUP_INTERVAL, POWERUP_MAX, PU_MINE_DAMAGE,
                      PU_MINE_RADIUS, PU_MINE_MAX, PU_LASER_DAMAGE,
                      PU_LASER_FAN_DAMAGE, PU_LASER_FAN_SPREAD,
                      PU_SMOKE_TIME, PU_SMOKE_RADIUS, PU_FREEZE_TIME,
                      PU_MINE_ENEMY_DIST,
                      BARRIER_HP, BARRIER_LEN, BARRIER_THICK,
                      BARRIER_DIST, BARRIER_MAX,
                      WALL_TIERS, WALL_TIER_ORDER,
                      WALL_REPAIR_RATE, WALL_REPAIR_DIST,
                      TURRET_DAMAGE, PU_TURRET_MAX, TURRET_CARRY,
                      TURRET_COOLDOWN,
                      ASSAULT_MODES, ASSAULT_POINT_R, ASSAULT_CAPTURE_T,
                      ASSAULT_HOLD_T, ASSAULT_KIT_WALLS, ASSAULT_KIT_TURRETS,
                      ASSAULT_KIT_MINES,
                      STAR_SHARDS, STAR_SHARD_DAMAGE, STAR_SHARD_LIFE,
                      STAR_SHARD_SPEED_MULT,
                      SHELL_STAR_DAMAGE_MULT,
                      CMD_PERIOD_MIN, CMD_PERIOD_MAX, CMD_HOLD_MIN,
                      CMD_HOLD_MAX, CMD_REACT_T,
                      HE_SPLASH_DAMAGE, HE_SPLASH_RADIUS,
                      BUILDS, BUILD_KEYS, EMP_CHARGE_BUILD,
                      NOVA_SHELLS, NOVA_DAMAGE_MULT,
                      SHELL_STAR_DAMAGE_MULT,
                      SHELL_TYPES, SHELL_KEYS, SHELL_BOT_WEIGHTS,
                      FIRE_ZONE_RADIUS, FIRE_ZONE_LIFE, FIRE_ZONE_DPS,
                      SHELL_AP_RELOAD_MULT,
                      SCORE_CURSE_BONUS, SCORE_BLESS_PENALTY, SCORE_MULT_FLOOR,
                      ICE_TIME, ICE_IMMUNE_T, POISON_TIME, POISON_DPS, VAMP_HEAL_RATIO,
                      SCORE_ROUND_WIN, SCORE_ROUND_DRAW, SCORE_MATCH_WIN,
                      SCORE_PICKUP,
                      DIFF_PRESETS, BOT_DIFFICULTY)
from arena import (Arena, LAYOUTS, WALL_T, ASSAULT_MAPS, EMPTY_VARIANT,
                   load_custom_maps, save_custom_map,
                   load_custom_battle_maps, save_custom_battle_map,
                   EDITOR_COLS, EDITOR_ROWS, EDITOR_CELL)
from tank import Tank
from bot import BotAI, random_build
from powerup import PowerUp, Mine, PU_INFO
from turret import Turret
from bullet import Bullet
from effects import Effects, get_font
from sound import SoundBank

# моды БОССА (режим «2 против босса»): крепкий, злой, неповоротливый
BOSS_MODS = {"hp_mult": BOSS_HP_MULT, "damage_mult": 1.3,
             "turn_mult": 0.8, "speed_mult": 0.9}

# v2.7/v2.8: какие режимы КОМАНДНЫЕ (счёт на две стороны: наша против
# чужой), а какие — «АРМЕЙСКИЕ» (12-20 танков на самых больших картах).
# В FFA (2-5, 11-15) team_mode выключен — у каждого танка свой team-номер.
# v3.2: ШТУРМ 21-27 тоже командный (ОБОРОНА игрока против АТАКИ ботов).
TEAM_MODES = ((6, 7, 8, 9, 10, 16, 17, 18, 19, 20) + ASSAULT_MODES)
ARMY_MODES = (16, 17, 18, 19, 20)

CH_KEYS = list(CHASSIS)
HU_KEYS = list(HULL)
WP_KEYS = list(WEAPONS)
PK_KEYS = list(PERKS)
EL_KEYS = list(ELEMENTS)
CR_KEYS = list(CURSES)
BL_KEYS = list(BLESSINGS)
EE_KEYS = list(ENEMY_EFFECTS)
JT_TOTAL = len(CR_KEYS) + len(BL_KEYS)   # карт жребия: 8 проклятий + 8 облегчений
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "duel_stats.json")
DIFF_NAMES = {1: "Лёгкий", 2: "Норм", 3: "Хардкор"}


def _wrap_px(text, font, maxw):
    """Разбивает строку на несколько, чтобы влезла в maxw пикселей."""
    if font.size(text)[0] <= maxw:
        return [text]
    words = text.split()
    if not words:
        return [text]
    lines, cur = [], words[0]
    for w in words[1:]:
        t = cur + " " + w
        if font.size(t)[0] <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


class Smoke:
    """Дымовая завеса: скрывает всё, что внутри (бот сквозь неё не видит)."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 0.0
        self.life = PU_SMOKE_TIME

    @property
    def radius(self):
        grow = min(1.0, self.t / 0.7)
        return PU_SMOKE_RADIUS * (0.35 + 0.65 * grow)

    def update(self, dt):
        self.t += dt
        self.life -= dt

    def draw(self, surf, ox=0, oy=0):
        r = self.radius
        size = int(r * 2)
        if size < 8:
            return
        cloud = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(14):
            a = i * 0.45 + math.sin(self.t * 1.3 + i) * 0.2
            rr = r * (0.35 + 0.25 * ((i % 3) / 2.0))
            px = size / 2 + math.cos(a) * r * 0.42
            py = size / 2 + math.sin(a) * r * 0.42
            pygame.draw.circle(cloud, (150, 158, 175, 60), (int(px), int(py)), int(rr))
        surf.blit(cloud, (int(self.x - size / 2 + ox), int(self.y - size / 2 + oy)))


def _seg_circle(x1, y1, x2, y2, cx, cy, r):
    """Пересекает ли отрезок круг (для зрения сквозь дым)."""
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return (x1 - cx) ** 2 + (y1 - cy) ** 2 < r * r
    t = ((cx - x1) * dx + (cy - y1) * dy) / l2
    t = max(0.0, min(1.0, t))
    px, py = x1 + t * dx, y1 + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2 < r * r


def _pt_seg_dist(px, py, p1, p2):
    """Расстояние от точки до отрезка (для коллизий со стеной-барьером)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - p1[0], py - p1[1])
    t = ((px - p1[0]) * dx + (py - p1[1]) * dy) / l2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (p1[0] + t * dx), py - (p1[1] + t * dy))


class Barrier:
    """Стена-бустер: ставится танком по Q, блокирует танки и взгляд,
    пробивается снарядами.
    v3.0: ПОСТОЯННАЯ — таймера жизни больше нет (по просьбе игрока:
    «почему стены временные? не дело»): лежит, пока её не разнесут.
    v3.2: ЯРУСЫ ПРОЧНОСТИ — обычная (120), ПРОЧНАЯ (переживает 8 самых
    злых выстрелов игры), ОЧЕНЬ ПРОЧНАЯ (12) и НЕВЕРОЯТНО ПРОЧНАЯ (16).
    Ярус задаёт прочность, цвет и цену попадания (она везде одинакова —
    каждый снаряд снимает свой урон).
    v3.3: КАЗЁННЫЕ СТЕНЫ — у стен здания ШТУРМА владелец None, а в team
    записана сторона обороны: такую стену чинят только защитники."""

    def __init__(self, x, y, angle_deg, owner, tier="std", team=None):
        self.x, self.y = float(x), float(y)
        self.owner = owner
        self.team = team   # None — личная стена (смотрим на owner), int — казённая
        self.tier = tier if tier in WALL_TIERS else "std"
        rad = math.radians(angle_deg)
        hl = BARRIER_LEN / 2
        self.p1 = (x - math.cos(rad) * hl, y - math.sin(rad) * hl)
        self.p2 = (x + math.cos(rad) * hl, y + math.sin(rad) * hl)
        self.max_hp = WALL_TIERS[self.tier]["hp"]
        self.hp = self.max_hp
        self.t = 0.0

    def _dist(self, px, py):
        return _pt_seg_dist(px, py, self.p1, self.p2)

    def blocks_circle(self, px, py, r):
        return self._dist(px, py) < r + BARRIER_THICK / 2

    def blocks_point(self, px, py):
        return self._dist(px, py) < BARRIER_THICK / 2 + 1

    def update(self, dt):
        self.t += dt

    def expired(self):
        return False   # v3.0: стены постоянные — гибнут только от снарядов

    def draw(self, surf, ox=0, oy=0):
        ax, ay = self.p1[0] + ox, self.p1[1] + oy
        bx, by = self.p2[0] + ox, self.p2[1] + oy
        k = self.hp / self.max_hp
        tier_col = WALL_TIERS[self.tier]["color"]
        if k > 0.5:
            core = tier_col
        else:
            core = (235, 150, 80)   # треснула — вот-вот развалится
        pygame.draw.line(surf, (52, 58, 84), (ax, ay), (bx, by), BARRIER_THICK + 6)
        pygame.draw.line(surf, (86, 96, 150), (ax, ay), (bx, by), BARRIER_THICK)
        pygame.draw.line(surf, core, (ax, ay), (bx, by), 4)
        for px, py in ((ax, ay), (bx, by)):
            pygame.draw.circle(surf, core, (int(px), int(py)), 4)
        # v3.2: у прочных стен — полоска прочности, пока они потрёпаны
        if k < 0.999:
            mx, my = (ax + bx) / 2, (ay + by) / 2
            w = 34
            r = pygame.Rect(int(mx - w / 2), int(my + BARRIER_THICK / 2 + 4),
                            w, 4)
            pygame.draw.rect(surf, (30, 36, 60), r, border_radius=2)
            f = r.copy()
            f.w = max(0, int(w * k))
            if f.w > 0:
                pygame.draw.rect(surf, core, f, border_radius=2)


class FireZone:
    """ОГНЕННАЯ ЛУЖА (v3.0): остаётся на месте гибели зажигательного
    снаряда. Жжёт всех ЧУЖИХ, кто в неё встал (владелец и его команда
    целы), урон в секунду — броня не спасает, как у поджога."""

    def __init__(self, x, y, owner):
        self.x, self.y = float(x), float(y)
        self.owner = owner
        self.team = owner.team
        self.t = 0.0
        self.life = FIRE_ZONE_LIFE
        self.radius = FIRE_ZONE_RADIUS
        self._tick = 0.0

    def expired(self):
        return self.life <= 0

    def step(self, dt, game):
        """Тикает уроном по чужим танкам в луже (каждые полсекунды)."""
        self.t += dt
        self.life -= dt
        self._tick -= dt
        if self._tick > 0:
            return
        self._tick = 0.5
        for t in game.tanks:
            if (not t.alive or t is self.owner
                    or getattr(t, "team", None) == self.team):
                continue
            if (t.x - self.x) ** 2 + (t.y - self.y) ** 2 < self.radius ** 2:
                t.hp -= FIRE_ZONE_DPS * 0.5   # броня не спасает — как поджог
                game.effects.burst(t.x, t.y, (255, 110, 0), 4, 110, 0.3, 3)
                if t.hp <= 0:
                    t._die(game.effects, game.sounds)

    def draw(self, surf, ox=0, oy=0):
        x, y = int(self.x + ox), int(self.y + oy)
        fade = max(0.25, min(1.0, self.life / FIRE_ZONE_LIFE * 1.4))
        # пляшущие языки пламени
        for i in range(6):
            a = i * 1.047 + self.t * (2.2 if i % 2 else -1.7)
            rr = self.radius * (0.28 + 0.16 * ((i % 3) / 2.0))
            fx = x + math.cos(a) * self.radius * 0.42
            fy = y + math.sin(a) * self.radius * 0.42
            col = (255, 120 + int(60 * fade), 20) if i % 2 else (255, 180, 40)
            pygame.draw.circle(surf, col, (int(fx), int(fy)), int(rr))
        pygame.draw.circle(surf, (255, 70 + int(80 * fade), 20), (x, y),
                           int(self.radius * 0.5), 2)


def _wrap_tags(tags, font, maxw, max_rows=None):
    """v3.1: группирует теги статусов в НЕСКОЛЬКО строк не длиннее maxw px
    (раньше всё склеивалось в одну строку, которая улетала за экран и
    налезала на блок врага). max_rows — потолок строк: лишнее прячется
    под «…» (для сжатых строк ботов, где вертикали нет)."""
    rows, cur = [], []
    for tg in tags:
        probe = "   ".join(cur + [tg])
        if cur and font.size(probe)[0] > maxw:
            rows.append(cur)
            cur = [tg]
        else:
            cur.append(tg)
    if cur:
        rows.append(cur)
    if max_rows is not None and len(rows) > max_rows:
        rows = rows[:max_rows]
        rows[-1] = rows[-1] + ["…"]
    return rows


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.sounds = SoundBank()
        self.arena = Arena()
        self.effects = Effects()
        self.world = pygame.Surface((SCREEN_W, SCREEN_H))  # сюда рисуем бой

        # состояние
        self.state = "menu"       # menu/select/table/intro/fight/round_end/match_end/pause
        self.timer = 0.0
        # режим боя (v2.1): сколько танков на арене — 2..5, каждый сам за себя
        self.mode = 2
        # сборка игрока: шасси, корпус, дуло, перк, стихия,
        # проклятья, облегчения, эффекты НА ВРАГА
        self.build = ("medium", "medium", "standard", "none", "none", (), (), ())
        self.bot_builds = []                # сборка каждого бота на матч
        self.sel_ch, self.sel_hu = 1, 1     # курсоры в ангаре
        self.sel_wpn, self.sel_pk, self.sel_el = 0, 0, 0
        self.sel_jt = 0                     # курсор жребия (0..15)
        self.sel_curses = []                # взятые проклятья (ключи)
        self.sel_blessings = []             # взятые облегчения (ключи)
        self.sel_en = 0                     # курсор эффектов на врага
        self.sel_enemy_keys = []            # взятые эффекты НА ВРАГА (ключи)
        self.score = [0, 0]                 # победы: score[0] — игрок, дальше боты
        self.round = 1
        self.winner = 0
        self.difficulty = BOT_DIFFICULTY
        # очки за матч (сырые), множитель жребия и итог
        self.points = 0.0
        self.score_mult = 1.0
        self.final_score = 0
        # таблица счёта: место забега и флаг рекорда после матча
        self.table_place = 0
        self.new_record = False
        self._table_from = "menu"          # куда возвращаться из таблицы

        # объекты боя
        self.player = None
        self.bot_tank = None      # первый бот (в 1на1 — единственный)
        self.ai = None            # его ИИ
        self.tanks = []           # ВСЕ танки раунда: игрок + боты (v2.1)
        self.bots = []
        self.ais = []
        self.bullets = []
        self.powerups = []
        self.mines = []
        self.smokes = []
        self.barriers = []
        self.turrets = []               # v2.9: размещаемые турели
        self.fire_zones = []            # v3.0: огненные лужи
        # v3.2: ШТУРМ — точка захвата, прогресс и таймер обороны
        self.is_assault = False
        self.cap_xy = (0.0, 0.0)
        self.cap_progress = 0.0         # 0..ASSAULT_CAPTURE_T — на сколько захватили
        self.cap_hold = ASSAULT_HOLD_T  # сколько обороне ещё держаться
        self._repair_fx = 0.0           # троттлер искр ремонта стен
        self.powerup_t = POWERUP_INTERVAL * 0.6
        # v2.9: стартовый билд (индекс в BUILD_KEYS или None — «без билда»),
        # выбирается в ангаре; максимум ОДИН билд на танк
        self.sel_build = None
        # v3.0: тип снаряда (индекс в SHELL_KEYS) — четвертая часть сборки
        self.sel_shell = 0
        # v3.0: СПЕКТАТОР — после смерти игрока камера следует за живым
        # танком; ←/→ (или A/D/Space) переключают, ЗА КЕМ смотреть
        self.spec_target = None
        # v3.6: ОКНО ПРИКАЗОВ — открывается на E (Shift+E — сразу цель
        # «вся команда»); в окне 1–8 — приказы, плитки/Tab — выбор бота
        self.orders_open = False
        self.orders_all = False
        self.orders_pick = set()   # выбранные в окне боты (клик/Tab)

        self._fake_keys = None  # только для автотестов
        # мышь: кликабельные зоны текущего кадра и позиция курсора
        self._click_zones = []
        self._mouse = (0, 0)
        # тултип: (заголовок, цвет, [строки]) — появляется при наведении
        # на карточку в ангаре и рисуется ПОВЕРХ всего в конце кадра
        self._tooltip = None
        # v2.2: мир больше окна — камера следует за игроком
        self.cam = [0.0, 0.0]
        # v2.5: после смерти игрока боты выясняют победителя SPECTATE_T сек
        self.spectate_t = 0.0
        # v2.2: командные режимы (2на2, босс) — команда каждого танка
        # и список врагов (для очков, таймера v2.5 и кнопки «УБИТЬ СРАЗУ»)
        self.team_mode = False
        self.tank_team = {}
        self.foes = []
        # v3.3: КРЕПОСТЬ — выбор стороны в ШТУРМЕ («можно выбирать атака
        # ты или оборона»): 'def' | 'atk' | 'rand' (случайно на матч).
        # Команды решаются на старт матча: assault_def_team — кто держит
        # здание, assault_atk_team — кто штурмует. Игрок ВСЕГДА в команде 0.
        self.assault_side = "def"
        self.assault_def_team = 0
        self.assault_atk_team = 1
        self._assault_slots = None    # (спавны защиты, спавны атаки)
        self._assault_build = None    # сегменты казённых стен карты
        self._assault_name = ""       # имя штурмовой карты для HUD
        # v3.3: РЕДАКТОР КАРТ — сетка 27×48 символов и текущий инструмент
        # v3.4: ДВА типа своих карт — «assault» (ШТУРМ) и «battle» (FFA и
        # командные): у каждого своя сетка, сохранились между визитами
        self.ed_kind = "assault"
        self.ed_grids = {"assault": None, "battle": None}
        self.ed_tool = "#"
        self.ed_msg = ""
        # v3.4: КОМАНДИР — таймер приказов вражеского командира;
        # своя БОЕВАЯ карта текущего раунда (None — встроенная раскладка)
        self.cmd_t = 5.0
        self._battle_custom = None
        self.prefer_battle_map = None   # только для автотестов
        # v2.2: КОНСОЛЬ РАЗРАБОТЧИКА — открывается на Ё (`)
        self.con_open = False
        self.con_input = ""
        self.con_lines = ["КОНСОЛЬ РАЗРАБОТЧИКА · напиши «помощь» — покажу команды",
                          "предметы выдаются так: «Огонь Игрок», «Гаубица Бот», «Веер»"]
        self.con_hist = []
        self.con_hist_i = 0
        self.con_scroll = 0        # v3.6: прокрутка истории (колесо/PgUp)
        self.con_place = None      # ждём клик, чтобы поставить бонус на карту
        self._con_blink = 0.0
        self._con_reg = self._con_build_registry()
        self.stats = self._load_stats()

    # ================= статистика матчей =================
    def _load_stats(self):
        st = {"wins": 0, "losses": 0, "draws": 0, "best_score": 0,
              "score_table": []}
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            st["wins"] = int(d.get("wins", 0))
            st["losses"] = int(d.get("losses", 0))
            st["draws"] = int(d.get("draws", 0))
            st["best_score"] = int(d.get("best_score", 0))
            rows = d.get("score_table", [])
            if isinstance(rows, list):
                st["score_table"] = [r for r in rows
                                     if isinstance(r, dict) and "score" in r]
                st["score_table"].sort(key=lambda r: -int(r["score"]))
                del st["score_table"][10:]      # держим топ-10
        except Exception:
            pass
        return st

    def _save_stats(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f)
        except Exception:
            pass

    # ================= создание боя =================
    def _tank_count(self):
        """Сколько танков выезжает: в FFA номер режима = число танков
        (2..5 и большие FFA v2.7: 11…15 → 6…10), в командах
        6 = «2 на 2» (4 танка), 7 = «2 против босса» (3 танка),
        8 = «3 на 3» (6 танков), 9 = «4 на 4» (8 танков),
        10 = «5 на 5» (10 танков, v2.5),
        v2.8 — армейские: 16 = «6 на 6» (12), 17 = «7 на 7» (14),
        18 = «8 на 8» (16), 19 = «9 на 9» (18), 20 = «10 на 10» (20).
        v3.2 — ШТУРМ: 21…27 = n на n (n = 1…7): оборона против атаки."""
        return {6: 4, 7: 3, 8: 6, 9: 8, 10: 10,
                11: 6, 12: 7, 13: 8, 14: 9, 15: 10,
                16: 12, 17: 14, 18: 16, 19: 18, 20: 20,
                21: 2, 22: 4, 23: 6, 24: 8, 25: 10, 26: 12, 27: 14
                }.get(self.mode, self.mode)

    def _pick_battle_map(self):
        """v3.4: карта для ОБЫЧНЫХ режимов — обычно случайная из
        встроенных раскладок, но СВОИ БОЕВЫЕ карты редактора
        (custom_battle_*.txt) играют наравне (с двойным весом)."""
        if self.prefer_battle_map is not None:      # крючок автотестов
            return self.prefer_battle_map
        bmaps = load_custom_battle_maps()
        if not bmaps:
            return None
        # вес каждой своей карты = 2 встроенные раскладки
        if random.randrange(len(LAYOUTS) + 2 * len(bmaps)) >= len(LAYOUTS):
            return random.choice(bmaps)
        return None

    def _pad_battle_slot(self, slots, taken):
        """v3.4: дополнительный слот на БОЕВОЙ карте — свободное место
        рядом с уже имеющимися слотами этой стороны."""
        base = slots[-1] if slots else (self.arena.w / 2.0, self.arena.h / 2.0)
        for _ in range(120):
            a = random.uniform(0, 2 * math.pi)
            d = random.uniform(60, 300)
            nx, ny = base[0] + math.cos(a) * d, base[1] + math.sin(a) * d
            if not (self.arena.wall_t + 60 < nx < self.arena.w - self.arena.wall_t - 60
                    and self.arena.wall_t + 60 < ny < self.arena.h - self.arena.wall_t - 60):
                continue
            if self.arena.circle_collides(nx, ny, TANK_RADIUS + 12):
                continue
            if all(math.hypot(nx - tx, ny - ty) > 100 for tx, ty in taken):
                return (nx, ny)
        return self._free_spawn(base[0], base[1], taken)

    def _custom_battle_spawns(self, n):
        """v3.4: точки появления на СВОЕЙ БОЕВОЙ карте: в командах —
        союзники на спавнах D, враги на спавнах A; в FFA все слоты
        D и A — общий набор точек появления. Слотов не хватает —
        добиваем свободными местами рядом."""
        dsl, asl = (self._battle_custom["spawns_d"],
                    self._battle_custom["spawns_a"])
        if self.team_mode:
            our = 2 if self.mode == 7 else n // 2
            foes_n = n - our
            ours = list(dsl[:our])
            taken = list(ours)
            while len(ours) < our:
                p = self._pad_battle_slot(dsl, taken)
                ours.append(p)
                taken.append(p)
            foes = list(asl[:foes_n])
            taken = list(taken) + list(foes)
            while len(foes) < foes_n:
                p = self._pad_battle_slot(asl, taken)
                foes.append(p)
                taken.append(p)
            ring = ours + foes
        else:
            all_slots = list(dsl) + list(asl)
            ring = all_slots[:n]
            while len(ring) < n:
                p = self._pad_battle_slot(all_slots, ring)
                ring.append(p)
        out = []
        for x, y in ring:
            out.append(self._assault_spawn(x, y, out))
        return out

    def _spawn_points(self, n):
        """Точки появления для n танков: 1вс1 — классика по краям, FFA —
        кольцо вокруг центра большого мира, КОМАНДЫ (v2.3) — двумя
        шеренгами: наша снизу, чужая сверху. Точки без стен и
        подальше друг от друга.
        v3.3: ШТУРМ — слоты штурмовой карты: защитники ВНУТРИ здания
        (кольцо вокруг точки), атакующие — шеренгой снаружи. Своя
        сторона — первой: pts[0] всегда у игрока."""
        cx, cy = self.arena.w / 2.0, self.arena.h / 2.0
        if self._battle_custom is not None:
            # v3.4: СВОЯ БОЕВАЯ карта — спавны с неё (FFA и командные)
            return self._custom_battle_spawns(n)
        if n == 2 and self.mode not in ASSAULT_MODES:
            ring = [(cx - 520, cy), (cx + 520, cy)]
        elif self.mode in ASSAULT_MODES:
            our = n // 2
            foes_n = n - our
            mine, theirs = (self._assault_slots
                            if self.assault_def_team == 0
                            else (self._assault_slots[1], self._assault_slots[0]))
            ring = list(mine[:our]) + list(theirs[:foes_n])
            # разводим спавны: каждому — свободное место рядом со слотом
            taken = []
            out = []
            for x, y in ring:
                p = self._assault_spawn(x, y, taken)
                out.append(p)
                taken.append(p)
            return out
        elif self.mode in TEAM_MODES:
            # командные режимы: наша команда — нижняя шеренга,
            # чужая — верхняя (сразу видно, кто с кем)
            if self.mode == 7:          # 2 против босса: нас двое, он один
                our, foes_n = 2, 1
            else:
                our = n // 2            # 2на2 → 2, 6на6 → 6, 10на10 → 10
                foes_n = our
            # v2.5: отступ шеренг = треть ВЫСОТЫ командной карты (729 при 2187) —
            # тянется вслед за размером; до стен (182) и блоков остаётся
            # запас даже под БОССА (r 48+14)
            row = self.arena.h / 3.0
            our_pts = [(cx, cy + row)]
            for j in range(our - 1):    # союзники веером вокруг игрока
                off = (j // 2 + 1) * 300 * (1 if j % 2 == 0 else -1)
                our_pts.append((cx + off, cy + row))
            foe_pts = [(cx + (j - (foes_n - 1) / 2.0) * 300, cy - row)
                       for j in range(foes_n)]
            ring = our_pts + foe_pts
        else:
            # FFA-кольцо вокруг центра; v2.7: большие FFA (6-10 танков)
            # стоят на КРУПНЫХ картах — радиус больше, чтобы по 240 px
            # между танками оставалось и без рандомного раскидывания
            rr = 380 if self.arena.w <= 3000 else 620
            ring = []
            for i in range(n):
                a = math.radians(90 + i * 360.0 / n)   # игрок — снизу
                ring.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        out = []
        for x, y in ring:
            out.append(self._free_spawn(x, y, out))
        return out

    def _free_spawn(self, x, y, taken):
        """Точка появления без стен и не ближе 240 px к уже занятым.
        Clearance с запасом под БОССА (его радиус 48, v2.2)."""
        clear = TANK_RADIUS * BOSS_SCALE + 14
        ok = (not self.arena.circle_collides(x, y, clear)
              and all(math.hypot(x - tx, y - ty) > 240 for tx, ty in taken))
        if ok:
            return (x, y)
        for _ in range(140):
            nx = random.uniform(self.arena.wall_t + 90,
                                self.arena.w - self.arena.wall_t - 90)
            ny = random.uniform(self.arena.wall_t + 80,
                                self.arena.h - self.arena.wall_t - 80)
            if self.arena.circle_collides(nx, ny, clear):
                continue
            if all(math.hypot(nx - tx, ny - ty) > 240 for tx, ty in taken):
                return (nx, ny)
        return (x, y)          # совсем некуда — пусть вылезает как есть

    def _assault_spawn(self, x, y, taken):
        """v3.3: точка появления В ШТУРМЕ — слот карты, при затыке
        подвинуться РЯДОМ (в пределах здания/своего края), а не
        улетать в случайное место карты, как _free_spawn."""
        clear = TANK_RADIUS + 12
        if (not self.arena.circle_collides(x, y, clear)
                and all(math.hypot(x - tx, y - ty) > 100
                        for tx, ty in taken)):
            return (x, y)
        for _ in range(120):
            a = random.uniform(0, 2 * math.pi)
            d = random.uniform(40, 240)
            nx, ny = x + math.cos(a) * d, y + math.sin(a) * d
            if not (self.arena.wall_t + 60 < nx < self.arena.w - self.arena.wall_t - 60
                    and self.arena.wall_t + 60 < ny < self.arena.h - self.arena.wall_t - 60):
                continue
            if self.arena.circle_collides(nx, ny, clear):
                continue
            if all(math.hypot(nx - tx, ny - ty) > 100 for tx, ty in taken):
                return (nx, ny)
        return (x, y)

    def _pick_assault_map(self):
        """v3.3: карта для ШТУРМА — случайная из встроенных крепостей
        (ДОМ/СКЛАД/ФОРТ) плюс СВОИ карты игрока из папки maps."""
        pool = list(ASSAULT_MAPS) + load_custom_maps()
        return random.choice(pool)

    def _setup_assault_arena(self):
        """v3.3: собрать арену ШТУРМА под выбранную карту: встроенные
        крепости — раскладка-фон + ЗДАНИЕ из казённых стен и спавны;
        свои карты редактора — пустырь + стены/барьеры/точка из файла."""
        amap = self._pick_assault_map()
        self._assault_name = amap["name"]
        if amap.get("custom"):
            self.arena = Arena(EMPTY_VARIANT, shuffle=False, team=True)
            self.arena.add_static(amap["walls"])
            self.arena.name = "%s [своя карта]" % amap["name"]
        else:
            self.arena = Arena(amap["variant"], shuffle=False, team=True)
            # фон-раскладка не лезет в здание: сносим всё, что попало
            # в прямоугольник здания с запасом
            self.arena.clear_box(pygame.Rect(
                int(amap["point"][0] - amap["hw"] - 90),
                int(amap["point"][1] - amap["hh"] - 90),
                int(amap["hw"] * 2 + 180), int(amap["hh"] * 2 + 180)))
            self.arena.name = "%s [штурм]" % amap["name"]
        self.cap_xy = (float(amap["point"][0]), float(amap["point"][1]))
        self._assault_slots = (amap["def_spawns"], amap["atk_spawns"])
        self._assault_build = amap.get("segs")
        # у своих карт могло не хватать слотов — добиваем свободными
        # местами рядом с точкой (защита) и по краю (атака)
        dslots, aslots = self._assault_slots
        if len(dslots) < 7:
            dslots = list(dslots) + [
                self._pad_def_slot(dslots) for _ in range(7 - len(dslots))]
            self._assault_slots = (dslots, aslots)
        if len(aslots) < 7:
            aslots = list(aslots) + [
                self._pad_atk_slot(aslots) for _ in range(7 - len(aslots))]
            self._assault_slots = (dslots, aslots)

    def _pad_def_slot(self, slots):
        """Дополнительный слот защитника: свободное место близ точки."""
        cx, cy = self.cap_xy
        for _ in range(120):
            a = random.uniform(0, 2 * math.pi)
            d = random.uniform(150, 330)
            x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
            if not self.arena.circle_collides(x, y, TANK_RADIUS + 12):
                if all((x - sx) ** 2 + (y - sy) ** 2 > 100 ** 2
                       for sx, sy in slots):
                    return (x, y)
        return (cx, cy)

    def _pad_atk_slot(self, slots):
        """Дополнительный слот атакующего: свободное место подальше
        от точки (минимум 1000 px) — по краям карты."""
        cx, cy = self.cap_xy
        for _ in range(160):
            x = random.uniform(self.arena.wall_t + 80,
                               self.arena.w - self.arena.wall_t - 80)
            y = random.uniform(self.arena.wall_t + 80,
                               self.arena.h - self.arena.wall_t - 80)
            if (x - cx) ** 2 + (y - cy) ** 2 < 1000 ** 2:
                continue
            if self.arena.circle_collides(x, y, TANK_RADIUS + 12):
                continue
            if all((x - sx) ** 2 + (y - sy) ** 2 > 100 ** 2
                   for sx, sy in slots):
                return (x, y)
        return (self.arena.wall_t + 120, self.arena.h / 2.0)

    def _reset_round(self):
        self.orders_open = False      # v3.5: окно приказов закрывается на новом раунде
        # арена переразыгрывается КАЖДЫЙ РАУНД и перемешивается (v2.1);
        # v2.5: командные режимы играют на КРУПНЫХ картах (3888x2187);
        # v2.7: большие FFA (6-10 танков) — на тех же крупных картах;
        # v2.8: армии 6на6…10на10 — на САМЫХ БОЛЬШИХ (5120x2880);
        # v3.3: ШТУРМ — без перемешивания: карта со ЗДАНИЕМ (точка внутри),
        # случайная из встроенных крепостей и своих карт редактора
        self.is_assault = self.mode in ASSAULT_MODES
        if self.is_assault:
            self._setup_assault_arena()
            self._battle_custom = None      # v3.4: в ШТУРМЕ — штурмовые карты
        else:
            # v3.4: СВОИ БОЕВЫЕ карты редактора играют в FFA и командах
            bmap = self._pick_battle_map()
            self._battle_custom = bmap
            if bmap is not None:
                self.arena = Arena(EMPTY_VARIANT, shuffle=False, team=True)
                self.arena.add_static(bmap["walls"])
                self.arena.name = "%s [своя]" % bmap["name"]
            else:
                self.arena = Arena(random.randrange(len(LAYOUTS)),
                                   shuffle=True,
                                   team=self.mode >= 6,
                                   army=self.mode in ARMY_MODES)
        cx, cy = self.arena.w / 2.0, self.arena.h / 2.0
        pts = self._spawn_points(self._tank_count())
        # v2.7: команды — ТОЛЬКО режимы 6-10 (большие FFA 11-15 — каждый сам за себя);
        # v2.8: к ним добавились армии 6на6…10на10 (16-20)
        self.team_mode = self.mode in TEAM_MODES
        self.tank_team = {}
        self.player = Tank(
            pts[0][0], pts[0][1],
            math.degrees(math.atan2(cy - pts[0][1], cx - pts[0][0])),
            self.build[0], self.build[1], COL_P1,
            self.build[2], self.build[3], self.build[4],
            self.build[5], self.build[6],
            shell_type=SHELL_KEYS[self.sel_shell])
        self.player.team = 0
        self.tank_team[self.player] = 0
        # эффекты НА ВРАГА: словарь модов для вражеской команды
        emods = {}
        for key in self.build[7]:
            for f, v in ENEMY_EFFECTS[key]["mods"].items():
                if f == "spread_deg":
                    emods[f] = emods.get(f, 0.0) + v
                else:
                    emods[f] = emods.get(f, 1.0) * v
        self.tanks = [self.player]
        self.bots = []
        self.ais = []
        n_tanks = self._tank_count()
        # сколько союзников впереди: 2 против босса — один,
        # 2на2/3на3/4на4 — половина минус игрок
        n_allies = (1 if self.mode == 7 else n_tanks // 2 - 1) \
            if self.team_mode else 0
        # v3.6: СВОЯ БАЗА — центр стартовой шеренги команды (для приказа
        # «ОТСТУПАЙ»); в ШТУРМЕ обороны базой служит само здание
        self.base0 = None
        if self.team_mode:
            ours = pts[:n_allies + 1]
            self.base0 = (sum(p[0] for p in ours) / len(ours),
                          sum(p[1] for p in ours) / len(ours))
        for i in range(n_tanks - 1):
            b = self.bot_builds[i % len(self.bot_builds)] if self.bot_builds \
                else ("medium", "medium", "standard", "none", "none")
            px, py = pts[i + 1]
            ang = math.degrees(math.atan2(cy - py, cx - px))
            ally = i < n_allies                # союзники — первые в списке
            boss = self.mode == 7 and i == 1   # огромный БОСС
            if ally:
                aname = "СОЮЗНИК" if i == 0 else "СОЮЗНИК-%d" % (i + 1)
                t = Tank(px, py, ang, b[0], b[1], ALLY_COLOR,
                         b[2], b[3], b[4], display_name=aname)
                t.team = 0
            elif boss:
                mods = dict(BOSS_MODS)
                for f, v in emods.items():
                    if f == "spread_deg":
                        mods[f] = mods.get(f, 0.0) + v
                    else:
                        mods[f] = mods.get(f, 1.0) * v
                t = Tank(px, py, ang, BOSS_BUILD[0], BOSS_BUILD[1], BOSS_COLOR,
                         BOSS_BUILD[2], BOSS_BUILD[3], BOSS_BUILD[4],
                         extra_mods=mods or None, scale=BOSS_SCALE,
                         display_name="БОСС")
                t.team = 1
            else:
                if self.team_mode:
                    j = i - n_allies           # номер вражеского бота в шеренге
                    color = BOT_COLORS[j % len(BOT_COLORS)]
                    t = Tank(px, py, ang, b[0], b[1], color,
                             b[2], b[3], b[4], extra_mods=emods or None,
                             display_name=BOT_NAMES[j])
                    t.team = 1
                else:
                    color = BOT_COLORS[i % len(BOT_COLORS)]
                    t = Tank(px, py, ang, b[0], b[1], color,
                             b[2], b[3], b[4], extra_mods=emods or None)
                    t.team = i + 1
            self.tank_team[t] = t.team
            self.bots.append(t)
            self.ais.append(BotAI(t, self.difficulty))
            self.tanks.append(t)
            # v3.0: БОТАМ ТОЖЕ ДАЮТ БИЛДЫ И ТИПЫ СНАРЯДОВ — случайный набор
            # каждому (кроме БОССА: он и так ходячая крепость). В 10на10
            # это и есть «заварушка»: у каждого бота свои стены, мины,
            # турели и свой боеприпас. Выдача только в НАЧАТОМ матче
            # (bot_builds наполнен в start_match): так раунды без матча
            # (меню, тесты) остаются детерминированными.
            if not boss and self.bot_builds:
                self._apply_build(t, random.randrange(len(BUILD_KEYS)))
                t.shell_type = self._random_bot_shell()
        self.bot_tank = self.bots[0] if self.bots else None
        self.ai = self.ais[0] if self.ais else None
        # враги — на них капают очки, они дохнут от кнопки и таймера v2.5
        self.foes = [t for t in self.tanks if t is not self.player
                     and self.tank_team[t] != 0]
        # v3.4: ВРАЖЕСКИЙ КОМАНДИР — у команды ботов тоже есть командир
        # (звезда ★): он приказывает своим держать рубежи и идти вперёд
        # (в ШТУРМЕ роли и так расписаны, БОСС командовать не умеет)
        if (self.team_mode and not self.is_assault and self.mode != 7):
            enemy_bots = [t for t in self.bots if self.tank_team.get(t) == 1]
            if enemy_bots:
                enemy_bots[0].is_commander = True
        self.cmd_t = random.uniform(4.0, 6.0)
        # счёт должен совпадать с режимом (FFA — на каждого танка,
        # команды — на две стороны): защита от смены режима без start_match
        need = 2 if self.team_mode else len(self.tanks)
        if len(self.score) != need:
            self.score = (list(self.score) + [0] * need)[:need]
        # v2.5: НЕУЯЗВИМОСТИ НЕТ — ботов можно бить с первой секунды;
        # окно «выяснения» стартует только после смерти игрока
        self.spectate_t = 0.0
        self.bullets = []
        self.powerups = []
        self.mines = []
        self.smokes = []
        self.barriers = []
        self.turrets = []
        self.fire_zones = []          # v3.0: огненные лужи с нового раунда
        self.arena.set_dynamic([])
        self.powerup_t = POWERUP_INTERVAL * 0.6
        self.effects.particles.clear()
        self.effects.texts.clear()
        self.con_place = None
        self._apply_build(self.player)   # v2.9: стартовый билд (если выбран)
        # v3.2: ШТУРМ — сброс точки и комплект защитников:
        # у каждого по 5 ПРОЧНЫХ стен, 2 турели и 3 мины (просьба игрока)
        # v3.3: комплект получает сторона ОБОРОНЫ (кем бы она ни была —
        # игрок мог выбрать АТАКУ), и строится ЗДАНИЕ карты
        self.cap_progress = 0.0
        self.cap_hold = ASSAULT_HOLD_T
        self._repair_fx = 0.0
        if self.is_assault:
            for tk in self.tanks:
                if self.tank_team.get(tk) == self.assault_def_team:
                    tk.give_walls("strong", ASSAULT_KIT_WALLS)
                    tk.turret_charges = min(tk.turret_charges + ASSAULT_KIT_TURRETS,
                                            TURRET_CARRY)
                    tk.mine_carried = min(tk.mine_carried + ASSAULT_KIT_MINES, 99)
            # казённые стены здания: owner нет, сторона — оборона.
            # Их можно ПРОЛОМАТЬ снарядами и ЧИНИТЬ ключом (H) — но
            # только защитникам
            if self._assault_build:
                for x, y, ang, tier in self._assault_build:
                    self.barriers.append(Barrier(x, y, ang, None,
                                                 tier=tier,
                                                 team=self.assault_def_team))
                self.arena.set_dynamic(self.barriers)
        elif self._battle_custom is not None:
            # v3.4: прочные стены с БОЕВОЙ карты — казённые барьеры без
            # владельца: их можно ПРОЛОМАТЬ, чинить их некому
            for x, y, ang, tier in self._battle_custom["segs"]:
                self.barriers.append(Barrier(x, y, ang, None, tier=tier,
                                             team=None))
            self.arena.set_dynamic(self.barriers)
        self.spec_target = None          # v3.0: спектатор-камера с начала
        self._cam_snap()          # камера сразу на игрока

    def start_match(self):
        # v3.3: решаем СТОРОНУ в ШТУРМЕ («можно выбирать атака ты или
        # оборона»): 'rand' — случайно на каждый матч. Игрок всегда в
        # команде 0; оборона = 0, если игрок в обороне, иначе 1.
        if self.mode in ASSAULT_MODES:
            side = self.assault_side
            if side == "rand":
                side = random.choice(("def", "atk"))
            self.assault_def_team = 0 if side == "def" else 1
            self.assault_atk_team = 1 - self.assault_def_team
        # у каждого бота своя сборка на матч
        self.bot_builds = [random_build()
                           for _ in range(self._tank_count() - 1)]
        # в FFA счёт на каждого танка, в командах — на две стороны
        self.score = [0] * (2 if self.mode in TEAM_MODES
                            else self._tank_count())
        self.round = 1
        self.points = 0.0
        self.score_mult = self._score_mult()   # жребий уже учтён в сборке
        self._reset_round()
        self.state = "intro"
        self.timer = ROUND_BANNER_T
        self.sounds.play("round")

    # ================= жребий: проклятья и облегчения =================
    @staticmethod
    def _random_bot_shell():
        """v3.0: случайный тип снаряда для бота (стандарт чаще всех)."""
        r = random.random()
        acc = 0.0
        for key, w in SHELL_BOT_WEIGHTS:
            acc += w
            if r < acc:
                return key
        return "std"

    def _apply_build(self, t, idx=None):
        """v2.9: выдать танку стартовый билд (в начале КАЖДОГО раунда).
        Максимум ОДИН билд на танк. v3.0: idx можно передать явно — так
        боты получают случайные билды (игроку берётся sel_build из ангара).
        Предметы кладутся в боекомплект напрямую, баффы включаются на
        старте, «mods» (v3.0, «Стройка века») множат характеристики."""
        if idx is None:
            idx = self.sel_build
        if idx is None or t is None:
            return
        bd = BUILDS[BUILD_KEYS[idx]]
        t.build_name = bd["name"]
        for item, n in bd.get("items", {}).items():
            if item == "barrier":
                t.barrier_charges = min(t.barrier_charges + n, BARRIER_MAX)
            elif item == "mine":
                t.mine_carried = min(t.mine_carried + n, 99)
            elif item == "turret":
                t.turret_charges = min(t.turret_charges + n, TURRET_CARRY)
            elif item == "triple":
                t.triple += n
            elif item == "he":
                t.he_shots = min(t.he_shots + n, 99)
            elif item == "emp":
                t.emp_charges = min(t.emp_charges + n, 99)
            elif item == "nova":                 # v3.1: «Круговой ад» — заряд один
                t.nova_charges = min(t.nova_charges + n, 1)
        for buff, val in bd.get("buffs", {}).items():
            setattr(t, buff, val)
        for mod, val in bd.get("mods", {}).items():   # v3.0: «Стройка века»
            t.mods[mod] = t.mods.get(mod, 1.0) * val
        self.effects.float_text(t.x, t.y - 78, "БИЛД: %s" % bd["name"],
                                bd["color"])

    def _bless_cap(self):
        """Сколько облегчений можно взять: 1 + каждое проклятье."""
        return 1 + len(self.sel_curses)

    def _toggle_curse(self, idx):
        key = CR_KEYS[idx]
        if key in self.sel_curses:
            self.sel_curses.remove(key)
            # проклятий стало меньше — лишние облегчения придётся снять
            while len(self.sel_blessings) > self._bless_cap():
                self.sel_blessings.pop()
        else:
            # v2.2: ЛИМИТА БОЛЬШЕ НЕТ — берите все 8 разом, если не жалко HP
            self.sel_curses.append(key)

    def _toggle_bless(self, idx):
        key = BL_KEYS[idx]
        if key in self.sel_blessings:
            self.sel_blessings.remove(key)
        elif len(self.sel_blessings) < self._bless_cap():
            self.sel_blessings.append(key)

    def _toggle_enemy(self, idx):
        """Эффекты НА ВРАГА: баффы врагу ДОБАВЛЯЮТ очки, дебаффы режут.
        v2.2: ЛИМИТА БОЛЬШЕ НЕТ — можно повесить все 12 разом."""
        key = EE_KEYS[idx]
        if key in self.sel_enemy_keys:
            self.sel_enemy_keys.remove(key)
        else:
            self.sel_enemy_keys.append(key)

    def _fate_mult(self, curses, blessings, enemy):
        """Множитель очков: проклятья ДОБАВЛЯЮТ 15% каждое (риск платит),
        облегчения режут 10%, баффы врагу ДОБАВЛЯЮТ свои %,
        дебаффы врага — режут."""
        m = (1.0 + SCORE_CURSE_BONUS * len(curses)
             - SCORE_BLESS_PENALTY * len(blessings))
        for key in enemy:
            e = ENEMY_EFFECTS[key]
            m += e.get("score_bonus", 0.0)   # усилить врага — очки капают
            m -= e.get("score_cut", 0.0)     # ослабить врага — режет счёт
        return max(SCORE_MULT_FLOOR, m)

    def _score_mult(self):
        """Множитель очков за ЗАФИКСИРОВАННУЮ сборку."""
        return self._fate_mult(self.build[5], self.build[6], self.build[7])

    # ================= ввод (клавиатура по событиям) =================
    def on_keydown(self, e):
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        # ----- ПОЛНОЭКРАННЫЙ РЕЖИМ (v2.9): F11 работает ВЕЗДЕ — в меню,
        # ангаре, бою, паузе и таблице. pygame сам разворачивает окно.
        if k == pygame.K_F11:
            try:
                pygame.display.toggle_fullscreen()
            except Exception:
                pass        # headless/dummy-драйвер — молча пропускаем
            return
        # ----- КОНСОЛЬ РАЗРАБОТЧИКА: Ё (`) открывает и закрывает.
        # v2.5: на РУССКОЙ раскладке Windows Ё не даёт K_BACKQUOTE —
        # ловим и сканкод клавиши, и символ (работает на любой раскладке)
        if (k == pygame.K_BACKQUOTE
                or getattr(e, "scancode", 0) == pygame.KSCAN_GRAVE
                or getattr(e, "unicode", "") in ("`", "~", "ё", "Ё")):
            self.con_open = not self.con_open
            if self.con_open:
                self.con_input = ""
                self.con_scroll = 0     # v3.6: открыли — показываем низ
            return
        if self.con_open:
            self._con_key(e)      # пока консоль открыта — весь ввод ей
            return
        if self.state == "menu":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "select"
            elif k == pygame.K_t:
                self._table_from = "menu"
                self.state = "table"           # ТАБЛИЦА СЧЕТА
            elif k == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            elif k in (pygame.K_1, pygame.K_KP1):
                self.difficulty = 1
                self.sounds.play("ric")
            elif k in (pygame.K_2, pygame.K_KP2):
                self.difficulty = 2
                self.sounds.play("ric")
            elif k in (pygame.K_3, pygame.K_KP3):
                self.difficulty = 3
                self.sounds.play("ric")
            elif k == pygame.K_g:
                self._cycle_assault_side()      # v3.3: сторона в ШТУРМЕ
            elif k == pygame.K_m:
                self.state = "editor"           # v3.3: РЕДАКТОР КАРТ
                self._ed_enter()
            elif k == pygame.K_F2:
                self.mode = 2
                self.sounds.play("ric")
            elif k == pygame.K_F3:
                self.mode = 3
                self.sounds.play("ric")
            elif k == pygame.K_F4:
                self.mode = 4
                self.sounds.play("ric")
            elif k == pygame.K_F5:
                self.mode = 5
                self.sounds.play("ric")
            elif k == pygame.K_F6:
                self.mode = 6
                self.sounds.play("ric")
            elif k == pygame.K_F7:
                self.mode = 7
                self.sounds.play("ric")
            elif k == pygame.K_F8:
                self.mode = 8
                self.sounds.play("ric")
            elif k == pygame.K_F9:
                self.mode = 9
                self.sounds.play("ric")
            elif k == pygame.K_F10:
                self.mode = 10
                self.sounds.play("ric")
        elif self.state == "editor":
            # v3.3: РЕДАКТОР КАРТ — инструменты и сохранение
            # v3.4: TAB — ТИП КАРТЫ: ШТУРМ (точка+спавны сторон) /
            # БОЙ (спавны союзников и врагов — для FFA и командных)
            tools = self._ed_tools()
            if k == pygame.K_ESCAPE:
                self.state = "menu"
            elif k == pygame.K_TAB:
                self.ed_kind = "battle" if self.ed_kind == "assault" else "assault"
                if self.ed_tool == "P":
                    self.ed_tool = "#"     # точки захвата только в ШТУРМЕ
                self.ed_msg = ""
                self.sounds.play("ric")
            elif k in (pygame.K_1, pygame.K_KP1):
                self.ed_tool = tools[0][0]
            elif k in (pygame.K_2, pygame.K_KP2):
                self.ed_tool = tools[1][0]
            elif k in (pygame.K_3, pygame.K_KP3):
                self.ed_tool = tools[2][0]
            elif k in (pygame.K_4, pygame.K_KP4):
                self.ed_tool = tools[3][0]
            elif k in (pygame.K_5, pygame.K_KP5) and len(tools) > 5:
                self.ed_tool = tools[4][0]
            elif k in (pygame.K_6, pygame.K_KP6) and len(tools) > 6:
                self.ed_tool = tools[5][0]
            elif k in (pygame.K_7, pygame.K_KP7) and len(tools) > 7:
                self.ed_tool = tools[6][0]
            elif k == pygame.K_e:
                self.ed_tool = "."      # ластик
            elif k == pygame.K_c:
                self.ed_grids[self.ed_kind] = \
                    [["."] * EDITOR_COLS for _ in range(EDITOR_ROWS)]
                self.ed_msg = "Поле очищено — стройте заново"
            elif k == pygame.K_s:
                self._ed_save()
        elif self.state == "select":
            if k in (pygame.K_a, pygame.K_LEFT):
                self.sel_ch = (self.sel_ch - 1) % len(CH_KEYS)
                self.sounds.play("ric")
            elif k in (pygame.K_d, pygame.K_RIGHT):
                self.sel_ch = (self.sel_ch + 1) % len(CH_KEYS)
                self.sounds.play("ric")
            elif k in (pygame.K_w, pygame.K_UP):
                self.sel_hu = (self.sel_hu - 1) % len(HU_KEYS)
                self.sounds.play("ric")
            elif k in (pygame.K_s, pygame.K_DOWN):
                self.sel_hu = (self.sel_hu + 1) % len(HU_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_q:
                self.sel_wpn = (self.sel_wpn - 1) % len(WP_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_e:
                self.sel_wpn = (self.sel_wpn + 1) % len(WP_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_z:
                self.sel_pk = (self.sel_pk - 1) % len(PK_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_c:
                self.sel_pk = (self.sel_pk + 1) % len(PK_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_f:
                self.sel_el = (self.sel_el - 1) % len(EL_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_g:
                self.sel_el = (self.sel_el + 1) % len(EL_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_r:
                self.sel_jt = (self.sel_jt - 1) % JT_TOTAL
                self.sounds.play("ric")
            elif k == pygame.K_t:
                self.sel_jt = (self.sel_jt + 1) % JT_TOTAL
                self.sounds.play("ric")
            elif k == pygame.K_v:
                if self.sel_jt < len(CR_KEYS):
                    self._toggle_curse(self.sel_jt)
                else:
                    self._toggle_bless(self.sel_jt - len(CR_KEYS))
                self.sounds.play("ric")
            elif k == pygame.K_b:
                self.sel_en = (self.sel_en - 1) % len(EE_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_n:
                self.sel_en = (self.sel_en + 1) % len(EE_KEYS)
                self.sounds.play("ric")
            elif k == pygame.K_m:
                self._toggle_enemy(self.sel_en)   # эффект НА ВРАГА
                self.sounds.play("ric")
            elif k in (pygame.K_0, pygame.K_KP0):
                self.sel_build = None             # v2.9: без билда
                self.sounds.play("ric")
            elif k in (pygame.K_1, pygame.K_KP1):
                self.sel_build = 0
                self.sounds.play("ric")
            elif k in (pygame.K_2, pygame.K_KP2):
                self.sel_build = 1
                self.sounds.play("ric")
            elif k in (pygame.K_3, pygame.K_KP3):
                self.sel_build = 2
                self.sounds.play("ric")
            elif k in (pygame.K_4, pygame.K_KP4):
                self.sel_build = 3
                self.sounds.play("ric")
            elif k in (pygame.K_5, pygame.K_KP5):
                self.sel_build = 4
                self.sounds.play("ric")
            elif k in (pygame.K_6, pygame.K_KP6):
                self.sel_build = 5
                self.sounds.play("ric")
            elif k in (pygame.K_7, pygame.K_KP7):
                self.sel_build = 6
                self.sounds.play("ric")
            elif k in (pygame.K_8, pygame.K_KP8):
                self.sel_build = 7                 # v3.0: СТРОЙКА ВЕКА
                self.sounds.play("ric")
            elif k in (pygame.K_9, pygame.K_KP9):
                self.sel_build = 8                 # v3.1: КРУГОВОЙ АД
                self.sounds.play("ric")
            elif k == pygame.K_x:
                # v3.0: ТИП СНАРЯДА — прокрутка по кругу (или клик по панели)
                self.sel_shell = (self.sel_shell + 1) % len(SHELL_KEYS)
                self.sounds.play("ric")
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self.build = (CH_KEYS[self.sel_ch], HU_KEYS[self.sel_hu],
                              WP_KEYS[self.sel_wpn], PK_KEYS[self.sel_pk],
                              EL_KEYS[self.sel_el],
                              tuple(self.sel_curses), tuple(self.sel_blessings),
                              tuple(self.sel_enemy_keys))
                self.start_match()
            elif k == pygame.K_ESCAPE:
                self.state = "menu"
        elif self.state == "table":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_m):
                self.state = self._table_from
        elif self.state == "fight":
            if self.orders_open and k in self.ORDERS_UI_KEYS:
                # v3.6: ОКНО ПРИКАЗОВ перехватывает свои клавиши —
                # Esc/E закрывают, T — вся команда, Tab — следующий бот,
                # 1–8 отдают приказы
                if k in (pygame.K_ESCAPE, pygame.K_e):
                    self.orders_open = False
                elif k == pygame.K_t:
                    self.orders_all = not self.orders_all
                    if self.orders_all:
                        self.orders_pick = set()
                    self.sounds.play("ric")
                elif k == pygame.K_TAB:
                    allies = self._allies_alive()
                    if allies:
                        cur = (next(iter(self.orders_pick))
                               if len(self.orders_pick) == 1
                               else self._order_target())
                        i = allies.index(cur) if cur in allies else -1
                        self.orders_pick = {allies[(i + 1) % len(allies)]}
                        self.orders_all = False
                    self.sounds.play("ric")
                else:
                    self._command_order(self.ORDER_KEYMAP[k],
                                        all_=self.orders_all)
            elif k == pygame.K_ESCAPE:
                if self.con_place:
                    self.con_place = None   # отмена установки бонуса
                else:
                    self.state = "pause"
            elif (k in (pygame.K_LEFT, pygame.K_a, pygame.K_SPACE)
                    and not self.player.alive):
                self._spec_switch(-1)      # v3.0: спектатор — предыдущий танк
            elif (k in (pygame.K_RIGHT, pygame.K_d)
                    and not self.player.alive):
                self._spec_switch(1)       # v3.0: спектатор — следующий танк
            elif k == pygame.K_q:
                self._place_barrier(self.player)   # стена-бустер
            elif k == pygame.K_e:
                # v3.5: КОМАНДИР — E ОТКРЫВАЕТ ОКНО ПРИКАЗОВ (Shift+E —
                # сразу с целью «ВСЯ КОМАНДА»); в окне 1–5 — приказы.
                # Мина переехала на F.
                self._command_open(
                    all_=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
            elif k == pygame.K_f:
                self._place_mine(self.player)      # мина руками (была на E)
            elif k == pygame.K_r:
                self._place_turret(self.player)    # v2.9: турель
            elif k == pygame.K_x:
                self._use_emp(self.player)         # v2.9: носимый ЭМИ-заряд
            elif k == pygame.K_v:
                self._fire_nova(self.player)       # v3.1: КРУГОВОЙ АД (билд)
        elif self.state == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.state = "fight"
            elif k == pygame.K_a:
                # выход в ангар: матч сбрасывается — сборка-то меняется
                self.score = [0] * (2 if self.mode in TEAM_MODES
                                    else self._tank_count())
                self.round = 1
                self.state = "select"
            elif k == pygame.K_m:
                self.state = "menu"
        elif self.state == "match_end":
            if k == pygame.K_RETURN:
                self.start_match()
            elif k == pygame.K_a:
                self.score = [0] * (2 if self.mode in TEAM_MODES
                                    else self._tank_count())
                self.round = 1
                self.state = "select"   # в ангар за новой сборкой
            elif k == pygame.K_t:
                self._table_from = "match_end"
                self.state = "table"    # посмотреть таблицу счёта
            elif k in (pygame.K_m, pygame.K_ESCAPE):
                self.state = "menu"

    # ============ мышь: клик по карточкам, жребию и кнопкам ============
    def _button(self, centerx, centery, label, kind, data=None,
                w=240, h=44, fs=20):
        """Нарисовать кнопку и зарегистрировать её как кликабельную."""
        r = pygame.Rect(0, 0, w, h)
        r.center = (int(centerx), int(centery))
        hover = r.collidepoint(self._mouse)
        pygame.draw.rect(self.screen, (46, 58, 104) if hover else (30, 40, 75),
                         r, border_radius=9)
        pygame.draw.rect(self.screen, COL_P1 if hover else (70, 80, 120), r,
                         2 if hover else 1, border_radius=9)
        img = get_font(fs).render(label, True, COL_TEXT)
        self.screen.blit(img, img.get_rect(center=r.center))
        self._click_zones.append((r, kind, data))
        return r

    def on_click(self, pos):
        """Клик мышью: зона, нарисованной последней, — в приоритете."""
        for rect, kind, data in reversed(self._click_zones):
            if rect.collidepoint(pos):
                self._handle_click(kind, data, pos)
                return True
        return False

    def _handle_click(self, kind, data, pos=None):
        attr = {"ch": "sel_ch", "hu": "sel_hu", "wpn": "sel_wpn",
                "pk": "sel_pk", "el": "sel_el"}.get(kind)
        if attr is not None:                      # карточка сборки — выбрать её
            if getattr(self, attr) != data:
                setattr(self, attr, data)
                self.sounds.play("ric")
        elif kind == "fate":                      # проклятье/облегчение
            self.sel_jt = data
            if data < len(CR_KEYS):
                self._toggle_curse(data)
            else:
                self._toggle_bless(data - len(CR_KEYS))
            self.sounds.play("ric")
        elif kind == "enemy":                     # эффект НА ВРАГА
            self.sel_en = data
            self._toggle_enemy(data)
            self.sounds.play("ric")
        elif kind == "menu_diff":
            self.difficulty = data
            self.sounds.play("ric")
        elif kind == "menu_mode":              # режим боя: 2..7 танков/команды
            self.mode = data
            self.sounds.play("ric")
        elif kind == "menu_side":              # v3.3: сторона в ШТУРМЕ
            self.assault_side = data
            self.sounds.play("ric")
        elif kind == "ord_row":                # v3.5: клик по строке приказа
            self._command_order(data, all_=self.orders_all)
        elif kind == "ord_bot":                # v3.6: клик по ПЛИТКЕ БОТА
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                # Shift+клик — ДОБАВИТЬ в выбор (нескольким сразу)
                if data in self.orders_pick:
                    self.orders_pick.discard(data)
                else:
                    self.orders_pick.add(data)
            else:
                # обычный клик — выбрать ТОЛЬКО этого бота; повторный
                # клик по нему снимает выбор (приказ уйдёт боту у прицела)
                self.orders_pick = set() if self.orders_pick == {data} \
                    else {data}
            self.orders_all = False
            self.sounds.play("ric")
        elif kind == "ord_all":                # v3.6: плитка «ВСЯ КОМАНДА»
            self.orders_all = True
            self.orders_pick = set()
            self.sounds.play("ric")
        elif kind == "ord_tgt":                # v3.5: сменить цель приказа
            self.orders_all = not self.orders_all
            if self.orders_all:
                self.orders_pick = set()
            self.sounds.play("ric")
        elif kind == "ord_close":              # v3.5: закрыть окно приказов
            self.orders_open = False
            self.sounds.play("ric")
        elif kind == "menu_editor":           # v3.3: РЕДАКТОР КАРТ
            self.state = "editor"
            self._ed_enter()
            self.sounds.play("ric")
        elif kind == "ed_tool":               # v3.3: инструмент редактора
            self.ed_tool = data
            self.sounds.play("ric")
        elif kind == "ed_kind":               # v3.4: тип карты ШТУРМ/БОЙ
            if self.ed_kind != data:
                self.ed_kind = data
                if self.ed_tool == "P":
                    self.ed_tool = "#"    # точка захвата только в ШТУРМЕ
                self.ed_msg = ""
            self.sounds.play("ric")
        elif kind == "ed_board":              # v3.3: клетка поля редактора
            if pos is not None:
                self._ed_click(pos)
        elif kind == "build":                  # v2.9: выбор билда (макс. один)
            self.sel_build = None if data == self.sel_build else data
            self.sounds.play("ric")
        elif kind == "shell":                  # v3.0: тип снаряда
            self.sel_shell = data
            self.sounds.play("ric")
        elif kind == "kill_all":               # кнопка «УБИТЬ СРАЗУ» (окно v2.5)
            self._kill_all_foes()
        elif kind == "menu_start":
            self.state = "select"
            self.sounds.play("ric")
        elif kind == "open_table":
            self._table_from = data if data else self._table_from
            self.state = "table"
            self.sounds.play("ric")
        elif kind == "table_back":
            self.state = self._table_from
            self.sounds.play("ric")
        elif kind == "go_fight":
            self.build = (CH_KEYS[self.sel_ch], HU_KEYS[self.sel_hu],
                          WP_KEYS[self.sel_wpn], PK_KEYS[self.sel_pk],
                          EL_KEYS[self.sel_el],
                          tuple(self.sel_curses), tuple(self.sel_blessings),
                          tuple(self.sel_enemy_keys))
            self.start_match()
        elif kind == "garage_menu":
            self.state = "menu"
        elif kind == "p_resume":
            self.state = "fight"
        elif kind == "to_garage":                 # из паузы и из конца матча
            self.score = [0] * (2 if self.mode in TEAM_MODES
                                else self._tank_count())
            self.round = 1
            self.state = "select"
            self.sounds.play("ric")
        elif kind == "p_menu" or kind == "me_menu":
            self.state = "menu"
        elif kind == "me_rematch":
            self.start_match()

    # ================= камера большого мира (v2.2) =================
    def _spec_switch(self, step):
        """v3.0: СПЕКТАТОР — переключить камеру на предыдущий/следующий
        живой танк. Включается после смерти игрока: вместо того чтобы
        пялиться на одного бота, смотрите за КЕМ ХОТИТЕ."""
        if self.player.alive:
            return
        alive = [tk for tk in self.tanks if tk.alive]
        if not alive:
            return
        if self.spec_target in alive:
            i = (alive.index(self.spec_target) + step) % len(alive)
        else:
            i = 0
        self.spec_target = alive[i]
        self.sounds.play("ric")

    def _update_cam(self, dt):
        """Камера едет за игроком; после его смерти — СПЕКТАТОРОМ: за живым
        танком на выбор (v3.0: ←/→ сменить цель, по умолчанию первый живой;
        раньше был прибит один бот — «почему я слежу за одним ботом?»)."""
        if self.player.alive:
            t = self.player
        else:
            alive = [tk for tk in self.tanks if tk.alive]
            if self.spec_target not in alive:
                self.spec_target = alive[0] if alive else None
            t = self.spec_target
            if t is None:
                return
        tx = min(max(t.x - SCREEN_W / 2, 0.0), self.arena.w - SCREEN_W)
        ty = min(max(t.y - SCREEN_H / 2, 0.0), self.arena.h - SCREEN_H)
        k = min(1.0, dt * 5.0)
        self.cam[0] += (tx - self.cam[0]) * k
        self.cam[1] += (ty - self.cam[1]) * k

    def _cam_snap(self):
        """Камера мгновенно на игрока (новый раунд)."""
        if self.player is None:
            return
        self.cam[0] = min(max(self.player.x - SCREEN_W / 2, 0.0),
                          self.arena.w - SCREEN_W)
        self.cam[1] = min(max(self.player.y - SCREEN_H / 2, 0.0),
                          self.arena.h - SCREEN_H)

    def _kill_all_foes(self):
        """Кнопка «УБИТЬ СРАЗУ» (v2.6): не ждать 180 секунд «выяснения».
        В FFA — ЖРЕБИЙ: случайный живой бот сразу забирает раунд,
        остальные враги взрываются этим же кадром.
        v2.8: в КОМАНДНЫХ режимах кнопка СУДИТ ПО ЖИВЫМ — перевес +2 танка
        забирает раунд, при равном/почти равном составе — НИЧЬЯ."""
        if self.team_mode:
            self._team_judge()
            return
        alive = [t for t in self.foes if t.alive]
        self.spectate_t = 0.0
        if not alive:
            return
        lucky = random.choice(alive)
        for t in alive:
            if t is not lucky:
                t._die(self.effects, self.sounds)
        self.sounds.play("explode")
        # раунд сразу за счастливчиком — как у последнего выжившего
        self.winner = self.tanks.index(lucky)
        self.score[self.winner] += 1
        self.state = "round_end"
        self.timer = ROUND_PAUSE_T
        self.sounds.play("round")

    def _team_judge(self):
        """Кнопка «УБИТЬ СРАЗУ» в командах (v2.8): судим по живым танкам.
        У какой стороны перевес ДВА танка и больше — та забирает раунд;
        разница 0 или 1 — раунд НИЧЬЯ (никому). Никого не убиваем —
        просто фиксируем вердикт и заканчиваем раунд."""
        a0 = sum(1 for t in self.tanks if t.alive and self.tank_team[t] == 0)
        a1 = sum(1 for t in self.tanks if t.alive and self.tank_team[t] == 1)
        self.winner = 0 if a0 - a1 >= 2 else (1 if a1 - a0 >= 2 else -1)
        if self.winner >= 0:
            self.score[self.winner] += 1
            if self.winner == 0:
                self.points += SCORE_ROUND_WIN
        else:
            self.points += SCORE_ROUND_DRAW
        self.state = "round_end"
        self.timer = ROUND_PAUSE_T
        self.sounds.play("round")

    def _team_ring_color(self, t):
        """v2.6: цвет командной подсветки танка (или None вне команд).
        Враги — КРАСНЫЙ, союзники (включая вас) — САЛАТОВЫЙ."""
        if not self.team_mode:
            return None
        team = self.tank_team.get(t)
        if team is None:
            return None
        return TEAM_FOE_COLOR if team == 1 else TEAM_ALLY_COLOR

    def _team_pad(self, t):
        """Светящийся круг под танком (v2.6): враги красным, союзники
        салатовым. Рисуется ПОД спрайтом, статусы (щит/лёд/огонь) — над."""
        col = self._team_ring_color(t)
        if col is None:
            return None
        r = int(t.radius + 11)
        pad = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(pad, (col[0], col[1], col[2], 70), (r, r), r)
        pygame.draw.circle(pad, col, (r, r), r, 2)
        return pad

    # ================= обновление =================
    def update(self, dt):
        self.effects.update(dt)
        for pu in self.powerups:
            pu.update(dt)

        if self.state == "intro":
            self.timer -= dt
            if self.timer <= 0:
                self.state = "fight"

        elif self.state == "fight":
            if not self.con_open:      # консоль на Ё ставит бой на паузу
                self._fight_step(dt)

        elif self.state == "round_end":
            self.timer -= dt
            if self.timer <= 0:
                if max(self.score) >= ROUNDS_TO_WIN:
                    self.state = "match_end"
                    if self.score[0] >= ROUNDS_TO_WIN:
                        self.stats["wins"] += 1
                        self.points += SCORE_MATCH_WIN
                        res = "win"
                    else:
                        self.stats["losses"] += 1
                        res = "loss"
                    self.final_score = int(self.points * self.score_mult)
                    # --- ТАБЛИЦА СЧЕТА: забег попадает в топ-10 ---
                    entry = {
                        "score": self.final_score, "res": res,
                        "rounds": self._score_str(),
                        "c": len(self.build[5]), "b": len(self.build[6]),
                        "e": len(self.build[7]),
                        "mult": round(self.score_mult, 2),
                        "el": ELEMENTS[self.build[4]]["name"],
                        "date": time.strftime("%d.%m %H:%M"),
                    }
                    table = self.stats.setdefault("score_table", [])
                    table.append(entry)
                    table.sort(key=lambda r: -int(r.get("score", 0)))
                    del table[10:]
                    # v2.5: забег мог НЕ попасть в топ-10 и быть удалён —
                    # тогда места нет (0), а не падение next()
                    places = [i for i, r in enumerate(table) if r is entry]
                    self.table_place = places[0] + 1 if places else 0
                    self.new_record = (self.table_place == 1
                                       and self.final_score > 0)
                    if self.final_score > self.stats.get("best_score", 0):
                        self.stats["best_score"] = self.final_score
                    self._save_stats()
                    self.sounds.play(
                        "win" if self.score[0] >= ROUNDS_TO_WIN else "lose")
                else:
                    self.round += 1
                    self._reset_round()
                    self.state = "intro"
                    self.timer = ROUND_BANNER_T
                    self.sounds.play("round")

    def _score_str(self):
        """Счёт матча строкой: 1на1 — «5:3», FFA — ваши : лучшие из ботов,
        команды — ваша команда : враги."""
        if self.team_mode:
            return "%d:%d" % (self.score[0],
                              self.score[1] if len(self.score) > 1 else 0)
        if not self.bots:
            return "0:0"
        return "%d:%d" % (self.score[0], max(self.score[1:]))

    def _read_keys(self):
        if self._fake_keys is not None:
            return self._fake_keys
        return pygame.key.get_pressed()

    def _fight_step(self, dt):
        if self.orders_open and not self.player.alive:
            self.orders_open = False   # v3.5: мёртвый не командует
        keys = self._read_keys()
        fwd = ((keys[pygame.K_w] or keys[pygame.K_UP]) -
               (keys[pygame.K_s] or keys[pygame.K_DOWN]))
        tn = ((keys[pygame.K_d] or keys[pygame.K_RIGHT]) -
              (keys[pygame.K_a] or keys[pygame.K_LEFT]))

        # барьеры участвуют в коллизиях танков и в обзоре ботов
        self.arena.set_dynamic(self.barriers)

        # v2.5: НЕУЯЗВИМОСТИ НЕТ. Если игрок погиб, а живых чужаков двое
        # и больше (FFA) — они выясняют, кто сильнее, но не дольше
        # SPECTATE_T секунд: не успели — ВСЕ дохнут, раунд ничья.
        # Один живой бот — он и так берёт раунд (логика последнего выжившего).
        foes_alive = sum(1 for t in self.foes if t.alive)
        if (not self.team_mode and not self.player.alive
                and self.spectate_t <= 0.0 and foes_alive >= 2):
            self.spectate_t = SPECTATE_T
            self.effects.float_text(self.arena.w / 2, self.arena.h / 2 - 90,
                                    "БОТЫ ВЫЯСНЯЮТ, КТО СИЛЬНЕЕ...",
                                    (190, 205, 255))
        elif self.spectate_t > 0.0:
            self.spectate_t -= dt
            if self.spectate_t <= 0:
                self.spectate_t = 0.0
                for t in self.foes:
                    if t.alive:
                        t._die(self.effects, self.sounds)

        self._update_cam(dt)

        # v2.1: тикают ВСЕ танки (пожар/яд/таймеры)
        for t in self.tanks:
            t.update(dt)
            t._burn_step(dt, self.effects, self.sounds)
            t._poison_step(dt, self.effects, self.sounds)

        self.player.control(dt, self.arena, fwd, tn, tuple(self.tanks))
        for ai in self.ais:
            ai.update(dt, self)
        if keys[pygame.K_SPACE]:
            self.fire_weapon(self.player)

        # снимок HP ВРАГОВ: сколько HP снесём в этом кадре — столько очков
        hp_snap = sum(t.hp for t in self.foes)

        # снаряды бьют стены-барьеры (а стены блокируют и обзор ботов)
        walls = self.arena.walls_only()
        for b in self.bullets:
            self._bullet_vs_barriers(b)
            if not b.dead:
                self._bullets_vs_turrets(b)   # v2.9: чужие снаряды ломают турели
            if not b.dead:
                b.update(dt, walls, tuple(self.tanks),
                         self.effects, self.sounds)
            self._bullet_vs_barriers(b)
        # v3.0: на месте гибели ЗАЖИГАТЕЛЬНОГО снаряда остаётся огненная лужа
        for b in self.bullets:
            if b.dead and b.zone:
                self.fire_zones.append(FireZone(b.zone[0], b.zone[1], b.owner))
        # v3.4: ЗВЁЗДНЫЙ СНАРЯД — при гибели (стена/танк/барьер/турель)
        # рождает 5 осколков ЗВЕЗДОЙ (лучи через 72°)
        shards = []
        for b in self.bullets:
            if b.dead and b.star_split:
                self.effects.ring(b.x, b.y, (255, 226, 90), 56, 0.28)
                self.effects.burst(b.x, b.y, (255, 226, 90), 10, 220, 0.3, 3)
                shards.extend(b.star_children())
                self.sounds.play("laser")
        if shards:
            self.bullets.extend(shards)
        self.bullets = [b for b in self.bullets if not b.dead]

        for br in self.barriers[:]:
            br.update(dt)
            if br.expired():
                self.barriers.remove(br)
                self.effects.burst(br.x, br.y, (205, 210, 225), 10, 160, 0.4, 3)

        self._mines_step(dt)
        self._smokes_step(dt)
        self._powerups_step(dt)
        self._turrets_step(dt)        # v2.9: турели ищут цель и стреляют
        # v3.2: РЕМОНТ СТЕН — держите H рядом со своей (командной) стеной;
        # боты чинят своим же механизмом из ИИ
        self._repair_step(self.player, bool(keys[pygame.K_h]), dt)
        # v3.4: ВРАЖЕСКИЙ КОМАНДИР — периодически командует своими ботами:
        # часть ДЕРЖИТ рубежи, остальные давят; отвечает и на приказы игрока
        if (self.team_mode and not self.is_assault and self.mode != 7
                and any(b.alive for b in self.foes)):
            self.cmd_t -= dt
            if self.cmd_t <= 0:
                self._enemy_commander()
                self.cmd_t = random.uniform(CMD_PERIOD_MIN, CMD_PERIOD_MAX)
        # приказы с таймером (вражеские) истекают — бот снова свободен;
        # приказы игрока (order_t = 0) вечны, пока их не сменили
        for t in self.tanks:
            if t.order_t > 0:
                t.order_t = max(0.0, t.order_t - dt)
                if t.order_t <= 0:
                    t.order = None
            # v3.6: цель приказа «ПО МОЕЙ ЦЕЛИ» умерла — приказ снят
            if (t.order == "target"
                    and (getattr(t, "order_tgt", None) is None
                         or not t.order_tgt.alive)):
                t.order = None
        # v3.0: огненные лужи жгут чужих и гаснут по таймеру
        for fz in self.fire_zones:
            fz.step(dt, self)
        self.fire_zones = [fz for fz in self.fire_zones if not fz.expired()]

        # очки за урон врагам: снаряды, лазер, мины, пожар — 1:1 за HP
        # (в FFA чужие боты, подбившие друг друга, тоже приносят очки)
        dmg = hp_snap - sum(t.hp for t in self.foes)
        alive = [t for t in self.tanks if t.alive]
        # конец раунда: FFA — остался один, команды — вырезана вся сторона
        done = False
        winner = -1
        if self.team_mode:
            a0 = any(t.alive for t in self.tanks if self.tank_team[t] == 0)
            a1 = any(t.alive for t in self.tanks if self.tank_team[t] == 1)
            if not (a0 and a1):
                done = True
                winner = 0 if a0 else (1 if a1 else -1)
        elif len(alive) <= 1:
            done = True
            winner = self.tanks.index(alive[0]) if alive else -1
        # v3.2: ШТУРМ — если всех не перебили, решает ТОЧКА:
        # атакующие на ней без защитников — захват капает; защитники на
        # точке — откатывают; обе стороны — спор (заморожено). Захватили
        # целиком — победа атаки; защитники продержались до конца таймера —
        # победа обороны. v3.3: роли привязаны к assault_def/atk_team —
        # игрок мог выбрать АТАКУ и штурмовать здание ботами-защитниками.
        if self.is_assault and not done:
            capx, capy = self.cap_xy
            r2 = ASSAULT_POINT_R ** 2
            on_atk = sum(1 for t in alive
                         if self.tank_team.get(t) == self.assault_atk_team
                         and (t.x - capx) ** 2 + (t.y - capy) ** 2 < r2)
            on_dfn = sum(1 for t in alive
                         if self.tank_team.get(t) == self.assault_def_team
                         and (t.x - capx) ** 2 + (t.y - capy) ** 2 < r2)
            if on_atk and not on_dfn:
                self.cap_progress += dt
                if self.cap_progress >= ASSAULT_CAPTURE_T:
                    done = True
                    winner = self.assault_atk_team   # ТОЧКУ ЗАХВАТИЛИ
            elif on_dfn and not on_atk:
                self.cap_progress = max(0.0, self.cap_progress - dt * 2.0)
            if not done:
                self.cap_hold -= dt
                if self.cap_hold <= 0:
                    done = True
                    winner = self.assault_def_team   # ОБОРОНА ПРОДЕРЖАЛАСЬ
        if done:
            if dmg > 0:            # урон в этом кадре (включая добивание)
                self.points += dmg
            self.winner = winner
            if winner >= 0:
                self.score[winner] += 1
                if winner == 0:
                    self.points += SCORE_ROUND_WIN
            else:
                self.points += SCORE_ROUND_DRAW
            self.state = "round_end"
            self.timer = ROUND_PAUSE_T
            self.sounds.play("round")
        elif dmg > 0:
            self.points += dmg

    # ================= оружие (снаряды и лазер) =================
    def fire_weapon(self, t):
        """Единая точка стрельбы: если есть заряды лазера — луч, иначе снаряд.
        ЛАЗЕРНЫЙ ВЕЕР: при активном веере лазер стреляет ТРЕМЯ лучами
        и тратит 1 заряд веера."""
        if not t.alive or t.frozen_t > 0 or t.cooldown > 0:
            return
        if t.laser_charges > 0:
            t.laser_charges -= 1
            fan = t.triple > 0
            if fan:
                t.triple -= 1
            self.fire_laser(t, fan=fan)
            t.cooldown = t.reload_time
        else:
            t.try_shoot(self.bullets, self.effects, self.sounds)

    def fire_laser(self, shooter, fan=False):
        """Мгновенный луч: пробивает всё до первой стены.
        Веер (fan=True) — три луча с разбросом, каждый слабее."""
        if fan:
            for off in (-PU_LASER_FAN_SPREAD, 0.0, PU_LASER_FAN_SPREAD):
                self._laser_ray(shooter, shooter.angle + off,
                                PU_LASER_FAN_DAMAGE)
        else:
            self._laser_ray(shooter, shooter.angle, PU_LASER_DAMAGE)
        self.sounds.play("laser")

    def _laser_ray(self, shooter, angle_deg, dmg):
        """Один луч: лучевая трассировка до стены, поджигает первого врага.
        Мир большой — луч летит до 2600 px (v2.2)."""
        rad = math.radians(angle_deg)
        sx = shooter.x + math.cos(rad) * (shooter.radius + 16)
        sy = shooter.y + math.sin(rad) * (shooter.radius + 16)
        x, y = sx, sy
        hit = None
        for _ in range(int(2600 / 6)):
            x += math.cos(rad) * 6
            y += math.sin(rad) * 6
            if self.arena.point_blocked(x, y):
                break
            for t in self.tanks:
                if (t.alive and t is not shooter and
                        (t.x - x) ** 2 + (t.y - y) ** 2 < (t.radius + 4) ** 2):
                    hit = t
                    break
            if hit:
                break
        self.effects.beam(sx, sy, x, y, shooter.light)
        self.effects.burst(x, y, shooter.light, 8, 190, 0.3, 3)
        if hit:
            hit.take_damage(dmg, self.effects, self.sounds)

    # ================= зрение (стены + дым) =================
    def vision_blocked(self, x1, y1, x2, y2):
        if self.arena.line_blocked(x1, y1, x2, y2):
            return True
        for s in self.smokes:
            if s.life > 0 and _seg_circle(x1, y1, x2, y2, s.x, s.y, s.radius):
                return True
        return False

    # ================= мины, стены и дым =================
    def _place_mine(self, t):
        """Мина ставится РУКАМИ (игрок — E, бот — решение ИИ).
        Правила игрока: ставим прямо под собой (в 5 клетках или ближе),
        и НИКОГДА во врага — если враг ближе 110 px, ставка отменяется."""
        if t.mine_carried <= 0:
            return False
        others = [o for o in self.tanks if o is not t and o.alive]
        if others:
            enemy = min(others, key=lambda o: (o.x - t.x) ** 2 + (o.y - t.y) ** 2)
            if (t.x - enemy.x) ** 2 + (t.y - enemy.y) ** 2 < PU_MINE_ENEMY_DIST ** 2:
                self.effects.float_text(t.x, t.y - 54, "ВРАГ РЯДОМ!", (255, 90, 90))
                self.sounds.play("ric")
                return False
        t.mine_carried -= 1
        own = [m for m in self.mines if m.owner is t]
        if len(own) >= PU_MINE_MAX:
            self.mines.remove(own[0])
        self.mines.append(Mine(t.x, t.y, t))
        self.sounds.play("mine")
        return True

    def _place_barrier(self, t, angle=None):
        """Стена-бустер: встаёт поперёк курса в паре метров перед танком.
        v3.2: расходуется самая ОБЫЧНАЯ из имеющихся стен (сначала штатные,
        потом прочные, очень прочные и невероятно прочные — редкие ярусы
        бережём). Если там стена/танк — пробуем ближе; совсем нельзя —
        честно скажем."""
        tier = t.next_wall_tier()
        if tier is None:
            return False
        if angle is None:
            angle = t.angle
        rad = math.radians(angle)
        ux, uy = math.cos(rad), math.sin(rad)
        for dist in (BARRIER_DIST, 64, 44, 28):
            cx, cy = t.x + ux * dist, t.y + uy * dist
            br = Barrier(cx, cy, angle + 90, t, tier=tier,
                         team=self.tank_team.get(t))
            # стены/препятствия не трогаем
            if any(self.arena.circle_collides(px, py, BARRIER_THICK)
                   for px, py in (br.p1, (br.x, br.y), br.p2)):
                continue
            # в танки не втыкаем (и в себя, и в чужаков)
            if any(tk.alive and br.blocks_circle(tk.x, tk.y, tk.radius)
                   for tk in self.tanks):
                continue
            t.consume_wall(tier)
            self.barriers.append(br)
            self.arena.set_dynamic(self.barriers)
            self.effects.burst(cx, cy, WALL_TIERS[tier]["color"], 8, 150, 0.3, 3)
            self.sounds.play("ric")
            return True
        self.effects.float_text(t.x, t.y - 54, "ЗДЕСЬ НЕ ПОСТАВИТЬ", (255, 90, 90))
        return False

    def _repair_step(self, t, holding, dt):
        """v3.2: РЕМОНТ СТЕН (просьба игрока: «чтоб можно было чинить
        стены»). Держите H рядом со своей (или командной) стеной — гаечный
        ключ тикает прочность обратно. Чинятся только СВОИ стены: в FFA —
        ваши, в командах — всей вашей стороны.
        v3.3: казённые стены здания ШТУРМА (owner None, team = сторона
        обороны) чинит ТОЛЬКО оборона — атака здание не латает."""
        if not holding or not t.alive:
            return False
        my = self.tank_team.get(t)
        best, best_d = None, WALL_REPAIR_DIST
        for br in self.barriers:
            if br.hp >= br.max_hp:
                continue
            br_team = br.team if br.team is not None \
                else self.tank_team.get(br.owner)
            if br_team != my:
                continue      # чужие стены не чиним
            d = br._dist(t.x, t.y)
            if d < best_d:
                best, best_d = br, d
        if best is None:
            return False
        before = best.hp
        best.hp = min(best.max_hp, best.hp + WALL_REPAIR_RATE * dt)
        # искры у ближнего конца стены — раз в 0.2 с
        self._repair_fx -= dt
        if self._repair_fx <= 0:
            self._repair_fx = 0.2
            self.effects.burst(best.x, best.y, (120, 255, 170), 4, 90, 0.25, 2)
        return best.hp > before

    def _place_turret(self, t):
        """v2.9: ТУРЕЛЬ ставится по R чуть позади танка — сама ищет и
        бьёт ближайшего чужака. Нельзя ставить в стену/танк. Лимит
        PU_TURRET_MAX турелей одного владельца на арене: лишняя —
        старейшая рассыпается."""
        if t.turret_charges <= 0:
            return False
        rad = math.radians(t.angle)
        bx, by = t.x - math.cos(rad) * 60, t.y - math.sin(rad) * 60
        # пробуем позади танка, потом под собой и чуть вперёд
        ok = None
        for cx, cy in ((bx, by), (t.x, t.y),
                       (t.x + math.cos(rad) * 50, t.y + math.sin(rad) * 50)):
            if self.arena.circle_collides(cx, cy, 16):
                continue
            if any(o.alive and (o.x - cx) ** 2 + (o.y - cy) ** 2
                   < (o.radius + 14) ** 2 for o in self.tanks if o is not t):
                continue
            ok = (cx, cy)
            break
        if ok is None:
            self.effects.float_text(t.x, t.y - 54, "ЗДЕСЬ НЕ ПОСТАВИТЬ",
                                    (255, 90, 90))
            return False
        own = [tr for tr in self.turrets if tr.owner is t and tr.alive]
        if len(own) >= PU_TURRET_MAX:
            self.turrets.remove(own[0])
        t.turret_charges -= 1
        self.turrets.append(Turret(ok[0], ok[1], t))
        self.effects.burst(ok[0], ok[1], t.color, 8, 150, 0.3, 3)
        self.sounds.play("mine")
        return True

    def _turrets_step(self, dt):
        """v2.9: турели тикают, ищут цель и стреляют. Снаряд турели —
        обычный Bullet с owner=турель (у неё есть team/color/radius)."""
        for tr in self.turrets[:]:
            tr.update(dt)
            if tr.expired():
                self.turrets.remove(tr)
                self.effects.burst(tr.x, tr.y, tr.color, 10, 160, 0.4, 3)
                continue
            if tr.cd > 0:
                continue
            target = tr.aim(self)
            if target is None:
                continue
            # маленькое упреждение: чуть опережаем цель по её курсу
            ang = math.degrees(math.atan2(target.y - tr.y, target.x - tr.x))
            tr.angle = ang
            tr.cd = TURRET_COOLDOWN
            rad = math.radians(ang)
            self.bullets.append(Bullet(
                tr.x + math.cos(rad) * 20, tr.y + math.sin(rad) * 20,
                ang, tr, damage=TURRET_DAMAGE))
            self.effects.burst(tr.x + math.cos(rad) * 22,
                               tr.y + math.sin(rad) * 22, tr.light,
                               4, 110, 0.15, 2)
            self.sounds.play("shoot")

    def _bullets_vs_turrets(self, b):
        """v2.9: вражеские снаряды пробивают турели (свои пролетают)."""
        if b.dead:
            return
        for tr in self.turrets:
            if not tr.alive or b.owner is tr:
                continue
            if getattr(b.owner, "team", None) == tr.team:
                continue   # снаряд союзной команды турель не трогает
            if (tr.x - b.x) ** 2 + (tr.y - b.y) ** 2 < (tr.radius + 4) ** 2:
                tr.take_damage(b.damage, self.effects, self.sounds)
                b.dead = True
                return

    def _use_emp(self, t):
        """v2.9: носимый ЭМИ-заряд (X, билд «Связист»): тот же blast, что
        у бонуса ЭМИ — валит всех ЧУЖИХ, свои остаются на ходу."""
        if t.emp_charges <= 0 or not t.alive:
            return False
        t.emp_charges -= 1
        self._emp_blast(t)
        return True

    def _fire_nova(self, t):
        """v3.1: КРУГОВОЙ АД (V, ТОЛЬКО билд «Круговой ад»): одноразовый
        залп — NOVA_SHELLS снарядов веером во ВСЕ стороны. v3.5: залп
        стреляет ТЕМ ТИПОМ СНАРЯДА, что выбран в ангаре (панель СНАРЯД):
        РАЗРЫВНОЙ взрывается осколками вокруг каждого попадания,
        БРОНЕБОЙНЫЙ пробивает броню без рикошетов и летит злее,
        ЗАЖИГАТЕЛЬНЫЙ оставляет 45 огненных луж, ЗВЁЗДНЫЙ рвётся на 5
        осколков ЗВЕЗДОЙ — итого 45 снарядов = 225 осколков. Бонус
        кругового ада x1.10 поверх типа снаряда. Заряд всего один и
        тратится целиком: второй раз до следующего раунда не выстрелит.
        Снаряды рождаются за габаритом танка — владельца не задевают,
        союзников не бьют (командные проверки снарядов общие)."""
        if t is None or not t.alive or t.nova_charges <= 0:
            return False
        t.nova_charges -= 1
        shell = getattr(t, "shell_type", "std")
        dmg = BULLET_DAMAGE * NOVA_DAMAGE_MULT   # x1.10 — суть билда
        spd = 1.0
        if shell == "he":
            dmg *= 0.80
        elif shell == "ap":
            dmg *= 1.30
            spd = 1.30
        elif shell == "fire":
            dmg *= 0.85
        elif shell == "star":
            dmg *= SHELL_STAR_DAMAGE_MULT
        dmg = round(dmg)
        off = t.radius + 6.0
        for i in range(NOVA_SHELLS):
            ang = 360.0 * i / NOVA_SHELLS
            rad = math.radians(ang)
            self.bullets.append(Bullet(
                t.x + math.cos(rad) * off, t.y + math.sin(rad) * off,
                ang, t, damage=dmg, speed_mult=spd,
                element=("fire" if shell == "fire" else None),
                bounces=(0 if shell == "ap" else None),
                shell=shell, he=(shell == "he"),
                star=(shell == "star")))
        self.effects.ring(t.x, t.y, (255, 60, 110), 130, 0.4)
        self.effects.burst(t.x, t.y, (255, 60, 110), 26, 380, 0.5, 5)
        self.effects.shake(4, 0.2)
        self.sounds.play("explode")
        self.effects.float_text(t.x, t.y - 60, "КРУГОВОЙ АД!", (255, 60, 110))
        return True

    def _emp_blast(self, t):
        """ЭМИ-взрыв вокруг танка t (бонус «Э» или носимый заряд по X):
        v2.6.2 — бьёт ТОЛЬКО ЧУЖИХ, союзники подобравшего целы (над
        ними всплывает «СВОИ!»). В FFA у каждого танка своя команда,
        поэтому там встают все, кроме владельца."""
        info = PU_INFO["freeze"]
        my = self.tank_team.get(t)
        for o in self.tanks:
            if o is t or not o.alive:
                continue
            if my is not None and self.tank_team.get(o) == my:
                self.effects.float_text(o.x, o.y - 54, "СВОИ!",
                                        TEAM_ALLY_COLOR)
                continue
            o.frozen_t = PU_FREEZE_TIME
            self.effects.float_text(o.x, o.y - 54, "ЭМИ!", info["color"])
        self.sounds.play("freeze")

    def _bullet_vs_barriers(self, b):
        """Снаряд врезался в стену-барьер: стена теряет прочность."""
        if b.dead:
            return
        for br in self.barriers:
            if _pt_seg_dist(b.x, b.y, br.p1, br.p2) < BARRIER_THICK / 2 + 5:
                br.hp -= b.damage
                b.dead = True
                self.effects.burst(b.x, b.y, b.color, 8, 170, 0.3, 3)
                self.sounds.play("ric")
                if br.hp <= 0:
                    self.barriers.remove(br)
                    self.effects.burst(br.x, br.y, (205, 210, 225), 20, 320, 0.5, 4)
                    self.effects.ring(br.x, br.y, (205, 210, 225), 70, 0.35)
                    self.effects.shake(4, 0.2)
                    self.sounds.play("explode")
                return

    def _mines_step(self, dt):
        """Мины (v3.0 — ПОСТОЯННЫЕ: таймера жизни больше нет, лежат,
        пока не рванут под чужаком)."""
        for m in self.mines[:]:
            m.update(dt)
            if not m.armed:
                continue
            for t in self.tanks:
                if (t.alive and t is not m.owner and
                        (t.x - m.x) ** 2 + (t.y - m.y) ** 2 < PU_MINE_RADIUS ** 2):
                    t.take_damage(PU_MINE_DAMAGE, self.effects, self.sounds)
                    self.effects.ring(m.x, m.y, (255, 140, 0), 70, 0.4)
                    self.effects.burst(m.x, m.y, (255, 140, 0), 18, 320, 0.5, 4)
                    self.effects.shake(5, 0.25)
                    self.sounds.play("explode")
                    self.mines.remove(m)
                    break

    def _smokes_step(self, dt):
        for s in self.smokes[:]:
            s.update(dt)
            if s.life <= 0:
                self.smokes.remove(s)

    # ================= бонусы =================
    def _powerups_step(self, dt):
        self.powerup_t -= dt
        if self.powerup_t <= 0 and len(self.powerups) < POWERUP_MAX:
            x, y = self.arena.free_spot(
                avoid=tuple((t.x, t.y) for t in self.tanks if t.alive))
            self.powerups.append(PowerUp(x, y, random.choice(list(PU_INFO))))
            self.powerup_t = POWERUP_INTERVAL
        for pu in self.powerups[:]:
            for t in self.tanks:
                if t.alive and (t.x - pu.x) ** 2 + (t.y - pu.y) ** 2 < (t.radius + 18) ** 2:
                    self._apply_pickup(t, pu)
                    self.powerups.remove(pu)
                    break

    def _apply_pickup(self, t, pu):
        info = PU_INFO[pu.kind]
        if pu.kind == "smoke":
            self.smokes.append(Smoke(t.x, t.y))
            self.sounds.play("smoke")
        elif pu.kind == "freeze":
            # v2.6.2: ЭМИ бьёт ТОЛЬКО ЧУЖИХ — общая логика с носимым
            # зарядом (X, билд «Связист») вынесена в _emp_blast
            self._emp_blast(t)
        else:
            # мина и стена носятся в боекомплекте (E / Q) — всё в apply_powerup
            t.apply_powerup(pu.kind)
        if t is self.player:
            self.points += SCORE_PICKUP   # очки за подбор бонуса
        self.effects.float_text(t.x, t.y - 54, info["name"], info["color"])
        self.sounds.play("pickup")

    # ================= отрисовка =================
    def draw(self):
        self._click_zones = []   # кликабельные зоны пересобираются каждый кадр
        ox, oy = self.effects.offset()
        ox -= self.cam[0]        # v2.2: мир больше окна — рисуем со сдвигом
        oy -= self.cam[1]        #      камеры (плюс тряска от взрывов)
        self.world.fill((0, 0, 0))
        self.arena.draw(self.world, ox, oy)

        in_battle = self.state in ("intro", "fight", "round_end", "pause", "match_end")
        if in_battle:
            if self.is_assault:      # v3.2: точка захвата — под всем остальным
                self._draw_capture_point(self.world, ox, oy)
            for pu in self.powerups:
                pu.draw(self.world, ox, oy)
            for m in self.mines:
                m.draw(self.world, ox, oy)
            for br in self.barriers:
                br.draw(self.world, ox, oy)
            for fz in self.fire_zones:   # v3.0: огненные лужи под танками
                fz.draw(self.world, ox, oy)
            for tr in self.turrets:      # v2.9: турели рисуются под танками
                tr.draw(self.world, ox, oy)
            for b in self.bullets:
                b.draw(self.world, ox, oy)
            for t in reversed(self.tanks):   # игрок рисуется поверх ботов
                if t.alive:
                    pad = self._team_pad(t)   # v2.6: подсветка команд
                    if pad is not None:
                        self.world.blit(
                            pad, (int(t.x + ox - pad.get_width() / 2),
                                  int(t.y + oy - pad.get_height() / 2)))
                    t.draw(self.world, ox, oy)
                    self._draw_badge(t, ox, oy)   # v3.4: приказы и командир
            self.effects.draw(self.world, ox, oy)
            for s in self.smokes:
                s.draw(self.world, ox, oy)
        self.screen.blit(self.world, (0, 0))

        if self.state == "menu":
            self._draw_menu()
        elif self.state == "select":
            self._draw_select()
        elif self.state == "editor":
            self._draw_editor()               # v3.3: редактор карт
        elif self.state == "table":
            self._draw_table()
        elif in_battle:
            self._draw_minimap()      # v2.2: карта большая — нужен ориентир
            self._draw_hud()
            if self.state == "fight" and self.orders_open:
                self._draw_orders()   # v3.5: окно приказов поверх HUD
            if self.state == "intro":
                self._banner("РАУНД %d" % self.round, COL_GOLD,
                             "карта «%s»" % self.arena.name)
            elif self.state == "round_end":
                if self.team_mode:
                    # v3.3: в ШТУРМЕ победителя определяем по РОЛИ
                    # (игрок мог быть атакой): оборона выстояла или
                    # точка захвачена — кто бы ни был какой стороной
                    def _asm_banner(w):
                        if not self.is_assault:
                            return None
                        return ("ОБОРОНА ВЫДЕРЖАЛА"
                                if w == self.assault_def_team
                                else "ТОЧКУ ЗАХВАТИЛИ")
                    if self.winner == 0:
                        self._banner(_asm_banner(0)
                                     or "РАУНД ЗА ВАШЕЙ КОМАНДОЙ", COL_P1,
                                     sub2="+%d ОЧКОВ" % SCORE_ROUND_WIN)
                    elif self.winner == 1:
                        col = self.foes[0].color if self.foes else COL_P2
                        self._banner(_asm_banner(1)
                                     or ("РАУНД ЗА БОССОМ" if self.mode == 7
                                         else "РАУНД ЗА КОМАНДОЙ БОТОВ"), col)
                    else:
                        self._banner("НИЧЬЯ", COL_TEXT,
                                     sub2="+%d ОЧКОВ" % SCORE_ROUND_DRAW)
                elif self.winner == 0:
                    self._banner("РАУНД ЗА ИГРОКОМ", COL_P1,
                                 sub2="+%d ОЧКОВ" % SCORE_ROUND_WIN)
                elif self.winner > 0:
                    bt = self.tanks[self.winner]
                    self._banner("РАУНД ЗА %s"
                                 % (bt.display_name or BOT_NAMES[self.winner - 1]),
                                 bt.color)
                else:
                    self._banner("НИЧЬЯ", COL_TEXT,
                                 sub2="+%d ОЧКОВ" % SCORE_ROUND_DRAW)
            elif self.state == "match_end":
                self._draw_match_end()
                for i, (lbl, kd, dta) in enumerate((
                        ("РЕВАНШ (Enter)", "me_rematch", None),
                        ("АНГАР (A)", "to_garage", None),
                        ("ТАБЛИЦА (T)", "open_table", "match_end"),
                        ("МЕНЮ (M)", "me_menu", None))):
                    self._button(SCREEN_W / 2 + (i - 1.5) * 240,
                                 SCREEN_H / 2 + 152, lbl, kd, data=dta, w=222)
            elif self.state == "pause":
                self._banner("ПАУЗА", COL_TEXT,
                             "Esc — продолжить   A — ангар   M — меню")
                for i, (lbl, kd) in enumerate((("ПРОДОЛЖИТЬ", "p_resume"),
                                               ("АНГАР", "to_garage"),
                                               ("МЕНЮ", "p_menu"))):
                    self._button(SCREEN_W / 2 + (i - 1) * 258,
                                 SCREEN_H / 2 + 118, lbl, kd, w=236)

        # режим установки бонуса из консоли (веер и другие — кликом на карту)
        if self.con_place and in_battle:
            self._draw_place_hint()
        # консоль разработчика — рисуется поверх всего (в конце кадра)
        if self.con_open:
            self._draw_console()

    def _draw_capture_point(self, surf, ox=0, oy=0):
        """v3.2: ТОЧКА ЗАХВАТА ШТУРМА — пульсирующее золотое кольцо;
        v3.3: стоит ВНУТРИ здания штурмовой карты; по мере захвата
        заливка и дуга краснеют."""
        x, y = int(self.cap_xy[0] + ox), int(self.cap_xy[1] + oy)
        r = ASSAULT_POINT_R
        t = pygame.time.get_ticks() / 1000.0
        k = max(0.0, min(1.0, self.cap_progress / ASSAULT_CAPTURE_T))
        col = (255, 208 - int(148 * k), int(60 * (1 - k) + 40))
        # тёмный диск под точкой, чтобы читалась на любой карте
        pygame.draw.circle(surf, (24, 30, 56), (x, y), r)
        pygame.draw.circle(surf, col, (x, y), r, 4)
        # пульсирующее внутреннее кольцо
        rr = int((r - 14) * (0.55 + 0.06 * math.sin(t * 2.2)))
        pygame.draw.circle(surf, col, (x, y), rr, 1)
        # крест прицела в центре
        pygame.draw.line(surf, col, (x - 16, y), (x + 16, y), 2)
        pygame.draw.line(surf, col, (x, y - 16), (x, y + 16), 2)
        # дуга прогресса захвата (красная — тем длиннее, чем ближе захват)
        if k > 0.001:
            rect = pygame.Rect(x - r + 8, y - r + 8, (r - 8) * 2, (r - 8) * 2)
            pygame.draw.arc(surf, (255, 70, 70), rect,
                            math.radians(-90), math.radians(-90 + 360 * k), 5)

    def _banner(self, text, color, sub="", sub2=None):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((5, 6, 14, 150))
        self.screen.blit(dim, (0, 0))
        img = get_font(72).render(text, True, color)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 - 20)))
        if sub:
            img2 = get_font(26, bold=False).render(sub, True, COL_DIM)
            self.screen.blit(img2, img2.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 + 40)))
        if sub2:
            img3 = get_font(24).render(sub2, True, COL_GOLD)
            self.screen.blit(img3, img3.get_rect(
                center=(SCREEN_W / 2, SCREEN_H / 2 + (84 if sub else 46))))

    def _draw_menu(self):
        self.screen.fill((10, 12, 26))   # и из паузы в меню тоже чистый фон
        img = get_font(110).render("DUEL", True, COL_TEXT)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 150)))
        sub = get_font(30, bold=False).render("танковая дуэль", True, COL_GOLD)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W / 2, 235)))
        lines = [
            "W/S — вперёд и назад   A/D — поворот   Пробел — выстрел   F11 — ВО ВЕСЬ ЭКРАН",
            "E — ОКНО ПРИКАЗОВ: 1 ДЕРЖАТЬ · 2 ЗА МНОЙ · 3 ПРИКРЫВАЙ · 4 В АТАКУ · 5 К ТОЧКЕ · 6 ОТСТУПАЙ · 7 ПО МОЕЙ ЦЕЛИ · 8 СВОБОДНО",
            "В окне ПЛИТКИ БОТОВ (клик или Tab — кому приказ) и «ВСЯ КОМАНДА» (T). Бой не останавливается.",
            "F — мина   Q — стена   R — ТУРЕЛЬ   H — РЕМОНТ   X — ЭМИ   V — КРУГОВОЙ АД выбранным снарядом (звёздный = 225 осколков)",
            "Вражеский ★ КОМАНДИР приказывает своим. Консоль (Ё): «помощь» с переносом строк и прокруткой.", 
        ]
        y = 290
        for s in lines:
            img = get_font(21, bold=False).render(s, True, COL_DIM)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y)))
            y += 23
        # выбор сложности (1/2/3 или клик)
        y += 4
        img = get_font(20, bold=False).render("Сложность бота (1/2/3 или клик):",
                                              True, COL_DIM)
        self.screen.blit(img, img.get_rect(midright=(SCREEN_W / 2 - 120, y)))
        for i, dkey in enumerate((1, 2, 3)):
            color = COL_GOLD if self.difficulty == dkey else (70, 80, 120)
            img = get_font(20).render("%d %s" % (dkey, DIFF_NAMES[dkey]),
                                      True, color)
            r = img.get_rect(midleft=(SCREEN_W / 2 - 100 + i * 135, y))
            hov = r.inflate(14, 12).collidepoint(self._mouse)
            pygame.draw.rect(self.screen, COL_P1 if hov else (40, 50, 90),
                             r.inflate(14 if hov else 10, 12 if hov else 8),
                             2, border_radius=7)
            self.screen.blit(img, r)
            self._click_zones.append((r.inflate(14, 12), "menu_diff", dkey))
        # РЕЖИМ БОЯ (v2.1+): два ряда кнопок (v2.7) — FFA и команды.
        # раскладка динамическая, шрифт 16, зазор 16
        y += 40
        img = get_font(20, bold=False).render(
            "Режим боя (клик; F2–F10):", True, COL_DIM)
        self.screen.blit(img, img.get_rect(midright=(SCREEN_W / 2 - 120, y)))
        mode_lbl = {2: "1×1", 3: "1×1×1", 4: "1×1×1×1", 5: "1×1×1×1×1",
                    6: "2×2", 7: "2×БОСС", 8: "3×3", 9: "4×4", 10: "5×5",
                    11: "FFA×6", 12: "FFA×7", 13: "FFA×8",
                    14: "FFA×9", 15: "FFA×10",
                    16: "6×6", 17: "7×7", 18: "8×8", 19: "9×9",
                    20: "ЗАВАРУШКА 10×10",
                    21: "ШТУРМ 1×1", 22: "ШТУРМ 2×2", 23: "ШТУРМ 3×3",
                    24: "ШТУРМ 4×4", 25: "ШТУРМ 5×5", 26: "ШТУРМ 6×6",
                    27: "ШТУРМ 7×7"}
        gap = 18
        fmode = get_font(16)

        def mode_row(modes, yy):
            btns = [(fmode.render(mode_lbl[m], True,
                                  COL_GOLD if self.mode == m else (70, 80, 120)), m)
                    for m in modes]
            total = sum(im.get_width() for im, _ in btns) + gap * (len(btns) - 1)
            bx = SCREEN_W / 2 - 100 + (724 - total) / 2.0   # полоса 540..1264
            for im, m in btns:
                r = im.get_rect(midleft=(bx, yy))   # левый край ровно в bx
                hov = r.inflate(14, 12).collidepoint(self._mouse)
                pygame.draw.rect(self.screen, COL_P1 if hov else (40, 50, 90),
                                 r.inflate(14 if hov else 10, 12 if hov else 8),
                                 2, border_radius=7)
                self.screen.blit(im, r)
                self._click_zones.append((r.inflate(14, 12), "menu_mode", m))
                bx += im.get_width() + gap

        mode_row((2, 3, 4, 5, 11, 12, 13, 14, 15), y)   # все против всех
        y += 34
        mode_row((6, 7, 8, 9, 10, 16, 17, 18, 19, 20), y)  # команды, босс и армии
        y += 34
        mode_row(ASSAULT_MODES, y)                     # v3.2: ШТУРМ 1×1…7×7
        # v3.3: СТОРОНА В ШТУРМЕ — ОБОРОНА / АТАКА / СЛУЧАЙНО (G или клик):
        # «можно выбирать атака ты или оборона»
        y += 30
        img = get_font(20, bold=False).render("Ваша сторона в ШТУРМЕ (G/клик):",
                                              True, COL_DIM)
        self.screen.blit(img, img.get_rect(midright=(SCREEN_W / 2 - 120, y)))
        side_lbl = (("def", "ОБОРОНА"), ("atk", "АТАКА"), ("rand", "СЛУЧАЙНО"))
        for i, (skey, slbl) in enumerate(side_lbl):
            color = COL_GOLD if self.assault_side == skey else (70, 80, 120)
            img = get_font(20).render(slbl, True, color)
            r = img.get_rect(midleft=(SCREEN_W / 2 - 100 + i * 165, y))
            hov = r.inflate(14, 12).collidepoint(self._mouse)
            pygame.draw.rect(self.screen, COL_P1 if hov else (40, 50, 90),
                             r.inflate(14 if hov else 10, 12 if hov else 8),
                             2, border_radius=7)
            self.screen.blit(img, r)
            self._click_zones.append((r.inflate(14, 12), "menu_side", skey))
        # статистика матчей и рекорд
        y += 36
        st = "Побед: %d   Поражений: %d   Ничьих: %d   ·   Рекорд очков: %d" % (
            self.stats["wins"], self.stats["losses"], self.stats["draws"],
            self.stats.get("best_score", 0))
        img = get_font(18, bold=False).render(st, True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y)))
        # большие кнопки: в ангар, В РЕДАКТОР КАРТ (v3.3) и в таблицу счёта
        self._button(SCREEN_W / 2 - 250, y + 54, "В АНГАР ▶", "menu_start",
                     w=232, h=48, fs=21)
        self._button(SCREEN_W / 2, y + 54, "РЕДАКТОР КАРТ", "menu_editor",
                     w=232, h=48, fs=21)
        self._button(SCREEN_W / 2 + 250, y + 54, "ТАБЛИЦА СЧЕТА", "open_table",
                     data="menu", w=232, h=48, fs=19)
        img = get_font(15, bold=False).render(
            "или Enter / T / M — мышью можно нажать любую кнопку", True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y + 96)))
        # версия
        img = get_font(16, bold=False).render("v3.6 · ШТАБ", True, (60, 66, 95))
        self.screen.blit(img, img.get_rect(bottomright=(SCREEN_W - 12,
                                                        SCREEN_H - 12)))

    # ================= выбор стороны и РЕДАКТОР КАРТ (v3.3) =================
    ED_TOOLS_ASSAULT = (("#", "СТЕНА"), ("S", "ПРОЧНАЯ"), ("H", "ОЧ.ПРОЧНАЯ"),
                        ("U", "НЕВЕРОЯТН."), ("P", "ТОЧКА"),
                        ("D", "СПАВН ОБОРОНЫ"), ("A", "СПАВН АТАКИ"),
                        (".", "ЛАСТИК"))
    ED_TOOLS_BATTLE = (("#", "СТЕНА"), ("S", "ПРОЧНАЯ"), ("H", "ОЧ.ПРОЧНАЯ"),
                       ("U", "НЕВЕРОЯТН."), ("D", "СПАВН СОЮЗНИКОВ"),
                       ("A", "СПАВН ВРАГОВ"), (".", "ЛАСТИК"))
    ED_CELL = 19          # клетка редактора на экране (48*19=912, 27*19=513)

    @property
    def ed_grid(self):
        """Сетка ТЕКУЩЕГО типа карты (v3.4: у ШТУРМА и БОЯ сетки свои)."""
        return self.ed_grids[self.ed_kind]

    def _cycle_assault_side(self):
        """v3.3: G в меню — ОБОРОНА → АТАКА → СЛУЧАЙНО → ОБОРОНА…"""
        order = ("def", "atk", "rand")
        self.assault_side = order[(order.index(self.assault_side) + 1) % 3]
        self.sounds.play("ric")

    # ============ КОМАНДИР: приказы ботам (v3.4/v3.5) ============

    # v3.6: ВОСЕМЬ ПРИКАЗОВ — список для окна приказов (клавиши 1–8)
    ORDER_LIST = ("hold", "follow", "cover", "attack", "point",
                  "retreat", "target", "free")
    ORDER_INFO = {
        "hold":    ("ДЕРЖАТЬ ПОЗИЦИЮ", "встанет и отстреливается с места",
                    (255, 208, 0)),
        "follow":  ("ЗА МНОЙ", "идёт за вами и прикрывает спину",
                    (120, 255, 220)),
        "cover":   ("ПРИКРЫВАЙ", "жмётся к вам и бьёт тех, кто ближе к вам",
                    (170, 255, 120)),
        "attack":  ("В АТАКУ", "сам давит ближайшего врага",
                    (255, 120, 60)),
        "point":   ("К ТОЧКЕ", "идёт к точке сбора и держит её",
                    (120, 200, 255)),
        "retreat": ("ОТСТУПАЙ", "уходит к своей базе и обороняет её",
                    (255, 170, 220)),
        "target":  ("ПО МОЕЙ ЦЕЛИ", "фокус на враге, что стоит у прицела",
                    (255, 95, 95)),
        "free":    ("СВОБОДНО", "воюет по собственному уму",
                    (160, 200, 255)),
    }
    ORDER_KEYMAP = {pygame.K_1: "hold", pygame.K_2: "follow",
                    pygame.K_3: "cover", pygame.K_4: "attack",
                    pygame.K_5: "point", pygame.K_6: "retreat",
                    pygame.K_7: "target", pygame.K_8: "free",
                    pygame.K_KP1: "hold", pygame.K_KP2: "follow",
                    pygame.K_KP3: "cover", pygame.K_KP4: "attack",
                    pygame.K_KP5: "point", pygame.K_KP6: "retreat",
                    pygame.K_KP7: "target", pygame.K_KP8: "free"}
    # v3.6: клавиши, которые открытое окно приказов перехватывает целиком
    ORDERS_UI_KEYS = (pygame.K_ESCAPE, pygame.K_e, pygame.K_t,
                      pygame.K_TAB) + tuple(ORDER_KEYMAP)

    def _allies_alive(self):
        """Живые боты-союзники (в FFA список пуст — командовать некем)."""
        return [b for b in self.bots
                if b.alive and self.tank_team.get(b) == 0]

    def _order_target(self):
        """Бот, БЛИЖАЙШИЙ К ПРИЦЕЛУ (курсору на арене); далеко от прицела
        подчинённых нет — приказ уходит ближайшему к вам."""
        allies = self._allies_alive()
        if not allies:
            return None
        wx = self._mouse[0] + self.cam[0]
        wy = self._mouse[1] + self.cam[1]
        near = min(allies, key=lambda b: (b.x - wx) ** 2 + (b.y - wy) ** 2)
        if math.hypot(near.x - wx, near.y - wy) > 560:
            near = min(allies, key=lambda b:
                       (b.x - self.player.x) ** 2
                       + (b.y - self.player.y) ** 2)
        return near

    def _command_open(self, all_=False):
        """v3.6: E — ОТКРЫТЬ ОКНО ПРИКАЗОВ (Shift+E — сразу с целью
        «ВСЯ КОМАНДА»). По умолчанию выбран бот у прицела, в окне можно
        тыкать в конкретные ПЛИТКИ ботов или идти Tab. Мёртвый
        командовать не может."""
        if not self.player.alive:
            return
        self.orders_open = True
        self.orders_all = bool(all_)
        tb = self._order_target()
        self.orders_pick = set() if all_ else ({tb} if tb else set())
        self.sounds.play("ric")

    def _order_point(self):
        """Точка сбора для приказа «К ТОЧКЕ»: в ШТУРМЕ — точка захвата
        (здание), в обычных командных — центр арены."""
        if self.is_assault:
            return (float(self.cap_xy[0]), float(self.cap_xy[1]))
        return (self.arena.w / 2.0, self.arena.h / 2.0)

    def _retreat_point(self):
        """v3.6: СВОЯ БАЗА для приказа «ОТСТУПАЙ»: в ШТУРМЕ при обороне —
        точка захвата (здание), иначе — центр своей стартовой шеренги
        (base0, считается на старте раунда); без данных — низ карты."""
        if self.is_assault and getattr(self, "assault_def_team", 0) == 0:
            return (float(self.cap_xy[0]), float(self.cap_xy[1]))
        if getattr(self, "base0", None):
            return (float(self.base0[0]), float(self.base0[1]))
        return (self.arena.w / 2.0, self.arena.h * 0.85)

    def _aim_enemy(self):
        """v3.6: ЧУЖАК, БЛИЖАЙШИЙ К ПРИЦЕЛУ — цель приказа «ПО МОЕЙ
        ЦЕЛИ». В командах — вся чужая сторона, в FFA чужаки и так все."""
        foes = [t for t in self.tanks
                if t.alive and self.tank_team.get(t, -1) != 0]
        if not foes:
            return None
        wx = self._mouse[0] + self.cam[0]
        wy = self._mouse[1] + self.cam[1]
        return min(foes, key=lambda t: (t.x - wx) ** 2 + (t.y - wy) ** 2)

    def _command_order(self, order, all_=False):
        """v3.6: применить ПРИКАЗ (8 видов) выбранным в окне ботам
        (orders_pick); пустой выбор — бот у прицела; all_=True — ВСЕЙ
        команде разом. Приказы игрока вечны, пока их не сменишь
        (order_t = 0). В FFA подчинённых нет — там каждый сам за себя."""
        if not self.player.alive:
            return
        allies = self._allies_alive()
        if not allies:
            self.effects.float_text(self.player.x, self.player.y - 64,
                                    "НЕТ ПОДЧИНЁННЫХ (FFA)", (255, 90, 90))
            self.sounds.play("ric")
            return
        if all_:
            targets = allies          # T / Shift+E — всей команде разом
        else:
            picked = [b for b in allies if b in self.orders_pick]
            targets = picked or [self._order_target()]
            if not targets or targets[0] is None:
                return
        for b in targets:
            if order == "free":
                b.order = None
            elif order == "hold":
                b.order = "hold"
                b.order_xy = (b.x, b.y)
                b.order_t = 0.0
            elif order == "point":
                b.order = "point"
                b.order_xy = self._order_point()
                b.order_t = 0.0
            elif order == "retreat":     # v3.6: к своей базе
                b.order = "retreat"
                b.order_xy = self._retreat_point()
                b.order_t = 0.0
            elif order == "target":      # v3.6: фокус на чужаке у прицела
                b.order = "target"
                b.order_tgt = self._aim_enemy()
                b.order_t = 0.0
            elif order == "attack":
                b.order = "attack"
                b.order_t = 0.0
            elif order == "cover":       # v3.6: рядом с командиром
                b.order = "cover"
                b.order_t = 0.0
            else:                     # follow
                b.order = "follow"
                b.order_t = 0.0
            name, _desc, col = self.ORDER_INFO[order]
            self.effects.float_text(b.x, b.y - 58, name + "!", col)
        self.sounds.play("laser")
        # вражеский командир заметил манёвр — командует быстрее
        self.cmd_t = min(self.cmd_t, CMD_REACT_T)

    def _enemy_commander(self):
        """v3.4: ВРАЖЕСКИЙ КОМАНДИР — у команды ботов СВОЙ командир
        (звезда ★ над танком): он оставляет часть ботов ДЕРЖАТЬ рубежи
        (на 8–12 секунд, потом снова свободны), v3.5 — ещё часть бросает
        В АТАКУ (давить игрока и его союзников). Если чужаков стало
        заметно меньше — ВСЯ команда идёт в атаку."""
        alive = [b for b in self.foes if b.alive]
        if len(alive) < 2:
            return
        ours = sum(1 for t in self.tanks
                   if t.alive and self.tank_team.get(t) == 0)
        if len(alive) <= ours // 2:
            # проигрываем по живым — оборона не по чину, ВСЕ В АТАКУ
            for b in alive:
                if b.order is None or b.order == "hold":
                    b.order = "attack"
                    b.order_t = CMD_HOLD_MAX
            lead = next((b for b in alive if b.is_commander), alive[0])
            self.effects.float_text(lead.x, lead.y - 58, "ВСЕ В АТАКУ!",
                                    (255, 120, 120))
            return
        free = [b for b in alive if b.order is None and not b.is_commander]
        random.shuffle(free)
        n_hold = max(1, int(len(free) * 0.4)) if free else 0
        n_atk = max(1, int(len(free) * 0.3)) if free else 0
        for b in free[:n_hold]:
            b.order = "hold"
            b.order_xy = (b.x, b.y)
            b.order_t = random.uniform(CMD_HOLD_MIN, CMD_HOLD_MAX)
            self.effects.float_text(b.x, b.y - 58, "ПРИКАЗ: ДЕРЖАТЬ",
                                    (255, 150, 150))
        for b in free[n_hold:n_hold + n_atk]:
            # v3.5: командир бросает часть ботов В АТАКУ
            b.order = "attack"
            b.order_t = random.uniform(CMD_HOLD_MIN, CMD_HOLD_MAX)
            self.effects.float_text(b.x, b.y - 58, "ПРИКАЗ: В АТАКУ",
                                    (255, 150, 150))

    def _draw_badge(self, t, ox, oy):
        """v3.4: значки НАД танком — звезда КОМАНДИРА и текущий ПРИКАЗ
        (ДЕРЖИТ / ЗА ТОБОЙ / В АТАКЕ / К ТОЧКЕ — v3.5). Свои —
        золотым/цианом, вражьи приказы — красноватым, чтобы видно, кто
        зарылся в оборону."""
        lab, col = None, COL_GOLD
        my = self.tank_team.get(t)
        friend = (my == 0)
        if t.order == "hold":
            lab = "ДЕРЖИТ"
            col = (255, 208, 0) if friend else (255, 130, 130)
        elif t.order == "follow":
            lab, col = "ЗА ТОБОЙ", (120, 255, 220) if friend else (255, 130, 130)
        elif t.order == "attack":
            lab, col = "В АТАКЕ", ((255, 150, 60) if friend
                                   else (255, 130, 130))
        elif t.order == "point":
            lab, col = "К ТОЧКЕ", ((120, 200, 255) if friend
                                   else (255, 130, 130))
        elif t.order == "cover":               # v3.6
            lab, col = "ПРИКРЫВАЕТ", ((170, 255, 120) if friend
                                      else (255, 130, 130))
        elif t.order == "retreat":             # v3.6
            lab, col = "ОТСТУПАЕТ", ((255, 170, 220) if friend
                                     else (255, 130, 130))
        elif t.order == "target":              # v3.6
            lab, col = "НА ЦЕЛИ", ((255, 95, 95) if friend
                                   else (255, 130, 130))
        if getattr(t, "is_commander", False):
            lab = "★ КОМАНДИР" if lab is None else "★ " + lab
            col = (255, 208, 0) if friend else (255, 130, 130)
        if not lab:
            return
        img = get_font(13).render(lab, True, col)
        self.world.blit(img, img.get_rect(
            midbottom=(int(t.x + ox), int(t.y + oy - t.radius - 8))))

    # ============ ОКНО ПРИКАЗОВ (v3.5) ============

    def _draw_orders(self):
        """v3.6: окно приказов командира — открывается на E (Shift+E —
        сразу с целью «ВСЯ КОМАНДА»). ВОСЕМЬ приказов — клавиши 1–8 или
        клик по строке. КОГО ПРИКАЗЫВАЕМ: ПЛИТКИ БОТОВ (клик — выбрать
        одного, Shift+клик — нескольких; Tab — следующий бот), плитка
        «ВСЯ КОМАНДА» и T — всем разом. E/Esc закрывает. Бой НЕ
        останавливается. В FFA подчинённых нет — окно честно пишет."""
        allies = self._allies_alive()
        # высота панели под число ботов (плитки — до 5 в ряд)
        per_row, tw, th, gap = 5, 108, 32, 8
        rows = 0
        if allies:
            rows = (len(allies) + 1 + per_row - 1) // per_row   # + «ВСЕ»
        panel_h = 50 + (22 + rows * (th + gap) + 30 if allies else 0) \
            + 8 * 46 + 38
        panel = pygame.Rect(0, 0, 640, panel_h)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((4, 6, 16, 135))
        self.screen.blit(dim, (0, 0))
        pygame.draw.rect(self.screen, (16, 20, 40), panel, border_radius=12)
        pygame.draw.rect(self.screen, COL_GOLD, panel, 2, border_radius=12)
        img = get_font(24).render("ПРИКАЗЫ КОМАНДИРА", True, COL_GOLD)
        self.screen.blit(img, img.get_rect(midtop=(panel.centerx,
                                                   panel.y + 12)))
        # крестик-закрыть
        xr = pygame.Rect(panel.right - 40, panel.y + 10, 28, 28)
        hov = xr.collidepoint(self._mouse)
        pygame.draw.rect(self.screen, (60, 26, 40) if hov else (40, 30, 46),
                         xr, border_radius=7)
        xi = get_font(17).render("X", True, (255, 120, 140))
        self.screen.blit(xi, xi.get_rect(center=xr.center))
        self._click_zones.append((xr, "ord_close", None))

        y = panel.y + 50
        if not allies:
            img = get_font(17, bold=False).render(
                "В FFA ПОДЧИНЁННЫХ НЕТ — командир работает в командных",
                True, (255, 130, 130))
            self.screen.blit(img, img.get_rect(midtop=(panel.centerx, y)))
            img = get_font(17, bold=False).render(
                "режимах (2на2…10на10) и в ШТУРМЕ",
                True, (255, 130, 130))
            self.screen.blit(img, img.get_rect(
                midtop=(panel.centerx, y + 24)))
        else:
            # ---- КОГО ПРИКАЗЫВАЕМ: плитки ботов + «ВСЯ КОМАНДА» ----
            img = get_font(13, bold=False).render(
                "КОГО ПРИКАЗЫВАЕМ (клик — выбрать, Shift+клик — нескольких, Tab — дальше):",
                True, COL_DIM)
            self.screen.blit(img, (panel.x + 26, y))
            y += 22
            for idx, b in enumerate(allies + [None]):    # None = «ВСЕ»
                r, c = divmod(idx, per_row)
                rect = pygame.Rect(panel.x + 26 + c * (tw + gap),
                                   y + r * (th + gap), tw, th)
                if b is None:
                    sel = self.orders_all
                    label = "ВСЯ КОМАНДА"
                    kind, data = "ord_all", None
                else:
                    sel = not self.orders_all and b in self.orders_pick
                    label = (b.display_name or "СОЮЗНИК")[:12]
                    kind, data = "ord_bot", b
                hov = rect.collidepoint(self._mouse)
                pygame.draw.rect(self.screen,
                                 (52, 62, 110) if sel
                                 else ((46, 58, 104) if hov
                                       else (24, 30, 58)),
                                 rect, border_radius=8)
                pygame.draw.rect(self.screen,
                                 COL_GOLD if sel
                                 else ((90, 100, 150) if hov
                                       else (52, 62, 104)),
                                 rect, 2 if sel else 1, border_radius=8)
                ti = get_font(14).render(label, True,
                                         COL_GOLD if sel else COL_TEXT)
                self.screen.blit(ti, ti.get_rect(center=rect.center))
                self._click_zones.append((rect, kind, data))
            y += rows * (th + gap) + 8
            # сводка: кому уйдёт приказ
            if self.orders_all:
                tgt = "ВСЯ КОМАНДА (%d)" % len(allies)
            elif self.orders_pick:
                names = [b.display_name or "СОЮЗНИК" for b in allies
                         if b in self.orders_pick]
                tgt = ", ".join(names[:3])
                if len(names) > 3:
                    tgt += " +ещё %d" % (len(names) - 3)
            else:
                tb = self._order_target()
                tgt = ((tb.display_name or "СОЮЗНИК")
                       + " (у прицела)") if tb else "—"
            img = get_font(15, bold=False).render("ЦЕЛЬ: %s" % tgt,
                                                  True, COL_TEXT)
            self.screen.blit(img, (panel.x + 26, y))
            y += 30
        # строки приказов: 1–8
        for i, key in enumerate(self.ORDER_LIST):
            name, desc, col = self.ORDER_INFO[key]
            cnt = sum(1 for b in allies
                      if b.order == key
                      or (key == "free" and b.order is None))
            row = pygame.Rect(panel.x + 18, y, panel.w - 36, 40)
            hov = row.collidepoint(self._mouse) and bool(allies)
            pygame.draw.rect(self.screen,
                             (34, 44, 84) if hov else (24, 30, 58),
                             row, border_radius=9)
            pygame.draw.rect(self.screen, col if hov else (52, 62, 104),
                             row, 2 if hov else 1, border_radius=9)
            # номер клавиши
            nr = pygame.Rect(row.x + 8, row.centery - 14, 28, 28)
            pygame.draw.rect(self.screen, (52, 62, 104), nr, border_radius=7)
            ni = get_font(16).render(str(i + 1), True, COL_TEXT)
            self.screen.blit(ni, ni.get_rect(center=nr.center))
            ti = get_font(19).render(name, True, col)
            self.screen.blit(ti, ti.get_rect(midleft=(row.x + 48,
                                                      row.centery - 8)))
            di = get_font(13, bold=False).render(desc, True, COL_DIM)
            self.screen.blit(di, di.get_rect(midleft=(row.x + 48,
                                                      row.centery + 11)))
            ci = get_font(15, bold=False).render(
                ("%d" % cnt) if allies else "—", True,
                col if cnt else (90, 100, 140))
            self.screen.blit(ci, ci.get_rect(midright=(row.right - 14,
                                                       row.centery)))
            if allies:
                self._click_zones.append((row, "ord_row", key))
            y += 46
        img = get_font(14, bold=False).render(
            "1–8 — приказ · плитки/Tab — кому · T — вся команда · E/Esc — закрыть",
            True, COL_DIM)
        self.screen.blit(img, img.get_rect(midbottom=(panel.centerx,
                                                      panel.bottom - 10)))

    def _ed_tools(self):
        """Палитра инструментов текущего типа карты (v3.4)."""
        return (self.ED_TOOLS_ASSAULT if self.ed_kind == "assault"
                else self.ED_TOOLS_BATTLE)

    def _ed_enter(self):
        """Войти в редактор: сетки сохраняются между визитами (у каждого
        типа карты своя), чтобы карту можно было дорабатывать."""
        if self.ed_grids[self.ed_kind] is None:
            self.ed_grids[self.ed_kind] = \
                [["."] * EDITOR_COLS for _ in range(EDITOR_ROWS)]
            self.ed_msg = "Стройте карту! S — сохранить, ESC — выход в меню"

    def _ed_board_rect(self):
        """Прямоугольник поля редактора на экране и размер клетки."""
        cw = self.ED_CELL
        x0 = (SCREEN_W - EDITOR_COLS * cw) // 2
        y0 = 116
        return pygame.Rect(x0, y0, EDITOR_COLS * cw, EDITOR_ROWS * cw), cw

    def _ed_click(self, pos, erase=False):
        """Клик по полю: поставить текущий инструмент (ПКМ — стереть).
        v3.4: точка захвата — только в ШТУРМЕ (в БОЕ её нет вовсе)."""
        if self.ed_grid is None:
            self._ed_enter()
        board, cw = self._ed_board_rect()
        if not board.collidepoint(pos):
            return
        c = int((pos[0] - board.x) // cw)
        r = int((pos[1] - board.y) // cw)
        ch = "." if erase else self.ed_tool
        if ch == "P":                    # точка захвата — только одна
            for row in self.ed_grid:
                for j, v in enumerate(row):
                    if v == "P":
                        row[j] = "."
        self.ed_grid[r][c] = ch
        self.sounds.play("ric")

    def _ed_valid(self):
        """Карта играбельна. ШТУРМ: точка + спавны обеих сторон.
        v3.4, БОЙ: спавны СОЮЗНИКОВ и ВРАГОВ (в FFA это просто точки
        появления, но обе стороны нужны — игрок и хоть один чужак)."""
        joined = "".join("".join(row) for row in (self.ed_grid or []))
        if self.ed_kind == "assault":
            return "P" in joined and "D" in joined and "A" in joined
        return "D" in joined and "A" in joined

    def _ed_save(self):
        """Сохранить карту: ШТУРМ — в maps/custom_N.txt (ротация ШТУРМА),
        БОЙ — в maps/custom_battle_N.txt (FFA и КОМАНДНЫЕ режимы)."""
        if self.ed_grid is None:
            return
        if not self._ed_valid():
            if self.ed_kind == "assault":
                self.ed_msg = ("НУЖНЫ ТОЧКА (5), СПАВН ОБОРОНЫ (6) И СПАВН АТАКИ (7)!")
            else:
                self.ed_msg = "НУЖНЫ СПАВН СОЮЗНИКОВ (5) И СПАВН ВРАГОВ (6)!"
            self.sounds.play("ric")
            return
        if self.ed_kind == "assault":
            name = "Карта игрока %d" % (len(load_custom_maps()) + 1)
            path = save_custom_map(name, self.ed_grid)
            self.ed_msg = "СОХРАНЕНО: %s — карта уже в ШТУРМЕ!" % path
        else:
            name = "Арена игрока %d" % (len(load_custom_battle_maps()) + 1)
            path = save_custom_battle_map(name, self.ed_grid)
            self.ed_msg = "СОХРАНЕНО: %s — играет в FFA и КОМАНДНЫХ!" % path
        self.sounds.play("win")

    def _draw_editor(self):
        """v3.3: экран редактора карт — вся карта перед глазами,
        инструменты внизу, сохранение на S.
        v3.4: вкладки ТИПА КАРТЫ — ШТУРМ и БОЙ (FFA и командные)."""
        self.screen.fill((10, 12, 26))
        img = get_font(30).render("РЕДАКТОР КАРТ", True, COL_TEXT)
        self.screen.blit(img, img.get_rect(midtop=(SCREEN_W / 2, 10)))
        # вкладки типа карты: ШТУРМ / БОЙ (клик или TAB)
        for i, (kind, lbl) in enumerate((
                ("assault", "ШТУРМ"),
                ("battle", "БОЙ — FFA и КОМАНДНЫЕ"))):
            cur = self.ed_kind == kind
            r = pygame.Rect(0, 0, 130 if i == 0 else 250, 26)
            r.midtop = (SCREEN_W / 2 - 200 + i * 400, 48)
            pygame.draw.rect(self.screen,
                             (46, 58, 104) if cur else (30, 40, 75), r,
                             border_radius=7)
            pygame.draw.rect(self.screen,
                             COL_GOLD if cur else (70, 80, 120),
                             r, 2 if cur else 1, border_radius=7)
            img = get_font(14).render(lbl, True, COL_TEXT if cur else COL_DIM)
            self.screen.blit(img, img.get_rect(center=r.center))
            self._click_zones.append((r, "ed_kind", kind))
        if self.ed_kind == "assault":
            img = get_font(15, bold=False).render(
                "оборона держит ТОЧКУ (в здании или где поставите), атака штурмует",
                True, COL_DIM)
            self.screen.blit(img, img.get_rect(midtop=(SCREEN_W / 2, 82)))
        else:
            img = get_font(15, bold=False).render(
                "карта для ВСЕХ обычных режимов: FFA, 2на2…10на10 — у союзников"
                " спавны D, у врагов A", True, COL_DIM)
            self.screen.blit(img, img.get_rect(midtop=(SCREEN_W / 2, 82)))
        if self.ed_grid is None:
            self._ed_enter()
        board, cw = self._ed_board_rect()
        tools = self._ed_tools()
        colors = {"#": (86, 96, 150), "S": (110, 200, 255),
                  "H": (255, 200, 80), "U": (255, 110, 200)}
        pygame.draw.rect(self.screen, (16, 20, 40), board)
        for r in range(EDITOR_ROWS):
            row = self.ed_grid[r]
            for c in range(EDITOR_COLS):
                ch = row[c]
                cell = pygame.Rect(board.x + c * cw, board.y + r * cw, cw, cw)
                if ch in colors:
                    pygame.draw.rect(self.screen, colors[ch],
                                     cell.inflate(-2, -2), border_radius=2)
                elif ch == "P":
                    pygame.draw.rect(self.screen, COL_GOLD,
                                     cell.inflate(-2, -2), 2, border_radius=2)
                    cxp, cyp = cell.center
                    pygame.draw.line(self.screen, COL_GOLD,
                                     (cxp - 5, cyp), (cxp + 5, cyp), 2)
                    pygame.draw.line(self.screen, COL_GOLD,
                                     (cxp, cyp - 5), (cxp, cyp + 5), 2)
                elif ch == "D":
                    pygame.draw.circle(self.screen, (120, 255, 150),
                                       cell.center, cw // 2 - 2, 2)
                elif ch == "A":
                    pygame.draw.circle(self.screen, (255, 90, 90),
                                       cell.center, cw // 2 - 2, 2)
        for i in range(EDITOR_COLS + 1):
            x = board.x + i * cw
            pygame.draw.line(self.screen, (26, 32, 58),
                             (x, board.y), (x, board.bottom))
        for j in range(EDITOR_ROWS + 1):
            yy = board.y + j * cw
            pygame.draw.line(self.screen, (26, 32, 58),
                             (board.x, yy), (board.right, yy))
        pygame.draw.rect(self.screen, (70, 80, 120), board, 1)
        self._click_zones.append((board.copy(), "ed_board", None))
        # подсветка клетки под курсором
        if board.collidepoint(self._mouse):
            c = int((self._mouse[0] - board.x) // cw)
            r = int((self._mouse[1] - board.y) // cw)
            pygame.draw.rect(self.screen, COL_P1,
                             pygame.Rect(board.x + c * cw, board.y + r * cw,
                                         cw, cw), 1)
        # палитра инструментов
        gap = 122
        x0 = int(SCREEN_W / 2 - (len(tools) * gap - (gap - 112)) / 2)
        for i, (ch, lbl) in enumerate(tools):
            r = pygame.Rect(0, 0, 112, 30)
            r.midtop = (x0 + i * gap, board.bottom + 14)
            cur = self.ed_tool == ch
            pygame.draw.rect(self.screen,
                             (46, 58, 104) if cur else (30, 40, 75), r,
                             border_radius=7)
            pygame.draw.rect(self.screen, COL_GOLD if cur else (70, 80, 120),
                             r, 2 if cur else 1, border_radius=7)
            img = get_font(14).render(lbl, True, COL_TEXT)
            self.screen.blit(img, img.get_rect(center=r.center))
            hotkey = str(i + 1) if i < len(tools) - 1 else "E"
            img2 = get_font(11, bold=False).render(hotkey, True, COL_DIM)
            self.screen.blit(img2, img2.get_rect(
                bottomright=(r.right - 4, r.bottom - 2)))
            self._click_zones.append((r, "ed_tool", ch))
        # статус/подсказки
        msg = self.ed_msg
        if not msg and not self._ed_valid():
            if self.ed_kind == "assault":
                msg = "ДЛЯ ИГРЫ НУЖНЫ: ТОЧКА (5), СПАВН ОБОРОНЫ (6), СПАВН АТАКИ (7)"
            else:
                msg = "ДЛЯ ИГРЫ НУЖНЫ: СПАВН СОЮЗНИКОВ (5) И СПАВН ВРАГОВ (6)"
        img = get_font(16, bold=False).render(
            msg, True, COL_GOLD if msg.startswith("СОХРАНЕНО") else COL_DIM)
        self.screen.blit(img, img.get_rect(midtop=(SCREEN_W / 2,
                                                   board.bottom + 50)))
        img = get_font(14, bold=False).render(
            "ЛКМ — ставить · ПКМ — стереть · 1-7/E — инструменты · "
            "TAB — тип карты (ШТУРМ/БОЙ) · C — очистить · S — сохранить · ESC — выход",
            True, (95, 105, 145))
        self.screen.blit(img, img.get_rect(midbottom=(SCREEN_W / 2,
                                                      SCREEN_H - 6)))

    # ================= тултипы ангарa =================
    def _tt_for(self, kind, key):
        """Содержимое тултипа для карточки сборки: название, цвет,
        и ЧИТАЕМЫЙ список того, что эта деталь делает."""
        if kind == "shell":
            return self._tt_shell(key)
        if kind == "ch":
            c = CHASSIS[key]
            lines = ["Скорость: %d px/с   ·   Разворот: %d°/с" % (c["speed"], c["turn"]),
                     "Броня: %d (сглаживает каждый удар)" % c["armor"]]
            if abs(c.get("wmult", 1.0) - 1.0) > 1e-9:
                lines.append("Чувствует вес корпуса: x%.2f" % c["wmult"])
            lines.append(c["desc"])
            return c["name"], COL_P1, lines
        if kind == "hu":
            h = HULL[key]
            lines = ["Прочность: %d HP" % h["hp"],
                     "Вес: %.2f — во столько замедляет танк" % h["weight"],
                     "Базовая перезарядка: %.2f с" % h["reload"],
                     h["desc"]]
            return h["name"], COL_P1, lines
        if kind == "wpn":
            w = WEAPONS[key]
            lines = ["Урон снаряда: x%.2f   ·   Скорость снаряда: x%.2f"
                     % (w["damage_mult"], w["speed_mult"]),
                     "Полная перезарядка: x%.2f" % w["reload_mult"]]
            if w["mag"] > 1:
                lines.append("Обойма: %d снаряда, пауза %.2f с"
                             % (w["mag"], w["mag_cd"]))
            if w.get("pellets", 1) > 1:
                lines.append("Дробин за выстрел: %d с разлётом ±%.0f°"
                             % (w["pellets"], w["pellet_spread"]))
            if w.get("pellet_spread") and w.get("pellets", 1) <= 1:
                lines.append("Разброс ствола: ±%.0f°" % w["pellet_spread"])
            if w.get("bigshot"):
                lines.append("Особо крупный снаряд")
            if abs(w["move_mult"] - 1.0) > 1e-9:
                lines.append("Танк едет: x%.2f (орудие тяжёлое)" % w["move_mult"])
            lines.append(w["desc"])
            return w["name"], COL_P1, lines
        if kind == "pk":
            p = PERKS[key]
            names = {"hp_mult": "Прочность", "speed_mult": "Скорость",
                     "reload_mult": "Перезарядка", "turn_mult": "Разворот"}
            lines = []
            for f, label in names.items():
                if abs(p[f] - 1.0) > 1e-9:
                    pct = round((p[f] - 1.0) * 100)
                    lines.append("%s: %+d%%" % (label, pct))
            if p.get("bounces"):
                lines.append("Рикошеты: +%d к каждому снаряду" % p["bounces"])
            lines.append(p["desc"])
            return p["name"], COL_P1, lines
        if kind == "el":
            e = ELEMENTS[key]
            lines = ["Урон снаряда: x%.2f   ·   Скорость снаряда: x%.2f"
                     % (e["damage_mult"], e["speed_mult"]),
                     e["desc"]]
            eff = {"fire": "ПОДЖОГ: 4 с по 6 урона/с — броня не спасает",
                   "water": "СМЫВАЕТ бонусы врага + буксование 1.2 с",
                   "earth": "ВЯЗКОСТЬ: враг еле ползёт 2.5 с",
                   "electric": "ТОК: мотор врага вполсилы 1.3 с",
                   "air": "ПОРЫВ: отшвыривает врага на 90 px",
                   "ice": "ЛЁД: вмораживает врага на %.1f с (повторно — не сразу: "
                          "после оттаивания %.1f с лёд не берёт)"
                          % (ICE_TIME, ICE_IMMUNE_T),
                   "poison": "ЯД: %.0f с по %.0f урона/с — броня не спасает"
                             % (POISON_TIME, POISON_DPS),
                   "vamp": "ЛЕЧИТ вам %d%% урона каждого попадания"
                           % round(VAMP_HEAL_RATIO * 100)}
            if key in eff:
                lines.append(eff[key])
            lines.append("Свои стихии на ВАС не действуют — сам себя не замедлишь.")
            return e["name"], (170, 190, 255), lines
        return key, COL_TEXT, []

    def _tt_fate(self, key, is_curse, taken):
        """Тултип карты жребия: проклятье (красная) или облегчение (зелёная)."""
        table = CURSES if is_curse else BLESSINGS
        item = table[key]
        if is_curse:
            head = "ПРОКЛЯТЬЕ — ослабляет ТОЛЬКО ВАС"
            lines = [head, item["desc"],
                     "Награда: +%d%% очков за забег"
                     % round(SCORE_CURSE_BONUS * 100)]
        else:
            head = "ОБЛЕГЧЕНИЕ — помогает вам"
            lines = [head, item["desc"],
                     "Цена: -%d%% очков за забег"
                     % round(SCORE_BLESS_PENALTY * 100)]
        lines.append("Клик или V — %s" % ("СНЯТЬ (взято)" if taken else "ВЗЯТЬ"))
        if not is_curse:
            lines.append("Без проклятий — одно облегчение,"
                         " каждое проклятье открывает ещё")
        return item["name"], (255, 90, 110) if is_curse else (90, 230, 140), lines

    def _tt_enemy(self, key, taken):
        """Тултип эффекта НА ВРАГА: бафф добавляет очки, дебафф режет."""
        item = ENEMY_EFFECTS[key]
        buff = "score_bonus" in item
        if buff:
            head = "БАФФ — УСИЛИТЬ врага (усиленный враг платит)"
            lines = [head, item["desc"],
                     "Награда: +%d%% очков за забег"
                     % round(item["score_bonus"] * 100)]
        else:
            head = "ДЕБАФФ — ОСЛАБИТЬ врага"
            lines = [head, item["desc"],
                     "Цена: -%d%% очков за забег" % round(item["score_cut"] * 100)]
        lines.append("Клик или M — %s" % ("СНЯТЬ (взято)" if taken else "ВЗЯТЬ"))
        return item["name"], (120, 230, 150) if buff else (255, 170, 80), lines

    def _draw_tooltip(self):
        """Окошко-подсказка у курсора: крупный шрифт, рисуется поверх всего."""
        if not self._tooltip:
            return
        title, color, lines = self._tooltip
        ft = get_font(18)
        fb = get_font(15, bold=False)
        pad, maxw = 12, 400
        wrapped = []
        for ln in lines:
            wrapped.extend(_wrap_px(ln, fb, maxw - 2 * pad))
        w = max(ft.size(title)[0],
                max((fb.size(l)[0] for l in wrapped), default=0)) + 2 * pad
        h = 36 + len(wrapped) * 21 + pad
        x = min(max(self._mouse[0] + 20, 6), SCREEN_W - w - 6)
        y = min(max(self._mouse[1] + 20, 6), SCREEN_H - h - 6)
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((10, 14, 30, 242))
        self.screen.blit(bg, (x, y))
        pygame.draw.rect(self.screen, color, (x, y, w, h), 2, border_radius=9)
        img = ft.render(title, True, color)
        self.screen.blit(img, (x + pad, y + 7))
        yy = y + 36
        for l in wrapped:
            img = fb.render(l, True, COL_TEXT)
            self.screen.blit(img, (x + pad, yy))
            yy += 21

    def _draw_select(self):
        self.screen.fill((10, 12, 26))   # непрозрачный фон: старый бой не просвечивает
        self._tooltip = None             # тултип собирается заново каждый кадр
        t1 = get_font(30).render("АНГАР", True, COL_TEXT)
        self.screen.blit(t1, t1.get_rect(center=(SCREEN_W / 2 - 120, 30)))
        # режим боя в шапке ангара — видно, на сколько танков идём (v2.1)
        img = get_font(20).render("бой: %s  ·  до %d побед"
                                  % (MODE_NAMES[self.mode], ROUNDS_TO_WIN),
                                  True, COL_GOLD)
        self.screen.blit(img, img.get_rect(midleft=(SCREEN_W / 2 + 60, 30)))

        ch = CHASSIS[CH_KEYS[self.sel_ch]]
        wp = WEAPONS[WP_KEYS[self.sel_wpn]]
        el = ELEMENTS[EL_KEYS[self.sel_el]]

        # --- пять компактных панелей сборки (шаг 60 — ужаты под СНАРЯД) ---
        self._choice_panel("ШАССИ — клик или A / D", CH_KEYS, self.sel_ch,
                           CHASSIS, 90, "ch")
        self._choice_panel("КОРПУС — клик или W / S", HU_KEYS, self.sel_hu,
                           HULL, 150, "hu")
        self._choice_panel("ДУЛО — клик или Q / E", WP_KEYS, self.sel_wpn,
                           WEAPONS, 210, "wpn")
        self._choice_panel("ПЕРК — клик или Z / C", PK_KEYS, self.sel_pk,
                           PERKS, 270, "pk")
        self._choice_panel("СТИХИЯ — клик или F / G", EL_KEYS, self.sel_el,
                           ELEMENTS, 330, "el")

        # --- v3.0: ТИП СНАРЯДА — чем стреляем (компактная полоса) ---
        self._shell_panel(396)

        # --- БИЛДЫ (v2.9): стартовые наборы, максимум ОДИН на танк ---
        self._build_panel(446)

        # --- жребий: проклятья (+очки) и облегчения (-очки) ---
        mult = self._fate_mult(self.sel_curses, self.sel_blessings,
                               self.sel_enemy_keys)
        self._fate_panel(508, 542, mult)

        # --- эффекты НА ВРАГА ---
        self._enemy_panel(608)

        # итоговые характеристики — с учётом жребия
        preview = Tank(0, 0, 0, CH_KEYS[self.sel_ch], HU_KEYS[self.sel_hu], COL_P1,
                       WP_KEYS[self.sel_wpn], PK_KEYS[self.sel_pk],
                       EL_KEYS[self.sel_el],
                       tuple(self.sel_curses), tuple(self.sel_blessings))
        stats_line = ("Скорость: %.0f px/с    Прочность: %d    Броня: %d    "
                      "Урон: %d    Выстрел: %.2f с"
                      % (preview.speed, preview.max_hp, ch["armor"],
                         round(BULLET_DAMAGE * wp["damage_mult"]
                               * el["damage_mult"] * preview.mods["damage_mult"])
                         * {"he": 0.80, "ap": 1.30, "fire": 0.85,
                            "star": SHELL_STAR_DAMAGE_MULT}
                         .get(SHELL_KEYS[self.sel_shell], 1.0),
                         preview.reload_time))
        if preview.mods["spread_deg"] > 0:
            stats_line += "    Разброс: %d°" % round(preview.mods["spread_deg"])
        img = get_font(18).render(stats_line, True,
                                  (255, 150, 90) if preview.speed < 110 else COL_TEXT)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 648)))
        img = get_font(21).render("Очки за забег: x%.2f      "
                                  "Enter — в бой, Esc — меню (или кнопки ниже)"
                                  % mult, True, COL_P1)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 666)))
        self._button(SCREEN_W / 2 - 95, 696, "В БОЙ ▶", "go_fight",
                     w=270, h=30, fs=18)
        self._button(SCREEN_W / 2 + 150, 696, "МЕНЮ", "garage_menu",
                     w=130, h=30, fs=17)

        # превью танка игрока (внизу справа, чтобы не мешать панелям)
        img = pygame.transform.scale_by(preview._sprite, 1.6)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W - 100, 668)))

        # тултип рисуется САМЫМ ПОСЛЕДНИМ — поверх всех панелей и кнопок
        self._draw_tooltip()

    def _shell_panel(self, y):
        """v3.0: ТИП СНАРЯДА — полоса из 4 кнопок в стиле билдов:
        чем стреляет главное орудие каждый выстрел. Описание — в
        подсказке при наведении, прокрутка — клавишей X."""
        t = get_font(14).render(
            "СНАРЯД — тип боеприпаса каждого выстрела (клик или X):",
            True, COL_GOLD)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W / 2, y - 24)))
        f = get_font(13)
        gap = 14
        btns = []
        for i, key in enumerate(SHELL_KEYS):
            sc = SHELL_TYPES[key]
            sel = self.sel_shell == i
            btns.append((f.render(sc["name"], True,
                                  COL_TEXT if sel else COL_DIM), i, sc))
        total = sum(im.get_width() + 22 for im, _, _ in btns) \
            + gap * (len(btns) - 1)
        bx = SCREEN_W / 2 - total / 2
        hov_key = None
        for im, i, sc in btns:
            r = pygame.Rect(bx, y - 13, im.get_width() + 22, 26)
            sel = (i == self.sel_shell)
            hov = r.collidepoint(self._mouse)
            if hov:
                hov_key = i
            if sel:
                pygame.draw.rect(self.screen, (40, 52, 96), r, border_radius=8)
            elif hov:
                pygame.draw.rect(self.screen, (30, 40, 75), r, border_radius=8)
            else:
                bg = pygame.Rect(r.x, r.y - 2, r.w, r.h + 4)
                pygame.draw.rect(self.screen, (24, 30, 56), bg, border_radius=8)
            edge = sc["color"] if (sel or hov) else (70, 80, 120)
            pygame.draw.rect(self.screen, edge, r,
                             3 if sel else (2 if hov else 1), border_radius=8)
            self.screen.blit(im, im.get_rect(center=r.center))
            self._click_zones.append((r, "shell", i))
            bx += r.w + gap
        if hov_key is not None:
            self._tooltip = self._tt_shell(SHELL_KEYS[hov_key])

    def _build_panel(self, y):
        """v2.9: БИЛДЫ — стартовые наборы в один ряд (10 кнопок: «НЕТ»
        плюс девять билдов — с v3.1 добавился «КРУГОВОЙ АД»).
        МАКСИМУМ ОДИН БИЛД НА ТАНК: клик по другому билду заменяет выбор,
        повторный клик по выбранному снимает. Клавиши 1…9 — билды,
        0 — без билда. Билд выдаёт предметы и баффы в начале КАЖДОГО
        раунда; с v3.0 билды получают и боты (случайный каждому)."""
        t = get_font(16).render(
            "БИЛД — стартовый набор на каждый раунд (клик; 1…9 — билд, 0 — без):",
            True, COL_GOLD)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W / 2, y - 26)))
        f = get_font(13)
        gap = 10
        btns = [(f.render("НЕТ", True,
                          COL_TEXT if self.sel_build is None else COL_DIM), None)]
        for i, key in enumerate(BUILD_KEYS):
            sel = self.sel_build == i
            btns.append((f.render(BUILDS[key]["name"], True,
                                  COL_TEXT if sel else COL_DIM), i))
        total = sum(im.get_width() + 18 for im, _ in btns) + gap * (len(btns) - 1)
        bx = SCREEN_W / 2 - total / 2.0
        hov_any, hov_bd = False, None
        for im, i in btns:
            r = pygame.Rect(bx, y - 13, im.get_width() + 18, 26)
            sel = (i == self.sel_build)
            hov = r.collidepoint(self._mouse)
            if hov:
                hov_any, hov_bd = True, i
            if sel:
                pygame.draw.rect(self.screen, (40, 52, 96), r, border_radius=8)
            elif hov:
                pygame.draw.rect(self.screen, (30, 40, 75), r, border_radius=8)
            else:
                bg = pygame.Rect(r.x, r.y - 2, r.w, r.h + 4)
                pygame.draw.rect(self.screen, (24, 30, 56), bg, border_radius=8)
            edge = BUILDS[BUILD_KEYS[i]]["color"] if (i is not None and
                                                      (sel or hov)) else (70, 80, 120)
            pygame.draw.rect(self.screen, edge, r,
                             3 if sel else (2 if hov else 1), border_radius=8)
            self.screen.blit(im, im.get_rect(center=r.center))
            self._click_zones.append((r, "build", i))
            bx += r.w + gap
        if hov_any:
            if hov_bd is None:
                self._tooltip = ("БЕЗ БИЛДА", COL_TEXT,
                                 ["чистый танк без стартовых предметов",
                                  "клик — снять выбранный билд"])
            else:
                bd = BUILDS[BUILD_KEYS[hov_bd]]
                self._tooltip = ("БИЛД «%s»" % bd["name"], bd["color"],
                                 [bd["desc"],
                                  "выдаётся В НАЧАЛЕ каждого раунда",
                                  "максимум ОДИН билд на танк",
                                  "v3.0: боты тоже получают случайные билды"])

    def _tt_shell(self, key):
        """v3.0: тултип карточки типа снаряда."""
        sc = SHELL_TYPES[key]
        lines = [sc["desc"]]
        if key == "ap":
            lines.append("урон x%.2f, скорость снаряда x%.2f,"
                         " перезарядка x%.2f" % (1.30, 1.30, SHELL_AP_RELOAD_MULT))
        elif key == "he":
            lines.append("осколки: %d урона всем чужакам в %d px"
                         % (HE_SPLASH_DAMAGE, HE_SPLASH_RADIUS))
        elif key == "fire":
            lines.append("лужа: %g с по %g урона/с, броня не спасает"
                         % (FIRE_ZONE_LIFE, FIRE_ZONE_DPS))
        elif key == "star":
            lines.append("звезда: %d осколка по %d урона, живут %g с"
                         " (примерно %d px), разрыв при любом попадании"
                         % (STAR_SHARDS, STAR_SHARD_DAMAGE, STAR_SHARD_LIFE,
                            int(540 * STAR_SHARD_SPEED_MULT * STAR_SHARD_LIFE)))
        lines.append("тип заряжает каждый выстрел главного орудия")
        return sc["name"], sc["color"], lines

    def _fate_panel(self, y_cur, y_bless, mult):
        """Жребий: 8 проклятий (красные) и 8 облегчений (зелёные).
        R/T — курсор, V — взять/снять. Без проклятий — максимум одно
        облегчение. Проклятья ослабляют ТОЛЬКО ВАС, но ДЕЛАЮТ ОЧКИ."""
        t = get_font(17).render(
            "ЖРЕБИЙ — клик по карточке: взять/снять   (R / T курсор, V — взять)"
            "   проклятья +%d%% очков" % round(SCORE_CURSE_BONUS * 100),
            True, COL_GOLD)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W / 2, y_cur - 38)))
        n_cur = len(CR_KEYS)
        step = min(150, (SCREEN_W - 140) // n_cur)
        box_w, box_h = step - 18, 36
        name_f = get_font(12)

        def _wrap(name):
            if name_f.size(name)[0] <= box_w - 6 or " " not in name:
                return [name]
            words = name.split(" ")
            best = None
            for j in range(1, len(words)):
                a, b = " ".join(words[:j]), " ".join(words[j:])
                w = max(name_f.size(a)[0], name_f.size(b)[0])
                if best is None or w < best[0]:
                    best = (w, a, b)
            return [best[1], best[2]]

        def _row(y, table, keys, taken_keys, is_curse):
            for i, key in enumerate(keys):
                item = table[key]
                taken = key in taken_keys
                cur = (i if is_curse else n_cur + i) == self.sel_jt
                edge = (255, 90, 110) if is_curse else (90, 230, 140)
                x = SCREEN_W / 2 + (i - (len(keys) - 1) / 2) * step
                box = pygame.Rect(0, 0, box_w, box_h)
                box.center = (int(x), y)
                bg = pygame.Rect(box.x - 3, box.y - 3, box.w + 6, box.h + 6)
                pygame.draw.rect(self.screen,
                                 (58, 28, 42) if is_curse else (22, 46, 34),
                                 bg, border_radius=7)
                if taken:   # взято — светлая заливка
                    pygame.draw.rect(self.screen,
                                     (96, 40, 58) if is_curse else (30, 66, 48),
                                     box, border_radius=7)
                hov = box.collidepoint(self._mouse)
                pygame.draw.rect(self.screen,
                                 edge if (taken or hov) else (60, 70, 110),
                                 box, 3 if taken else (2 if hov else 1),
                                 border_radius=7)
                if cur:   # курсор — белая рамка снаружи
                    pygame.draw.rect(self.screen, COL_TEXT,
                                     box.inflate(6, 6), 2, border_radius=9)
                color = COL_TEXT if (taken or cur or hov) else COL_DIM
                self._click_zones.append((box, "fate",
                                          i if is_curse else n_cur + i))
                if hov:   # окошко-подсказка над картой жребия
                    self._tooltip = self._tt_fate(key, is_curse, taken)
                lines = _wrap(item["name"])
                dy = box.centery - (len(lines) * 14) // 2 + 7
                for ln in lines:
                    img = name_f.render(ln, True, color)
                    self.screen.blit(img, img.get_rect(center=(box.centerx, dy)))
                    dy += 14

        _row(y_cur, CURSES, CR_KEYS, self.sel_curses, True)
        _row(y_bless, BLESSINGS, BL_KEYS, self.sel_blessings, False)

        # подпись под жребием: что под курсором и правила
        if self.sel_jt < n_cur:
            item, is_curse = CURSES[CR_KEYS[self.sel_jt]], True
            taken = CR_KEYS[self.sel_jt] in self.sel_curses
        else:
            j = self.sel_jt - n_cur
            item, is_curse = BLESSINGS[BL_KEYS[j]], False
            taken = BL_KEYS[j] in self.sel_blessings
        edge = (255, 90, 110) if is_curse else (90, 230, 140)
        img = get_font(13).render("%s — %s   [%s]"
                                  % (item["name"], item["desc"],
                                     "ВЗЯТО" if taken else "свободно"),
                                  True, edge)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y_bless + 26)))
        # v3.0: строка-boilerplate с правилами убрана — правила переехали
        # в заголовок и в подсказки карт (_tt_fate), место — типу снаряда

    def _enemy_panel(self, y):
        """Эффекты НА ВРАГА: дебаффы режут счёт, баффы наоборот ДОБАВЛЯЮТ —
        усиленный враг платит. v3.0: ужата (32px карточки, одна подпись,
        лимитов-строка убрана — «лимитов нет» переехало в заголовок)."""
        buffs = [EE["score_bonus"] for EE in ENEMY_EFFECTS.values()
                 if "score_bonus" in EE]
        t = get_font(15).render(
            "НА ВРАГА — клик: взять/снять   (B / N курсор, M — взять)"
            "   ·   лимитов нет: баффы +%d%%..+%d%% очков, дебаффы режут"
            % (round(min(buffs) * 100), round(max(buffs) * 100)),
            True, (255, 170, 80))
        self.screen.blit(t, t.get_rect(center=(SCREEN_W / 2, y - 22)))
        step = min(180, (SCREEN_W - 140) // len(EE_KEYS))
        box_w, box_h = step - 16, 32
        name_f = get_font(12)

        def _wrap(name):
            if name_f.size(name)[0] <= box_w - 6 or " " not in name:
                return [name]
            words = name.split(" ")
            best = None
            for j in range(1, len(words)):
                a, b = " ".join(words[:j]), " ".join(words[j:])
                w = max(name_f.size(a)[0], name_f.size(b)[0])
                if best is None or w < best[0]:
                    best = (w, a, b)
            return [best[1], best[2]]

        for i, key in enumerate(EE_KEYS):
            item = ENEMY_EFFECTS[key]
            taken = key in self.sel_enemy_keys
            buff = "score_bonus" in item   # баффы — зелёные, дебаффы — рыжие
            edge = (120, 230, 150) if buff else (255, 170, 80)
            x = SCREEN_W / 2 + (i - (len(EE_KEYS) - 1) / 2) * step
            box = pygame.Rect(0, 0, box_w, box_h)
            box.center = (int(x), y)
            bg = pygame.Rect(box.x - 3, box.y - 3, box.w + 6, box.h + 6)
            pygame.draw.rect(self.screen,
                             (22, 46, 34) if buff else (62, 44, 26),
                             bg, border_radius=7)
            if taken:
                pygame.draw.rect(self.screen,
                                 (30, 66, 48) if buff else (92, 62, 34),
                                 box, border_radius=7)
            hov = box.collidepoint(self._mouse)
            pygame.draw.rect(self.screen,
                             edge if (taken or hov) else (60, 70, 110),
                             box, 3 if taken else (2 if hov else 1),
                             border_radius=7)
            if i == self.sel_en:
                pygame.draw.rect(self.screen, COL_TEXT,
                                 box.inflate(6, 6), 2, border_radius=9)
            color = COL_TEXT if (taken or i == self.sel_en or hov) else COL_DIM
            self._click_zones.append((box, "enemy", i))
            if hov:   # окошко-подсказка над эффектом на врага
                self._tooltip = self._tt_enemy(key, taken)
            lines = _wrap(item["name"])
            dy = box.centery - (len(lines) * 14) // 2 + 7
            for ln in lines:
                img = name_f.render(ln, True, color)
                self.screen.blit(img, img.get_rect(center=(box.centerx, dy)))
                dy += 14

        item = ENEMY_EFFECTS[EE_KEYS[self.sel_en]]
        taken = EE_KEYS[self.sel_en] in self.sel_enemy_keys
        if "score_bonus" in item:
            price = "[счёт +%d%%]" % round(item["score_bonus"] * 100)
        else:
            price = "[счёт -%d%%]" % round(item["score_cut"] * 100)
        img = get_font(14).render("%s — %s   %s   [%s]"
                                  % (item["name"], item["desc"], price,
                                     "ВЗЯТО" if taken else "свободно"),
                                  True, (255, 190, 110))
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y + 20)))
        # v3.0: нижняя строка-правило убрана — «лимитов нет» теперь в заголовке

    def _choice_panel(self, title, keys, idx, table, y, kind=None):
        """Компактная панель выбора: заголовок сверху, карточки в ряд.
        kind — метка для мыши: клик по карточке выбирает её."""
        t = get_font(16).render(title, True, COL_GOLD)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W / 2, y - 34)))
        n = len(keys)
        step = min(240, (SCREEN_W - 140) // n)
        box_w, box_h = step - 20, 44
        name_f = get_font(14)
        desc_f = get_font(11, bold=False)

        def _wrap(desc):
            """Длинная подпись в узкой коробке — переносим на 2 строки."""
            if desc_f.size(desc)[0] <= box_w - 6 or " " not in desc:
                return [desc]
            words = desc.split(" ")
            best = None
            for j in range(1, len(words)):
                a, b = " ".join(words[:j]), " ".join(words[j:])
                w = max(desc_f.size(a)[0], desc_f.size(b)[0])
                if best is None or w < best[0]:
                    best = (w, a, b)
            return [best[1], best[2]]

        for i, key in enumerate(keys):
            item = table[key]
            x = SCREEN_W / 2 + (i - (n - 1) / 2) * step
            sel = (i == idx)
            box = pygame.Rect(0, 0, box_w, box_h)
            box.center = (int(x), y)
            bg = pygame.Rect(box.x - 4, box.y - 4, box.w + 8, box.h + 8)
            pygame.draw.rect(self.screen, (30, 40, 75), bg, border_radius=8)
            hov = box.collidepoint(self._mouse)
            pygame.draw.rect(self.screen,
                             COL_P1 if sel else ((160, 175, 220) if hov
                                                  else (60, 70, 110)),
                             box, 3 if sel else (2 if hov else 1),
                             border_radius=7)
            if kind and hov:   # окошко-подсказка над карточкой сборки
                self._tooltip = self._tt_for(kind, key)
            dlines = _wrap(item["desc"])
            name_y = box.y + (11 if len(dlines) > 1 else 14)
            img = name_f.render(item["name"],
                                True, COL_TEXT if (sel or hov) else COL_DIM)
            if kind:
                self._click_zones.append((box, kind, i))
            self.screen.blit(img, img.get_rect(center=(box.centerx, name_y)))
            dy = box.y + (24 if len(dlines) > 1 else 29)
            for dl in dlines:
                img2 = desc_f.render(dl, True, COL_DIM)
                self.screen.blit(img2, img2.get_rect(center=(box.centerx, dy)))
                dy += 12

    def _draw_table(self):
        """ТАБЛИЦА СЧЕТА: топ-10 забегов (хранится в duel_stats.json)."""
        self.screen.fill((10, 12, 26))
        t1 = get_font(38).render("ТАБЛИЦА СЧЕТА", True, COL_GOLD)
        self.screen.blit(t1, t1.get_rect(center=(SCREEN_W / 2, 52)))
        sub = get_font(15, bold=False).render(
            "топ-10 забегов · проклятья +%d%% очков, облегчения и эффекты на врага режут счёт"
            % round(SCORE_CURSE_BONUS * 100), True, COL_DIM)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W / 2, 88)))
        rows = self.stats.get("score_table", [])
        if not rows:
            img = get_font(22, bold=False).render(
                "Пока пусто — сыграйте матч, и забег попадёт в таблицу!",
                True, COL_TEXT)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 300)))
        else:
            medal = ((255, 208, 0), (192, 198, 215), (205, 127, 50))
            row_f = get_font(17)
            dim_f = get_font(15, bold=False)
            y = 126
            for i, r in enumerate(rows):
                col = medal[i] if i < 3 else COL_DIM
                img = row_f.render("#%d" % (i + 1), True, col)
                self.screen.blit(img, (150 - img.get_width(), y))
                img = get_font(20 if i == 0 else 18).render(
                    str(r.get("score", 0)), True, col if i < 3 else COL_TEXT)
                self.screen.blit(img, img.get_rect(midleft=(190, y + 9)))
                res = r.get("res", "draw")
                rtxt, rcol = (("ПОБЕДА", COL_P1) if res == "win" else
                              ("ПОРАЖЕНИЕ", COL_P2) if res == "loss" else
                              ("НИЧЬЯ", COL_DIM))
                img = dim_f.render("%s %s" % (rtxt, r.get("rounds", "")),
                                   True, rcol)
                self.screen.blit(img, img.get_rect(midleft=(300, y + 9)))
                img = dim_f.render(
                    "прокл.%d облег.%d враг%d" % (r.get("c", 0), r.get("b", 0),
                                                  r.get("e", 0)), True, COL_DIM)
                self.screen.blit(img, img.get_rect(midleft=(490, y + 9)))
                img = dim_f.render("x%.2f" % r.get("mult", 1.0), True, COL_GOLD)
                self.screen.blit(img, img.get_rect(midleft=(700, y + 9)))
                img = dim_f.render(str(r.get("el", "-")), True, (170, 190, 255))
                self.screen.blit(img, img.get_rect(midleft=(795, y + 9)))
                img = dim_f.render(str(r.get("date", "")), True, (95, 105, 145))
                self.screen.blit(img, img.get_rect(midright=(1130, y + 9)))
                if (self._table_from == "match_end"
                        and i + 1 == self.table_place):
                    img = dim_f.render("← ваш забег", True, COL_GOLD)
                    self.screen.blit(img, img.get_rect(midleft=(1145, y + 9)))
                y += 36
        self._button(SCREEN_W / 2, 634, "НАЗАД", "table_back", w=250, h=42)
        img = get_font(17, bold=False).render("Esc / Enter — назад", True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 672)))

    def _draw_match_end(self):
        win = self.score[0] >= ROUNDS_TO_WIN
        color = COL_P1 if win else COL_P2
        rec = "  НОВЫЙ РЕКОРД!" if self.new_record else ""
        if win:
            head = "ПОБЕДА!"
        elif self.team_mode:
            head = ("БОСС ЗАБРАЛ МАТЧ" if self.mode == 7
                    else "КОМАНДА БОТОВ ЗАБРАЛА МАТЧ")
        elif self.bots:
            bi = max(range(len(self.bots)), key=lambda i: self.score[i + 1]
                     if i + 1 < len(self.score) else 0)
            head = "%s ЗАБРАЛ МАТЧ" % (self.bots[bi].display_name
                                       or BOT_NAMES[bi])
        else:
            head = "ПОРАЖЕНИЕ"
        self._banner(head, color,
                     "Счёт %s      Enter — реванш   A — ангар   "
                     "T — таблица   M — меню" % self._score_str(),
                     sub2=("ОЧКИ: %d  (множитель x%.2f)   МЕСТО В ТАБЛИЦЕ: #%d%s"
                           % (self.final_score, self.score_mult,
                              self.table_place, rec))
                     if self.table_place else
                     "ОЧКИ: %d  (множитель x%.2f)   в топ-10 не попал%s"
                     % (self.final_score, self.score_mult, rec))

    # ----- HUD во время боя -----
    def _hp_bar(self, x, y, tank, right=False, h=14):
        w = 260                  # ширина одна и та же, меняется только высота
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, (30, 36, 60), rect, border_radius=4)
        # v2.9 ФИКС «маленькой полосочки здоровья»: у убитого танка
        # заливки НЕТ вообще — раньше остаток рисовался как 2-пиксельная
        # красная нитка (max(2, ...)) и висела над местом смерти врага
        k = max(0.0, tank.hp / tank.max_hp) if tank.alive else 0.0
        fill_w = int(w * k)
        if fill_w > 0:
            fill = rect.copy()
            fill.w = fill_w
            if right:
                fill.x = x + w - fill.w
            color = tank.color if k > 0.3 else (255, 90, 90)
            pygame.draw.rect(self.screen, color, fill, border_radius=4)
        pygame.draw.rect(self.screen, (70, 80, 120), rect, 1, border_radius=4)

    def _build_label(self, t, who=None, color=None, cap=22, suffix=""):
        """«ИГРОК — шасси + корпус + дуло + перк + стихия» с автоподбором
        размера шрифта: длинная сборка не должна налезать на центральный счёт.
        Имя можно не передавать — возьмём display_name (СОЮЗНИК, БОСС).
        color (v2.6) перекрашивает строку (командная подсветка HUD).
        cap (v2.8) — потолок шрифта: в плотных строках армий он мельче.
        suffix (v3.1) — хвост строки: в армиях так виден БИЛД бота."""
        who = who or t.display_name or "БОТ"
        label = "%s — %s + %s + %s + %s + %s%s" % (
            who, t.chassis["name"], t.hull["name"], t.weapon["name"],
            t.perk["name"], t.elem["name"], suffix)
        size = cap
        while size > 13 and get_font(size).size(label)[0] > 500:
            size -= 1
        return get_font(size).render(label, True, color or t.color)

    def _status_tags(self, t):
        """Статусы танка строкой (общие для HUD игрока и строк ботов)."""
        sfx = []
        # v3.4: приказ командира и звезда командира стороны
        if t.order == "hold":
            sfx.append("ПРИКАЗ: ДЕРЖИТ ПОЗИЦИЮ")
        elif t.order == "follow":
            sfx.append("ПРИКАЗ: ЗА ТОБОЙ")
        elif t.order == "attack":              # v3.5
            sfx.append("ПРИКАЗ: В АТАКЕ")
        elif t.order == "point":               # v3.5
            sfx.append("ПРИКАЗ: К ТОЧКЕ")
        elif t.order == "cover":               # v3.6
            sfx.append("ПРИКАЗ: ПРИКРЫВАЕТ")
        elif t.order == "retreat":             # v3.6
            sfx.append("ПРИКАЗ: ОТСТУПАЕТ")
        elif t.order == "target":              # v3.6
            sfx.append("ПРИКАЗ: НА ЦЕЛИ")
        if getattr(t, "is_commander", False):
            sfx.append("★ КОМАНДИР")
        if t.build_name:                       # v3.0: имя стартового билда
            sfx.append("БИЛД: %s" % t.build_name)
        if t.shell_type != "std":              # v3.0: тип снаряда
            sfx.append("СНАРЯД: %s" % SHELL_TYPES[t.shell_type]["name"])
        if t.mag_size > 1:
            sfx.append("ОБОЙМА %d/%d" % (t.mag_ammo, t.mag_size))
        if t.armor:
            sfx.append("броня %d" % t.armor)
        if t.element_key != "none":
            sfx.append("стихия: %s" % t.elem["name"])
        if t.mine_carried > 0:
            sfx.append("МИНА x%d (F)" % t.mine_carried)
        # v3.2: стены по ярусам — все ставятся по Q (сначала обычные)
        if t.wall_charges.get("std", 0) > 0:
            sfx.append("СТЕНА x%d (Q)" % t.wall_charges["std"])
        if t.wall_charges.get("strong", 0) > 0:
            sfx.append("ПРОЧН.СТЕНА x%d" % t.wall_charges["strong"])
        if t.wall_charges.get("heavy", 0) > 0:
            sfx.append("ОЧ.ПРОЧН.СТЕНА x%d" % t.wall_charges["heavy"])
        if t.wall_charges.get("ultra", 0) > 0:
            sfx.append("НЕВЕРОЯТН.СТЕНА x%d" % t.wall_charges["ultra"])
        if t.turret_charges > 0:
            sfx.append("ТУРЕЛЬ x%d (R)" % t.turret_charges)
        if t.emp_charges > 0:
            sfx.append("ЭМИ-ЗАРЯД x%d (X)" % t.emp_charges)
        if t.he_shots > 0:
            sfx.append("РАЗРЫВНЫЕ x%d" % t.he_shots)
        if t.nova_charges > 0:                 # v3.1: «Круговой ад»
            # v3.5: в залпе летит ВЫБРАННЫЙ тип снаряда — показываем какой
            sfx.append("КРУГОВОЙ АД x%d (V)%s" % (
                t.nova_charges,
                "" if t.shell_type == "std"
                else " · " + SHELL_TYPES[t.shell_type]["name"]))
        if t.shield_t > 0:
            sfx.append("ЩИТ %.0f" % t.shield_t)
        # ЛАЗЕРНЫЙ ВЕЕР: лазер + веер вместе — лучи веером
        if t.laser_charges > 0 and t.triple > 0:
            sfx.append("ЛАЗЕРНЫЙ ВЕЕР %d/%d" % (t.laser_charges, t.triple))
        elif t.triple > 0:
            sfx.append("ВЕЕР x%d" % t.triple)
        if t.boost_t > 0:
            sfx.append("ТУРБО %.0f" % t.boost_t)
        if t.rapid_t > 0:
            sfx.append("СКОРОСТРЕЛ %.0f" % t.rapid_t)
        if t.laser_charges > 0 and t.triple <= 0:
            sfx.append("ЛАЗЕР x%d" % t.laser_charges)
        if t.frozen_t > 0:
            sfx.append("ЗАМОРОЗКА!")
        elif t.ice_immune_t > 0:
            sfx.append("ОТТАИЛ")      # v2.3: лёд сейчас не берёт
        if t.burn_t > 0:
            sfx.append("ПОЖАР!")
        if t.poison_t > 0:
            sfx.append("ЯД!")
        if t.mud_t > 0:
            sfx.append("УВЯЗ!")
        if t.shock_t > 0:
            sfx.append("ТОК!")
        if t.curses_keys:
            sfx.append("ПРОКЛЯТЬЯ %d" % len(t.curses_keys))
        if t.blessings_keys:
            sfx.append("ОБЛЕГЧЕНИЯ %d" % len(t.blessings_keys))
        return sfx

    def _draw_hud(self):
        p = self.player
        # --- игрок (слева, всегда наверху слева) ---
        self.screen.blit(self._build_label(p, "ИГРОК"), (70, 62))
        self._hp_bar(70, 92, p)
        self._mini_info(p, 70, 116,
                        extra=("НА ВРАГА %d" % len(self.build[7]))
                        if self.build[7] else "")
        map_line = "до %d побед  ·  карта «%s»  ·  %s" % (
            ROUNDS_TO_WIN, self.arena.name, MODE_NAMES[self.mode])
        pts = int(self.points * self.score_mult)
        pts_label = "ОЧКИ %d" % pts
        if abs(self.score_mult - 1.0) > 1e-9:
            pts_label += "  ·  жребий x%.2f" % self.score_mult
        if self.mode == 2:
            # --- классика: один бот справа, счёт по центру сверху ---
            b = self.bots[0]
            img = self._build_label(b, "БОТ")
            self.screen.blit(img, img.get_rect(topright=(SCREEN_W - 70, 62)))
            self._hp_bar(SCREEN_W - 330, 92, b, right=True)
            self._mini_info(b, SCREEN_W - 70, 116, right=True,
                            extra=("ЭФФЕКТЫ ИГРОКА %d" % len(self.build[7]))
                            if self.build[7] else "")
            img = get_font(44).render("%d : %d" % tuple(self.score),
                                      True, COL_TEXT)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 86)))
            img = get_font(17, bold=False).render(map_line, True, COL_DIM)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 120)))
            img = get_font(15, bold=False).render(pts_label, True, COL_GOLD)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 141)))
        else:
            # --- FFA и команды: танки компактными строками справа.
            # v2.8: в армиях (6на6…10на10) ботов до 19 — строки СЖАТЫЕ
            # (без списка статусов, только имя + полоска HP), иначе
            # не влезают в экран
            compact = len(self.bots) > 9
            row_h = 27 if compact else 52
            for i, b in enumerate(self.bots):
                self._bot_row(b, i, 62 + i * row_h, compact=compact)
            # победы цветными сегментами (низ по центру); при толпе
            # (FFA 8-10, v2.7) шрифт мельче — полоса не налезает на края
            seg_f = get_font(26 if len(self.tanks) <= 7 else 15)
            dot = seg_f.render(" · ", True, COL_DIM)
            if self.team_mode:
                if self.is_assault:   # v3.3: сторона игрока может быть любой
                    if self.assault_def_team == 0:
                        segs = [seg_f.render("ОБОРОНА (ВЫ) %d" % self.score[0],
                                             True, COL_P1),
                                seg_f.render("АТАКА %d" % self.score[1], True,
                                             self.foes[0].color if self.foes
                                             else COL_P2)]
                    else:
                        segs = [seg_f.render("ОБОРОНА %d" % self.score[1],
                                             True, self.foes[0].color
                                             if self.foes else COL_P2),
                                seg_f.render("АТАКА (ВЫ) %d" % self.score[0],
                                             True, COL_P1)]
                else:
                    segs = [seg_f.render("КОМАНДА %d" % self.score[0], True, COL_P1),
                            seg_f.render(("БОСС %d" if self.mode == 7 else "БОТЫ %d")
                                         % self.score[1],
                                         True, self.foes[0].color if self.foes
                                         else COL_P2)]
            else:
                segs = []
                for i, t in enumerate(self.tanks):
                    nm = "ВЫ" if i == 0 else BOT_NAMES[i - 1]
                    wins = self.score[i] if i < len(self.score) else 0
                    segs.append(seg_f.render("%s %d" % (nm, wins), True, t.color))
            total = (sum(s.get_width() for s in segs)
                     + dot.get_width() * (len(segs) - 1))
            x = SCREEN_W / 2 - total / 2
            y = SCREEN_H - 44
            for s in segs:
                self.screen.blit(s, (int(x), y - s.get_height() // 2))
                x += s.get_width() + dot.get_width()
                if s is not segs[-1]:
                    self.screen.blit(dot, (int(x), y - dot.get_height() // 2))
            img = get_font(14, bold=False).render(pts_label, True, COL_GOLD)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2,
                                                       SCREEN_H - 66)))
            img = get_font(14, bold=False).render(map_line, True, COL_DIM)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2,
                                                       SCREEN_H - 22)))
        # v3.2: ШТУРМ — панель ТОЧКИ: роль, прогресс захвата и таймер обороны
        # v3.3: роль по выбранной стороне; здание вместо «центра карты»
        if self.is_assault and self.state in ("fight", "intro", "pause"):
            capx, capy = self.cap_xy
            r2 = ASSAULT_POINT_R ** 2
            on_atk = sum(1 for t in self.tanks if t.alive
                         and self.tank_team.get(t) == self.assault_atk_team
                         and (t.x - capx) ** 2 + (t.y - capy) ** 2 < r2)
            on_dfn = sum(1 for t in self.tanks if t.alive
                         and self.tank_team.get(t) == self.assault_def_team
                         and (t.x - capx) ** 2 + (t.y - capy) ** 2 < r2)
            if self.assault_def_team == 0:
                role = "ВЫ — ОБОРОНА: ДЕРЖИТЕ ЗДАНИЕ И ТОЧКУ ВНУТРИ"
            else:
                role = "ВЫ — АТАКА: ПРОРВИТЕСЬ В ЗДАНИЕ И ЗАХВАТИТЕ ТОЧКУ"
            img = get_font(16).render(role, True, COL_GOLD)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 64)))
            k = max(0.0, min(1.0, self.cap_progress / ASSAULT_CAPTURE_T))
            bar = pygame.Rect(0, 0, 320, 12)
            bar.center = (SCREEN_W / 2, 86)
            pygame.draw.rect(self.screen, (30, 36, 60), bar, border_radius=6)
            if k > 0:
                f = bar.copy()
                f.w = max(3, int(bar.w * k))
                pygame.draw.rect(self.screen, (255, 70, 70), f, border_radius=6)
            pygame.draw.rect(self.screen, (70, 80, 120), bar, 1, border_radius=6)
            if on_atk and on_dfn:
                st, col = "ТОЧКА В СПОРЕ", (255, 208, 0)
            elif on_atk:
                st = "АТАКА ЗАХВАТЫВАЕТ ТОЧКУ!"
                st, col = (st, (255, 70, 70)) if self.assault_def_team == 0 \
                    else ("ВЫ ЗАХВАТЫВАЕТЕ ТОЧКУ!", (120, 255, 150))
            elif on_dfn:
                st = "ВЫ НА ТОЧКЕ — ЗАХВАТ ОТКАТЫВАЕТСЯ"
                st, col = (st, (120, 255, 150)) if self.assault_def_team == 0 \
                    else ("ОБОРОНА НА ТОЧКЕ — ЗАХВАТ ОТКАТЫВАЕТСЯ",
                          (255, 70, 70))
            else:
                st, col = "ТОЧКА НИКЕМ НЕ ЗАНЯТА", (160, 200, 255)
            img = get_font(14, bold=False).render(
                "%s   ·   ОБОРОНЕ ДЕРЖАТЬ: %d С" % (st, int(self.cap_hold + 0.99)),
                True, col)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 106)))
        if self.spectate_t > 0 and self.state == "fight":
            img = get_font(16).render(
                "БОТЫ ВЫЯСНЯЮТ ОТНОШЕНИЯ — ДОХНУТ ЧЕРЕЗ %d С (НИЧЬЯ)"
                % int(self.spectate_t + 0.99), True, (190, 205, 255))
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2,
                                                       SCREEN_H - 140)))
            self._button(SCREEN_W / 2, SCREEN_H - 112, "УБИТЬ СРАЗУ", "kill_all",
                         w=210, h=30, fs=15)
        elif (self.team_mode and not self.player.alive
                and self.state == "fight"):
            # v2.8: кнопка теперь и в КОМАНДНЫХ режимах — вы погибли,
            # а боты воюют бесконечно? Нажмите — раунд засудят по живым:
            # перевес +2 танка забирает победу, иначе ничья.
            img = get_font(16).render(
                "КОМАНДЫ ВОЮЮТ БЕЗ ВАС — УБИТЬ СРАЗУ: ПЕРЕВЕС +2 ЖИВЫХ "
                "ЗАБИРАЕТ РАУНД, ИНАЧЕ НИЧЬЯ", True, (190, 205, 255))
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2,
                                                       SCREEN_H - 140)))
            self._button(SCREEN_W / 2, SCREEN_H - 112, "УБИТЬ СРАЗУ", "kill_all",
                         w=210, h=30, fs=15)
        # v3.0: СПЕКТАТОР — вы мертвы, но смотрите за КЕМ ХОТИТЕ
        if (not self.player.alive and self.state == "fight"
                and self.spec_target is not None):
            nm = self.spec_target.display_name or "БОТ"
            img = get_font(15).render(
                "СПЕКТАТОР: %s — ←/→ (A/D) сменить цель" % nm,
                True, (190, 205, 255))
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 166)))

    def _bot_row(self, t, idx, y, compact=False):
        """Компактная строка танка в HUD (v2.1): имя, HP, победы и статусы.
        v2.2: имя берём из display_name (СОЮЗНИК / БОСС), победы в командах
        считаются по стороне.
        v2.8: compact=True — СЖАТАЯ строка для армий (11-19 ботов): имя
        мельче, полоска HP уже, статусы не выводим (они видны на танке и
        в полосе побед внизу) — иначе 19 строк не влезают в экран."""
        # v2.6: в командах строка танка красится цветом стороны
        # v3.1: в армиях (compact) билд бота теперь ВИДЕН — коротким
        # суффиксом « · «МИНЁР»» в конце строки (раньше статусы там
        # не выводились вовсе, и билд было не разглядеть)
        sfx_suffix = (" · «%s»" % t.build_name) if (compact and t.build_name) else ""
        img = self._build_label(t, t.display_name or BOT_NAMES[idx],
                                color=self._team_ring_color(t),
                                cap=13 if compact else 22, suffix=sfx_suffix)
        self.screen.blit(img, img.get_rect(topright=(SCREEN_W - 70, y)))
        if compact:
            self._hp_bar(SCREEN_W - 330, y + 15, t, right=True, h=8)
            return
        self._hp_bar(SCREEN_W - 330, y + 22, t, right=True)
        tags = self._status_tags(t)
        if self.team_mode:
            wins = self.score[0] if self.tank_team.get(t) == 0 else self.score[1]
        else:
            wins = self.score[idx + 1] if idx + 1 < len(self.score) else 0
        tags.insert(0, "ПОБЕДЫ %d" % wins)
        if self.build[7] and t is not self.player and self.tank_team.get(t) != 0:
            tags.append("ЭФФЕКТЫ ИГРОКА %d" % len(self.build[7]))
        # v3.1: одна строка со всем списком раньше улетала влево через весь
        # экран — теперь ужимается шрифтом и при нужде режется с «…»
        label_txt = "   ".join(tags)
        fsize = 12
        while (fsize > 9
               and get_font(fsize, bold=False).size(label_txt)[0] > 560):
            fsize -= 1
        ftags = get_font(fsize, bold=False)
        if ftags.size(label_txt)[0] > 560:
            while label_txt and ftags.size(label_txt + "…")[0] > 560:
                label_txt = label_txt[:-1].rstrip()
            label_txt += "…"
        img = ftags.render(label_txt, True, (160, 200, 255))
        self.screen.blit(img, img.get_rect(topright=(SCREEN_W - 70, y + 38)))

    def _mini_info(self, t, x, y, right=False, extra=""):
        # перезарядка
        k = 1 - t.cooldown / t.reload_time
        k = max(0.0, min(1.0, k))
        bar = pygame.Rect(0, 0, 120, 6)
        bar.x, bar.y = (x - 120, y) if right else (x, y)
        pygame.draw.rect(self.screen, (30, 36, 60), bar, border_radius=3)
        f = bar.copy()
        f.w = max(2, int(120 * k))
        if right:
            f.x = x - f.w
        pygame.draw.rect(self.screen, COL_GOLD if k >= 1 else (90, 100, 140), f, border_radius=3)
        label = "ГОТОВ" if k >= 1 else "перезарядка"
        img = get_font(16, bold=False).render(label, True, COL_DIM)
        lx = x - 60 if right else x + 60
        self.screen.blit(img, img.get_rect(midtop=(lx, y + 10)))
        # эффекты и бонусы (v3.1): БИЛД и СНАРЯД — ВСЕГДА отдельной
        # золотой строкой (не теряются среди активируемых сил), остальное
        # переносится по строкам в пределах своей половины экрана —
        # раньше одна длинная строка налезала на блок врага
        sfx = self._status_tags(t)
        if extra:
            sfx.append(extra)
        f16 = get_font(16, bold=False)
        head = [s for s in sfx if s.startswith(("БИЛД:", "СНАРЯД:"))]
        rest = [s for s in sfx if s not in head]
        row_y = y + 32
        if head:
            img = f16.render("   ".join(head), True, COL_GOLD)
            if right:
                self.screen.blit(img, img.get_rect(topright=(x, row_y)))
            else:
                self.screen.blit(img, (x, row_y))
            row_y += 24
        for row in _wrap_tags(rest, f16, 540):
            img = f16.render("   ".join(row), True, (160, 200, 255))
            if right:
                self.screen.blit(img, img.get_rect(topright=(x, row_y)))
            else:
                self.screen.blit(img, (x, row_y))
            row_y += 24
        # спидометр
        img = get_font(16, bold=False).render("скорость %d px/с" % int(t.speed),
                                              True, (190, 205, 255))
        if right:
            self.screen.blit(img, img.get_rect(topright=(x, row_y)))
        else:
            self.screen.blit(img, (x, row_y))

    # ----- миникарта большого мира (v2.2) -----
    def _draw_minimap(self):
        """Миникарта в правом нижнем углу: мир 2240x1260 больше окна,
        без ориентира легко заблудиться. Показывает препятствия, танки,
        рамку видимой области. v2.9: на ней видны и ВСЕ БОНУСЫ (точки
        своих цветов), мины и турели — трофеи больше не теряются."""
        mw, mh = 192, 108
        x0, y0 = SCREEN_W - mw - 16, SCREEN_H - mh - 16
        k = mw / float(self.arena.w)
        bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
        bg.fill((8, 10, 22, 190))
        self.screen.blit(bg, (x0, y0))
        pygame.draw.rect(self.screen, (70, 80, 120), (x0, y0, mw, mh), 1)
        for r in self.arena.obstacles:
            pygame.draw.rect(self.screen, (72, 84, 140),
                             (x0 + r.x * k, y0 + r.y * k,
                              max(1.0, r.w * k), max(1.0, r.h * k)))
        # v2.9: бонусы — пульсирующие точки цветов бонусов
        for pu in self.powerups:
            px, py = int(x0 + pu.x * k), int(y0 + pu.y * k)
            pygame.draw.circle(self.screen, PU_INFO[pu.kind]["color"],
                               (px, py), 3)
            pygame.draw.circle(self.screen, (10, 12, 26), (px, py), 3, 1)
        # мины — оранжевые ромбики, турели — квадратики цвета владельца
        for m in self.mines:
            mx, my = int(x0 + m.x * k), int(y0 + m.y * k)
            pygame.draw.rect(self.screen, (255, 140, 0) if m.armed
                             else (150, 150, 160),
                             (mx - 1, my - 1, 3, 3))
        for tr in self.turrets:
            tx, ty = int(x0 + tr.x * k), int(y0 + tr.y * k)
            pygame.draw.rect(self.screen, tr.color, (tx - 2, ty - 2, 4, 4))
        # v3.0: огненные лужи — оранжевые пятна
        for fz in self.fire_zones:
            fx, fy = int(x0 + fz.x * k), int(y0 + fz.y * k)
            pygame.draw.circle(self.screen, (255, 130, 30), (fx, fy), 2)
        for t in self.tanks:
            if not t.alive:
                continue
            cx, cy = int(x0 + t.x * k), int(y0 + t.y * k)
            # v2.6: в командах миникарта красит точки цветом команды
            col = self._team_ring_color(t) or t.color
            pygame.draw.circle(self.screen, col, (cx, cy), 3)
            if t is self.player:
                pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 4, 1)
        pygame.draw.rect(self.screen, (150, 165, 230),
                         (x0 + self.cam[0] * k, y0 + self.cam[1] * k,
                          SCREEN_W * k, SCREEN_H * k), 1)

    # ================= КОНСОЛЬ РАЗРАБОТЧИКА (Ё / `) =================
    def _con_build_registry(self):
        """Имя предмета -> (категория, ключ). Имена — как в ангаре/на карте,
        всё маленькими буквами: «веер», «гаубица», «огонь», «закалить врага»."""
        reg = {}
        for key in WP_KEYS:
            reg[WEAPONS[key]["name"].lower()] = ("wpn", key)
        for key in PK_KEYS:
            reg[PERKS[key]["name"].lower()] = ("pk", key)
        for key in EL_KEYS:
            reg[ELEMENTS[key]["name"].lower()] = ("el", key)
        for key in CR_KEYS:
            reg[CURSES[key]["name"].lower()] = ("cr", key)
        for key in BL_KEYS:
            reg[BLESSINGS[key]["name"].lower()] = ("bl", key)
        for key in EE_KEYS:
            reg[ENEMY_EFFECTS[key]["name"].lower()] = ("ee", key)
        for kind, info in PU_INFO.items():
            reg[info["name"].lower()] = ("pu", kind)
        reg["заморозка"] = ("pu", "freeze")   # алиас ЭМИ
        return reg

    _CON_TARGETS = ("игрок", "я", "бот", "бот1", "бот2", "бот3", "бот4", "бот5",
                    "союзник", "союзник2", "союзник3", "союзник4",
                    "босс", "все", "всех")

    def _con_key(self, e):
        """Ввод в открытой консоли: текст (русский тоже), Enter, Tab, история."""
        k = e.key
        if k == pygame.K_ESCAPE:
            self.con_open = False
        elif k == pygame.K_RETURN:
            cmd = self.con_input.strip()
            self.con_input = ""
            if cmd:
                self._con_say("> " + cmd)  # v3.6: тоже с переносом строк
                self.con_hist.append(cmd)
                self.con_hist_i = len(self.con_hist)
                self._con_execute(cmd)
        elif k == pygame.K_TAB:
            self._con_complete()
        elif k == pygame.K_BACKSPACE:
            self.con_input = self.con_input[:-1]
        elif k == pygame.K_UP:
            if self.con_hist:
                self.con_hist_i = max(0, self.con_hist_i - 1)
                self.con_input = self.con_hist[self.con_hist_i]
        elif k == pygame.K_DOWN:
            if self.con_hist:
                self.con_hist_i = min(len(self.con_hist), self.con_hist_i + 1)
                self.con_input = (self.con_hist[self.con_hist_i]
                                  if self.con_hist_i < len(self.con_hist) else "")
        elif k == pygame.K_PAGEUP:         # v3.6: прокрутка истории
            self._con_scroll(-3)
        elif k == pygame.K_PAGEDOWN:
            self._con_scroll(3)
        elif e.unicode and e.unicode.isprintable() and len(self.con_input) < 70:
            self.con_input += e.unicode

    _CON_MAX_W = SCREEN_W - 24   # v3.6: ширина строки консоли

    def _con_wrap(self, text):
        """v3.6: длинные строки больше НЕ улетают за край консоли —
        режем по словам, точно меряя ширину шрифтом."""
        f = get_font(15, bold=False)
        out, cur = [], ""
        for w in text.split(" "):
            trial = (cur + " " + w) if cur else w
            if not cur or f.size(trial)[0] <= self._CON_MAX_W:
                cur = trial
            else:
                out.append(cur)
                cur = w
        out.append(cur)
        return out

    def _con_say(self, *lines):
        for ln in lines:
            self.con_lines.extend(self._con_wrap(ln))
        del self.con_lines[:-200]
        self.con_scroll = 0          # свежий вывод — показываем низ

    def _con_scroll(self, dy):
        """v3.6: прокрутка истории консоли (колесо мыши, PgUp/PgDn):
        dy < 0 — вверх, к старым строкам; dy > 0 — вниз, к свежим."""
        self.con_scroll = max(0, self.con_scroll - dy)

    def _con_candidates(self):
        """Все слова, которые понимает консоль: команды, предметы, цели."""
        base = (["помощь", "список", "хп", "убить", "ждать", "сброс",
                 "счёт", "очистить"]
                + list(self._con_reg.keys()) + list(self._CON_TARGETS))
        return sorted(set(base))

    def _con_hints(self):
        """Подсказки под строкой ввода: пишешь «Ту» — консоль подскажет
        «Турбо». Tab дополняет ввод первой подсказкой."""
        toks = self.con_input.split()
        tok = toks[-1].lower() if toks else ""
        if not tok:
            return []
        return [c for c in self._con_candidates()
                if c.startswith(tok) and c != tok][:5]

    def _con_complete(self):
        hints = self._con_hints()
        if not hints:
            return
        toks = self.con_input.split()
        toks = (toks[:-1] + [hints[0]]) if toks else [hints[0]]
        self.con_input = " ".join(toks) + " "

    def _con_tname(self, t):
        """Человекочитаемое имя танка для ответов консоли."""
        if t is self.player:
            return "Игрок"
        return t.display_name or "Бот"

    def _con_targets(self, toks):
        """Разобрать цель из слов: «Игрок», «Я», «Бот», «Бот2», «Союзник»,
        «Союзник2», «Босс», «Все» или число (номер танка, 1 = игрок).
        v2.3: «Бот/БотN» — это ЧУЖАКИ (в командах союзник ботом не считается)."""
        allies = [b for b in self.bots if self.tank_team.get(b) == 0]
        tanks, rest = [], []
        for tok in toks:
            t = tok.strip(",.")
            if t in ("игрок", "я"):
                if self.player:
                    tanks.append(self.player)
            elif t == "союзник":
                tanks += allies
            elif t.startswith("союзник") and t[-1].isdigit():
                i = int(t[-1]) - 1
                if 0 <= i < len(allies):
                    tanks.append(allies[i])
            elif t in ("все", "всех"):
                tanks += [tk for tk in self.tanks if tk is not self.player]
            elif t == "босс":
                tanks += [b for b in self.bots if b.display_name == "БОСС"]
            elif t == "бот":
                tanks += self.foes[:1]
            elif t.startswith("бот") and t[-1].isdigit():
                i = int(t[-1]) - 1
                if 0 <= i < len(self.foes):
                    tanks.append(self.foes[i])
            elif t.isdigit():
                i = int(t) - 1
                if 0 <= i < len(self.tanks):
                    tanks.append(self.tanks[i])
            else:
                rest.append(tok)
        return tanks, rest

    def _con_resprite(self, t):
        """Перерисовать спрайт танка (сменилось дуло/стихия) с учётом масштаба."""
        t._sprite = t._make_sprite()
        if t.scale != 1.0:
            t._sprite = pygame.transform.smoothscale(
                t._sprite, (int(64 * t.scale), int(50 * t.scale)))

    def _con_give(self, t, cat, key):
        """Выдать предмет танку ПРЯМО В БОЮ (консоль для тестов).
        wpn/pk/el/cr/bl/ee меняют сборку на лету, pu применяет бонус."""
        if cat == "pu":
            if key == "freeze":
                t.frozen_t = PU_FREEZE_TIME
            elif key == "smoke":
                self.smokes.append(Smoke(t.x, t.y))
            else:
                t.apply_powerup(key)
            return
        if cat == "wpn":
            t.wpn_key = key
            t.weapon = WEAPONS[key]
            t.mag_size = t.weapon["mag"]
            t.mag_ammo = t.mag_size
            self._con_resprite(t)
            return
        if cat == "pk":
            t.perk_key = key
            t.perk = PERKS[key]
            t.bullet_bounces = BULLET_BOUNCES + int(t.perk.get("bounces", 0))
            t.max_hp = max(20, int(round(t.hull["hp"] * t.perk["hp_mult"]
                                        * t.mods["hp_mult"])))
            t.hp = min(t.hp, t.max_hp)
            return
        if cat == "el":
            if key == "none":
                t.element_keys = []
                t.element_key = "none"
                t.elem = ELEMENTS["none"]
            else:
                # НЕСКОЛЬКО стихий на одном танке: «Огонь» + «Вода» = микс
                if key not in t.element_keys:
                    t.element_keys.append(key)
                if t.element_key == "none":
                    t.element_key = key
                    t.elem = ELEMENTS[key]
            self._con_resprite(t)
            return
        table = {"cr": CURSES, "bl": BLESSINGS, "ee": ENEMY_EFFECTS}[cat]
        for f, v in table[key]["mods"].items():
            if f == "spread_deg":
                t.mods[f] += v
            else:
                t.mods[f] *= v
        t.max_hp = max(20, int(round(t.hull["hp"] * t.perk["hp_mult"]
                                    * t.mods["hp_mult"])))
        t.hp = min(t.hp, t.max_hp)

    def _con_item_name(self, cat, key):
        table = {"wpn": WEAPONS, "pk": PERKS, "el": ELEMENTS, "cr": CURSES,
                 "bl": BLESSINGS, "ee": ENEMY_EFFECTS, "pu": PU_INFO}
        return table[cat][key]["name"]

    def _con_execute(self, cmd):
        """Исполнить команду консоли: команды, предметы, цели."""
        parts = cmd.lower().replace("ё", "е").split()
        if not parts:
            return
        if parts[0] in ("помощь", "help"):
            self._con_say(
                "КОМАНДЫ КОНСОЛИ:",
                "  <предмет> [кому] — выдать: Огонь Игрок · Гаубица Бот · Рикошет Бот2",
                "  бонусы (веер, турбо, щит...) БЕЗ цели — ставятся КЛИКОМ на карту,",
                "    потом можно просто подъехать и забрать (как обычный бонус)",
                "  хп <N> [кому] — выставить прочность · убить [кому] — убить",
                "  ждать <сек> — окно выяснения после вашей смерти (0 — выключить)",
                "  счёт <N> — накинуть очков · сброс — перезапустить раунд",
                "  список — все предметы · очистить — убрать этот текст",
                "КОМУ: Игрок / Я / Бот / Бот2..5 / Союзник(2,3,4) / Босс / Все / число",
                "(в командах Бот — это только ЧУЖАКИ, союзники — Союзник/Союзник2/3/4)",
                "Стихии СКЛАДЫВАЮТСЯ: «Огонь Игрок» потом «Вода 1 Игрок» — и то и то.",
                "Пиши «Ту» — подскажет «Турбо» (Tab — дополнить). Ё — закрыть.")
            return
        if parts[0] == "список":
            for title, keys, table in (
                    ("ДУЛА", WP_KEYS, WEAPONS), ("ПЕРКИ", PK_KEYS, PERKS),
                    ("СТИХИИ", EL_KEYS, ELEMENTS),
                    ("ПРОКЛЯТЬЯ", CR_KEYS, CURSES),
                    ("ОБЛЕГЧЕНИЯ", BL_KEYS, BLESSINGS),
                    ("НА ВРАГА", EE_KEYS, ENEMY_EFFECTS)):
                self._con_say(title + ": " + ", ".join(
                    table[k2]["name"].lower() for k2 in keys))
            self._con_say("БОНУСЫ (ставятся кликом): " + ", ".join(
                i["name"].lower() for i in PU_INFO.values()))
            return
        if parts[0] == "очистить":
            self.con_lines = []
            self.con_scroll = 0
            return
        if parts[0] == "сброс":
            if self.state in ("intro", "fight", "round_end", "pause"):
                self._reset_round()
                self.state = "intro"
                self.timer = ROUND_BANNER_T
                self._con_say("Раунд перезапущен.")
            else:
                self._con_say("Сброс доступен только в бою.")
            return
        if parts[0] == "ждать":
            if len(parts) > 1 and parts[1].lstrip("-").isdigit():
                sec = max(0, int(parts[1]))
                self.spectate_t = float(sec)
                self._con_say("Окно выяснения после вашей смерти: %d с." % sec)
            else:
                self._con_say("Формат: ждать 180 / ждать 0")
            return
        if parts[0] == "счет":   # ё нормализована в е выше
            if len(parts) > 1 and parts[1].lstrip("-").isdigit():
                self.points += int(parts[1])
                self._con_say("Сырых очков теперь: %.0f" % self.points)
            else:
                self._con_say("Формат: счёт 500")
            return
        if self.player is None:
            self._con_say("Сначала начни бой — в меню выдавать некому.")
            return
        if parts[0] == "хп":
            nums = [i for i, p in enumerate(parts) if i and p.isdigit()]
            if not nums:
                self._con_say("Формат: хп 200 [кому]")
                return
            val = max(1, int(parts[nums[0]]))
            rest = [p for i, p in enumerate(parts)
                    if i > 0 and i != nums[0]]
            tanks, _ = self._con_targets(rest)
            if not tanks:
                tanks = [self.player]
            for t2 in tanks:
                t2.hp = min(t2.max_hp, val)
            self._con_say("Прочность %d: %s" % (
                val, ", ".join(self._con_tname(t2) for t2 in tanks)))
            return
        if parts[0] == "убить":
            tanks, _ = self._con_targets(parts[1:])
            if not tanks:
                tanks = list(self.foes)
            for t2 in tanks:
                if t2.alive:
                    t2._die(self.effects, self.sounds)
            self._con_say("Убиты: %s" % (", ".join(
                self._con_tname(t2) for t2 in tanks) or "никто"))
            return
        # ---- предмет: «Вода 1 Игрок», «Веер», «Гаубица Бот» ----
        item, used = None, 0
        for j in range(min(4, len(parts)), 0, -1):
            name = " ".join(parts[:j])
            if name in self._con_reg:
                item = self._con_reg[name]
                used = j
                break
        if item is None:
            self._con_say("Не понял. «помощь» — команды, «список» — предметы.")
            return
        cat, key = item
        toks = parts[used:]
        if cat == "pu" and not toks:
            # бонус БЕЗ цели — ставим кликом на карту (поставил — потом забрал)
            if self.state in ("intro", "fight"):
                self.con_place = key
                self.con_open = False
                self._con_say("Кликни по карте, чтобы поставить «%s»."
                              % PU_INFO[key]["name"].upper())
            else:
                self._con_say("Бонус на карту ставится только в бою.")
            return
        tanks, rest = self._con_targets(toks)
        if not tanks:
            tanks = ([self.bot_tank] if cat == "ee" and self.bot_tank
                     else [self.player])
        for t2 in tanks:
            self._con_give(t2, cat, key)
        self._con_say("Выдано «%s»: %s" % (
            self._con_item_name(cat, key),
            ", ".join(self._con_tname(t2) for t2 in tanks)))

    def _con_do_place(self, pos):
        """Клик в режиме установки бонуса: бонус появляется на карте мира —
        подъезжай и подбирай, как обычный."""
        kind = self.con_place
        self.con_place = None
        wx, wy = pos[0] + self.cam[0], pos[1] + self.cam[1]
        if self.arena.circle_collides(wx, wy, 26):
            self.effects.float_text(wx, wy - 40, "ЗДЕСЬ НЕ ПОСТАВИТЬ",
                                    (255, 90, 90))
            return
        self.powerups.append(PowerUp(wx, wy, kind))
        self.effects.burst(wx, wy, PU_INFO[kind]["color"], 10, 150, 0.4, 3)
        self.effects.float_text(wx, wy - 40,
                                "%s ПОСТАВЛЕН" % PU_INFO[kind]["name"],
                                PU_INFO[kind]["color"])
        self.sounds.play("pickup")

    def _draw_place_hint(self):
        info = PU_INFO[self.con_place]
        text = "КЛИК — поставить «%s»   ·   Esc — отмена" % info["name"].upper()
        img = get_font(20).render(text, True, info["color"])
        r = img.get_rect(center=(SCREEN_W / 2, 60))
        bg = pygame.Surface((r.w + 24, r.h + 12), pygame.SRCALPHA)
        bg.fill((6, 8, 20, 210))
        self.screen.blit(bg, (r.x - 12, r.y - 6))
        self.screen.blit(img, r)

    def _draw_console(self):
        """Консоль разработчика внизу экрана: история (v3.6 — с
        ПЕРЕНОСОМ длинных строк и ПРОКРУТКОЙ), строка ввода и ПОДСКАЗКИ
        под ней — пишешь «Ту», она пишет «Турбо» (Tab — дополнить)."""
        h = 272
        panel = pygame.Surface((SCREEN_W, h), pygame.SRCALPHA)
        panel.fill((6, 8, 20, 232))
        self.screen.blit(panel, (0, SCREEN_H - h))
        pygame.draw.line(self.screen, COL_P1,
                         (0, SCREEN_H - h), (SCREEN_W, SCREEN_H - h), 2)
        f = get_font(15, bold=False)
        y = SCREEN_H - h + 8
        vis = 10                                   # видно строк
        n = len(self.con_lines)
        sc = min(self.con_scroll, max(0, n - vis))  # не выше начала
        if sc <= 0:
            chunk = self.con_lines[-vis:]
        else:
            chunk = self.con_lines[-(vis + sc):-sc]
        for ln in chunk:
            img = f.render(ln, True,
                           COL_P1 if ln.startswith(">") else (150, 160, 200))
            self.screen.blit(img, (10, y))
            y += 19
        if sc > 0:      # подсказка: выше есть ещё строки
            up = get_font(12, bold=False).render(
                "↑ ещё %d стр. (колесо/PgUp)" % sc, True, (130, 140, 185))
            self.screen.blit(up, (SCREEN_W - up.get_width() - 12,
                                  SCREEN_H - h + 8))
        self._con_blink += 1 / 60.0
        cur = "_" if int(self._con_blink * 2) % 2 == 0 else " "
        img = get_font(19).render("> " + self.con_input + cur, True, COL_TEXT)
        self.screen.blit(img, (10, SCREEN_H - 56))
        hints = self._con_hints()
        if hints:
            img = get_font(16).render("Tab: " + hints[0], True, COL_GOLD)
            self.screen.blit(img, (10, SCREEN_H - 30))
            rest = "   ".join(hints[1:])
            if rest:
                img2 = get_font(14, bold=False).render(rest, True, (120, 130, 170))
                self.screen.blit(img2, (36 + img.get_width(), SCREEN_H - 27))
        else:
            img = get_font(13, bold=False).render(
                "Ё — закрыть · ↑/↓ — история · колесо/PgUp — прокрутка · «помощь» — команды",
                True, (95, 105, 145))
            self.screen.blit(img, (10, SCREEN_H - 27))

    # ================= главный цикл =================
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    # таблица счёта и статистика уже на диске после каждого
                    # матча, но на всякий случай сохраняемся и при выходе
                    self._save_stats()
                    pygame.quit()
                    return
                if e.type == pygame.MOUSEMOTION:
                    self._mouse = e.pos          # для подсветки наведения
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.con_place and self.state == "fight" \
                            and not self.con_open:
                        self._con_do_place(e.pos)   # бонус кликом на карту
                    elif not self.con_open:
                        self.on_click(e.pos)     # мышь: выбор и кнопки
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3 \
                        and self.state == "editor" and not self.con_open:
                    self._ed_click(e.pos, erase=True)   # ПКМ — стереть
                elif e.type == pygame.MOUSEWHEEL and self.con_open:
                    self._con_scroll(e.y * 2)    # v3.6: листаем историю
                self.on_keydown(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()
