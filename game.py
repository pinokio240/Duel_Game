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
                      CURSES, BLESSINGS, MAX_CURSES, ENEMY_EFFECTS,
                      MAX_ENEMY_EFFECTS,
                      BULLET_DAMAGE,
                      POWERUP_INTERVAL, POWERUP_MAX, PU_MINE_DAMAGE,
                      PU_MINE_RADIUS, PU_MINE_MAX, PU_MINE_LIFE, PU_LASER_DAMAGE,
                      PU_LASER_FAN_DAMAGE, PU_LASER_FAN_SPREAD,
                      PU_SMOKE_TIME, PU_SMOKE_RADIUS, PU_FREEZE_TIME,
                      PU_MINE_ENEMY_DIST,
                      BARRIER_HP, BARRIER_LIFE, BARRIER_LEN, BARRIER_THICK,
                      BARRIER_DIST, BARRIER_MAX,
                      SCORE_CURSE_BONUS, SCORE_BLESS_PENALTY, SCORE_MULT_FLOOR,
                      SCORE_ROUND_WIN, SCORE_ROUND_DRAW, SCORE_MATCH_WIN,
                      SCORE_PICKUP,
                      DIFF_PRESETS, BOT_DIFFICULTY)
from arena import Arena, LAYOUTS
from tank import Tank
from bot import BotAI, random_build
from powerup import PowerUp, Mine, PU_INFO
from effects import Effects, get_font
from sound import SoundBank

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
    """Стена-бустер: ставится танком по Q, имеет 120 прочности,
    блокирует танки и взгляд, пробивается снарядами, рассыпается со временем."""

    def __init__(self, x, y, angle_deg, owner):
        self.x, self.y = float(x), float(y)
        self.owner = owner
        rad = math.radians(angle_deg)
        hl = BARRIER_LEN / 2
        self.p1 = (x - math.cos(rad) * hl, y - math.sin(rad) * hl)
        self.p2 = (x + math.cos(rad) * hl, y + math.sin(rad) * hl)
        self.hp = BARRIER_HP
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
        return self.t >= BARRIER_LIFE

    def draw(self, surf, ox=0, oy=0):
        ax, ay = self.p1[0] + ox, self.p1[1] + oy
        bx, by = self.p2[0] + ox, self.p2[1] + oy
        blink = self.t > BARRIER_LIFE - 3 and int(self.t * 6) % 2 == 0
        k = self.hp / BARRIER_HP
        if blink:
            core = (90, 95, 115)
        elif k > 0.5:
            core = (205, 210, 225)
        else:
            core = (235, 150, 80)   # треснула — вот-вот развалится
        pygame.draw.line(surf, (52, 58, 84), (ax, ay), (bx, by), BARRIER_THICK + 6)
        pygame.draw.line(surf, (86, 96, 150), (ax, ay), (bx, by), BARRIER_THICK)
        pygame.draw.line(surf, core, (ax, ay), (bx, by), 4)
        for px, py in ((ax, ay), (bx, by)):
            pygame.draw.circle(surf, core, (int(px), int(py)), 4)


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
        # сборка игрока: шасси, корпус, дуло, перк, стихия,
        # проклятья, облегчения, эффекты НА ВРАГА
        self.build = ("medium", "medium", "standard", "none", "none", (), (), ())
        self.bot_build = ("medium", "medium", "standard", "none", "none")
        self.sel_ch, self.sel_hu = 1, 1     # курсоры в ангаре
        self.sel_wpn, self.sel_pk, self.sel_el = 0, 0, 0
        self.sel_jt = 0                     # курсор жребия (0..15)
        self.sel_curses = []                # взятые проклятья (ключи)
        self.sel_blessings = []             # взятые облегчения (ключи)
        self.sel_en = 0                     # курсор эффектов на врага
        self.sel_enemy_keys = []            # взятые эффекты НА ВРАГА (ключи)
        self.score = [0, 0]
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
        self.bot_tank = None
        self.ai = None
        self.bullets = []
        self.powerups = []
        self.mines = []
        self.smokes = []
        self.barriers = []
        self.powerup_t = POWERUP_INTERVAL * 0.6

        self._fake_keys = None  # только для автотестов
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
    def _reset_round(self):
        cx, cy = SCREEN_W / 2, SCREEN_H / 2
        self.player = Tank(cx - 400, cy, 0, self.build[0], self.build[1], COL_P1,
                           self.build[2], self.build[3], self.build[4],
                           self.build[5], self.build[6])
        # эффекты НА ВРАГА: словарь модов для бота (баффы и дебаффы)
        emods = {}
        for key in self.build[7]:
            for f, v in ENEMY_EFFECTS[key]["mods"].items():
                if f == "spread_deg":
                    emods[f] = emods.get(f, 0.0) + v
                else:
                    emods[f] = emods.get(f, 1.0) * v
        self.bot_tank = Tank(cx + 400, cy, 180, self.bot_build[0], self.bot_build[1],
                             COL_P2, self.bot_build[2], self.bot_build[3],
                             self.bot_build[4], extra_mods=emods or None)
        self.ai = BotAI(self.bot_tank, self.difficulty)
        self.bullets = []
        self.powerups = []
        self.mines = []
        self.smokes = []
        self.barriers = []
        self.arena.set_dynamic([])
        self.powerup_t = POWERUP_INTERVAL * 0.6
        self.effects.particles.clear()
        self.effects.texts.clear()

    def start_match(self):
        self.arena = Arena(random.randrange(len(LAYOUTS)))  # случайная арена на матч
        self.bot_build = random_build()
        self.score = [0, 0]
        self.round = 1
        self.points = 0.0
        self.score_mult = self._score_mult()   # жребий уже учтён в сборке
        self._reset_round()
        self.state = "intro"
        self.timer = ROUND_BANNER_T
        self.sounds.play("round")

    # ================= жребий: проклятья и облегчения =================
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
        elif len(self.sel_curses) < MAX_CURSES:
            self.sel_curses.append(key)

    def _toggle_bless(self, idx):
        key = BL_KEYS[idx]
        if key in self.sel_blessings:
            self.sel_blessings.remove(key)
        elif len(self.sel_blessings) < self._bless_cap():
            self.sel_blessings.append(key)

    def _toggle_enemy(self, idx):
        """Эффекты НА ВРАГА: баффы и дебаффы, любой режет счёт."""
        key = EE_KEYS[idx]
        if key in self.sel_enemy_keys:
            self.sel_enemy_keys.remove(key)
        elif len(self.sel_enemy_keys) < MAX_ENEMY_EFFECTS:
            self.sel_enemy_keys.append(key)

    def _fate_mult(self, curses, blessings, enemy):
        """Множитель очков: проклятья ДОБАВЛЯЮТ 15% каждое (риск платит),
        облегчения режут 10%, эффекты на врага — по своей цене."""
        m = (1.0 + SCORE_CURSE_BONUS * len(curses)
             - SCORE_BLESS_PENALTY * len(blessings))
        for key in enemy:
            m -= ENEMY_EFFECTS[key]["score_cut"]
        return max(SCORE_MULT_FLOOR, m)

    def _score_mult(self):
        """Множитель очков за ЗАФИКСИРОВАННУЮ сборку."""
        return self._fate_mult(self.build[5], self.build[6], self.build[7])

    # ================= ввод (клавиатура по событиям) =================
    def on_keydown(self, e):
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
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
            if k == pygame.K_ESCAPE:
                self.state = "pause"
            elif k == pygame.K_q:
                self._place_barrier(self.player)   # стена-бустер
            elif k == pygame.K_e:
                self._place_mine(self.player)      # мина руками
        elif self.state == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.state = "fight"
            elif k == pygame.K_a:
                # выход в ангар: матч сбрасывается — сборка-то меняется
                self.score = [0, 0]
                self.round = 1
                self.state = "select"
            elif k == pygame.K_m:
                self.state = "menu"
        elif self.state == "match_end":
            if k == pygame.K_RETURN:
                self.start_match()
            elif k == pygame.K_a:
                self.score = [0, 0]
                self.round = 1
                self.state = "select"   # в ангар за новой сборкой
            elif k == pygame.K_t:
                self._table_from = "match_end"
                self.state = "table"    # посмотреть таблицу счёта
            elif k in (pygame.K_m, pygame.K_ESCAPE):
                self.state = "menu"

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
            self._fight_step(dt)

        elif self.state == "round_end":
            self.timer -= dt
            if self.timer <= 0:
                if max(self.score) >= ROUNDS_TO_WIN:
                    self.state = "match_end"
                    if self.score[0] > self.score[1]:
                        self.stats["wins"] += 1
                        self.points += SCORE_MATCH_WIN
                        res = "win"
                    elif self.score[1] > self.score[0]:
                        self.stats["losses"] += 1
                        res = "loss"
                    else:
                        self.stats["draws"] += 1
                        res = "draw"
                    self.final_score = int(self.points * self.score_mult)
                    # --- ТАБЛИЦА СЧЕТА: забег попадает в топ-10 ---
                    entry = {
                        "score": self.final_score, "res": res,
                        "rounds": "%d:%d" % tuple(self.score),
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
                    self.table_place = next(
                        i for i, r in enumerate(table) if r is entry) + 1
                    self.new_record = (self.table_place == 1
                                       and self.final_score > 0)
                    if self.final_score > self.stats.get("best_score", 0):
                        self.stats["best_score"] = self.final_score
                    self._save_stats()
                    self.sounds.play("win" if self.score[0] > self.score[1] else "lose")
                else:
                    self.round += 1
                    self._reset_round()
                    self.state = "intro"
                    self.timer = ROUND_BANNER_T
                    self.sounds.play("round")

    def _read_keys(self):
        if self._fake_keys is not None:
            return self._fake_keys
        return pygame.key.get_pressed()

    def _fight_step(self, dt):
        keys = self._read_keys()
        fwd = ((keys[pygame.K_w] or keys[pygame.K_UP]) -
               (keys[pygame.K_s] or keys[pygame.K_DOWN]))
        tn = ((keys[pygame.K_d] or keys[pygame.K_RIGHT]) -
              (keys[pygame.K_a] or keys[pygame.K_LEFT]))

        # барьеры участвуют в коллизиях танков и в обзоре бота
        self.arena.set_dynamic(self.barriers)

        self.player.update(dt)
        self.bot_tank.update(dt)
        self.player._burn_step(dt, self.effects, self.sounds)
        self.bot_tank._burn_step(dt, self.effects, self.sounds)
        self.player.control(dt, self.arena, fwd, tn, (self.bot_tank,))
        self.ai.update(dt, self)
        if keys[pygame.K_SPACE]:
            self.fire_weapon(self.player)

        hp0 = self.bot_tank.hp   # для очков: сколько HP отнимем за этот кадр

        # снаряды бьют стены-барьеры (а стены блокируют и обзор бота)
        walls = self.arena.walls_only()
        for b in self.bullets:
            self._bullet_vs_barriers(b)
            if not b.dead:
                b.update(dt, walls, (self.player, self.bot_tank),
                         self.effects, self.sounds)
            self._bullet_vs_barriers(b)
        self.bullets = [b for b in self.bullets if not b.dead]

        for br in self.barriers[:]:
            br.update(dt)
            if br.expired():
                self.barriers.remove(br)
                self.effects.burst(br.x, br.y, (205, 210, 225), 10, 160, 0.4, 3)

        self._mines_step(dt)
        self._smokes_step(dt)
        self._powerups_step(dt)

        if not self.player.alive or not self.bot_tank.alive:
            # очки за урон в этом кадре (включая добивание)
            if self.bot_tank.hp < hp0:
                self.points += hp0 - self.bot_tank.hp
            if self.player.alive:
                self.winner = 0   # выжил игрок
            elif self.bot_tank.alive:
                self.winner = 1   # выжил бот
            else:
                self.winner = -1  # оба подорвались — ничья, очко никому
            if self.winner >= 0:
                self.score[self.winner] += 1
                if self.winner == 0:
                    self.points += SCORE_ROUND_WIN
            else:
                self.points += SCORE_ROUND_DRAW
            self.state = "round_end"
            self.timer = ROUND_PAUSE_T
            self.sounds.play("round")
        elif self.bot_tank.hp < hp0:
            # очки за урон врагу: снаряды, лазер, мины, пожар — 1:1 за HP
            self.points += hp0 - self.bot_tank.hp

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
        """Один луч: лучевая трассировка до стены, поджигает первого врага."""
        rad = math.radians(angle_deg)
        sx = shooter.x + math.cos(rad) * (shooter.radius + 16)
        sy = shooter.y + math.sin(rad) * (shooter.radius + 16)
        x, y = sx, sy
        hit = None
        for _ in range(int(2000 / 6)):
            x += math.cos(rad) * 6
            y += math.sin(rad) * 6
            if self.arena.point_blocked(x, y):
                break
            for t in (self.player, self.bot_tank):
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
        enemy = self.bot_tank if t is self.player else self.player
        if (enemy.alive and
                (t.x - enemy.x) ** 2 + (t.y - enemy.y) ** 2 < PU_MINE_ENEMY_DIST ** 2):
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
        Если там стена/танк — пробуем ближе; совсем нельзя — честно скажем."""
        if t.barrier_charges <= 0:
            return False
        if angle is None:
            angle = t.angle
        rad = math.radians(angle)
        ux, uy = math.cos(rad), math.sin(rad)
        enemy = self.bot_tank if t is self.player else self.player
        for dist in (BARRIER_DIST, 64, 44, 28):
            cx, cy = t.x + ux * dist, t.y + uy * dist
            br = Barrier(cx, cy, angle + 90, t)
            # стены/препятствия не трогаем
            if any(self.arena.circle_collides(px, py, BARRIER_THICK)
                   for px, py in (br.p1, (br.x, br.y), br.p2)):
                continue
            # в танки не втыкаем (и в себя, и во врага)
            if any(tk.alive and br.blocks_circle(tk.x, tk.y, tk.radius)
                   for tk in (self.player, self.bot_tank)):
                continue
            t.barrier_charges -= 1
            self.barriers.append(br)
            self.arena.set_dynamic(self.barriers)
            self.effects.burst(cx, cy, (205, 210, 225), 8, 150, 0.3, 3)
            self.sounds.play("ric")
            return True
        self.effects.float_text(t.x, t.y - 54, "ЗДЕСЬ НЕ ПОСТАВИТЬ", (255, 90, 90))
        return False

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
        for m in self.mines[:]:
            m.update(dt)
            if m.t > PU_MINE_LIFE:
                self.mines.remove(m)
                continue
            if not m.armed:
                continue
            for t in (self.player, self.bot_tank):
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
                avoid=((self.player.x, self.player.y),
                       (self.bot_tank.x, self.bot_tank.y)))
            self.powerups.append(PowerUp(x, y, random.choice(list(PU_INFO))))
            self.powerup_t = POWERUP_INTERVAL
        for pu in self.powerups[:]:
            for t in (self.player, self.bot_tank):
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
            enemy = self.bot_tank if t is self.player else self.player
            if enemy.alive:
                enemy.frozen_t = PU_FREEZE_TIME
                self.effects.float_text(enemy.x, enemy.y - 54, "ЭМИ!", info["color"])
            self.sounds.play("freeze")
        else:
            # мина и стена носятся в боекомплекте (E / Q) — всё в apply_powerup
            t.apply_powerup(pu.kind)
        if t is self.player:
            self.points += SCORE_PICKUP   # очки за подбор бонуса
        self.effects.float_text(t.x, t.y - 54, info["name"], info["color"])
        self.sounds.play("pickup")

    # ================= отрисовка =================
    def draw(self):
        ox, oy = self.effects.offset()
        self.world.fill((0, 0, 0))
        self.arena.draw(self.world, ox, oy)

        in_battle = self.state in ("intro", "fight", "round_end", "pause", "match_end")
        if in_battle:
            for pu in self.powerups:
                pu.draw(self.world, ox, oy)
            for m in self.mines:
                m.draw(self.world, ox, oy)
            for br in self.barriers:
                br.draw(self.world, ox, oy)
            for b in self.bullets:
                b.draw(self.world, ox, oy)
            if self.bot_tank.alive:
                self.bot_tank.draw(self.world, ox, oy)
            if self.player.alive:
                self.player.draw(self.world, ox, oy)
            self.effects.draw(self.world, ox, oy)
            for s in self.smokes:
                s.draw(self.world, ox, oy)
        self.screen.blit(self.world, (0, 0))

        if self.state == "menu":
            self._draw_menu()
        elif self.state == "select":
            self._draw_select()
        elif self.state == "table":
            self._draw_table()
        elif in_battle:
            self._draw_hud()
            if self.state == "intro":
                self._banner("РАУНД %d" % self.round, COL_GOLD,
                             "карта «%s»" % self.arena.name)
            elif self.state == "round_end":
                if self.winner == 0:
                    self._banner("РАУНД ЗА ИГРОКОМ", COL_P1,
                                 sub2="+%d ОЧКОВ" % SCORE_ROUND_WIN)
                elif self.winner == 1:
                    self._banner("РАУНД ЗА БОТОМ", COL_P2)
                else:
                    self._banner("НИЧЬЯ", COL_TEXT,
                                 sub2="+%d ОЧКОВ" % SCORE_ROUND_DRAW)
            elif self.state == "match_end":
                self._draw_match_end()
            elif self.state == "pause":
                self._banner("ПАУЗА", COL_TEXT,
                             "Esc — продолжить   A — ангар   M — меню")

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
            "W/S — вперёд и назад   A/D — поворот   Пробел — выстрел",
            "Q — стена (120 прочности)   E — мина   Лазер + Веер = ЛАЗЕРНЫЙ ВЕЕР!",
            "Ангар: шасси, корпус, дуло, перк, стихия — 1800 сборок.",
            "ЖРЕБИЙ: проклятья ослабляют ТОЛЬКО ВАС, но каждое +15% ОЧКОВ.",
            "Облегчения помогают, но режут счёт; без проклятий — максимум одно.",
            "На врага можно навесить баффы или дебаффы — это тоже режет счёт.",
            "10 арен, 10 бонусов. Бот собирает бонусы и строит стены!",
        ]
        y = 310
        for s in lines:
            img = get_font(22, bold=False).render(s, True, COL_DIM)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y)))
            y += 34
        # выбор сложности
        y += 6
        img = get_font(20, bold=False).render("Сложность бота (1/2/3):", True, COL_DIM)
        self.screen.blit(img, img.get_rect(midright=(SCREEN_W / 2 - 120, y)))
        for i, dkey in enumerate((1, 2, 3)):
            color = COL_GOLD if self.difficulty == dkey else (70, 80, 120)
            img = get_font(20).render("%d %s" % (dkey, DIFF_NAMES[dkey]), True, color)
            self.screen.blit(img, (SCREEN_W / 2 - 100 + i * 135, y - img.get_height() / 2))
        # статистика матчей и рекорд
        y += 42
        st = "Побед: %d   Поражений: %d   Ничьих: %d   ·   Рекорд очков: %d" % (
            self.stats["wins"], self.stats["losses"], self.stats["draws"],
            self.stats.get("best_score", 0))
        img = get_font(18, bold=False).render(st, True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y)))
        # призыв
        img = get_font(26).render("Enter — в ангар      T — ТАБЛИЦА СЧЕТА",
                                  True, COL_P1)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y + 44)))
        # версия
        img = get_font(16, bold=False).render("v1.7", True, (60, 66, 95))
        self.screen.blit(img, (SCREEN_W - 60, SCREEN_H - 34))

    def _draw_select(self):
        self.screen.fill((10, 12, 26))   # непрозрачный фон: старый бой не просвечивает
        t1 = get_font(30).render("АНГАР", True, COL_TEXT)
        self.screen.blit(t1, t1.get_rect(center=(SCREEN_W / 2, 30)))

        ch = CHASSIS[CH_KEYS[self.sel_ch]]
        wp = WEAPONS[WP_KEYS[self.sel_wpn]]
        el = ELEMENTS[EL_KEYS[self.sel_el]]

        # --- пять компактных панелей сборки ---
        self._choice_panel("ШАССИ   (A / D)", CH_KEYS, self.sel_ch, CHASSIS, 96)
        self._choice_panel("КОРПУС   (W / S)", HU_KEYS, self.sel_hu, HULL, 162)
        self._choice_panel("ДУЛО   (Q / E)", WP_KEYS, self.sel_wpn, WEAPONS, 228)
        self._choice_panel("ПЕРК   (Z / C)", PK_KEYS, self.sel_pk, PERKS, 294)
        self._choice_panel("СТИХИЯ   (F / G)", EL_KEYS, self.sel_el, ELEMENTS, 360)

        # --- жребий: проклятья (+очки) и облегчения (-очки) ---
        mult = self._fate_mult(self.sel_curses, self.sel_blessings,
                               self.sel_enemy_keys)
        self._fate_panel(422, 460, mult)

        # --- эффекты НА ВРАГА ---
        self._enemy_panel(552)

        # итоговые характеристики — с учётом жребия
        preview = Tank(0, 0, 0, CH_KEYS[self.sel_ch], HU_KEYS[self.sel_hu], COL_P1,
                       WP_KEYS[self.sel_wpn], PK_KEYS[self.sel_pk],
                       EL_KEYS[self.sel_el],
                       tuple(self.sel_curses), tuple(self.sel_blessings))
        stats_line = ("Скорость: %.0f px/с    Прочность: %d    Броня: %d    "
                      "Урон: %d    Выстрел: %.2f с"
                      % (preview.speed, preview.max_hp, ch["armor"],
                         round(BULLET_DAMAGE * wp["damage_mult"]
                               * el["damage_mult"] * preview.mods["damage_mult"]),
                         preview.reload_time))
        if preview.mods["spread_deg"] > 0:
            stats_line += "    Разброс: %d°" % round(preview.mods["spread_deg"])
        img = get_font(18).render(stats_line, True,
                                  (255, 150, 90) if preview.speed < 110 else COL_TEXT)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 614)))
        img = get_font(21).render("Enter — в бой      Esc — назад      "
                                  "Очки за забег: x%.2f" % mult, True, COL_P1)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 644)))

        # превью танка игрока (внизу справа, чтобы не мешать панелям)
        img = pygame.transform.scale_by(preview._sprite, 1.6)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W - 100, 664)))

    def _fate_panel(self, y_cur, y_bless, mult):
        """Жребий: 8 проклятий (красные) и 8 облегчений (зелёные).
        R/T — курсор, V — взять/снять. Без проклятий — максимум одно
        облегчение. Проклятья ослабляют ТОЛЬКО ВАС, но ДЕЛАЮТ ОЧКИ."""
        t = get_font(17).render(
            "ЖРЕБИЙ   (R / T — курсор, V — взять/снять)   проклятья +%d%% очков"
            % round(SCORE_CURSE_BONUS * 100), True, COL_GOLD)
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
                pygame.draw.rect(self.screen, edge if taken else (60, 70, 110),
                                 box, 3 if taken else 1, border_radius=7)
                if cur:   # курсор — белая рамка снаружи
                    pygame.draw.rect(self.screen, COL_TEXT,
                                     box.inflate(6, 6), 2, border_radius=9)
                color = COL_TEXT if (taken or cur) else COL_DIM
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
        img = get_font(14).render("%s — %s   [%s]"
                                  % (item["name"], item["desc"],
                                     "ВЗЯТО" if taken else "свободно"),
                                  True, edge)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y_bless + 30)))
        rule = ("Проклятья ослабляют ТОЛЬКО ВАС, но +%d%% очков каждое (макс. %d). "
                "Облегчения -%d%% очков: без проклятий — одно, каждое проклятье "
                "открывает ещё. Сейчас x%.2f"
                % (round(SCORE_CURSE_BONUS * 100), MAX_CURSES,
                   round(SCORE_BLESS_PENALTY * 100), mult))
        img = get_font(12, bold=False).render(rule, True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y_bless + 46)))

    def _enemy_panel(self, y):
        """Эффекты НА ВРАГА: баффы и дебаффы боту — любой режет счёт."""
        t = get_font(17).render(
            "НА ВРАГА   (B / N — курсор, M — взять/снять)   любой эффект режет счёт",
            True, (255, 170, 80))
        self.screen.blit(t, t.get_rect(center=(SCREEN_W / 2, y - 28)))
        step = min(180, (SCREEN_W - 140) // len(EE_KEYS))
        box_w, box_h = step - 16, 36
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
            x = SCREEN_W / 2 + (i - (len(EE_KEYS) - 1) / 2) * step
            box = pygame.Rect(0, 0, box_w, box_h)
            box.center = (int(x), y)
            bg = pygame.Rect(box.x - 3, box.y - 3, box.w + 6, box.h + 6)
            pygame.draw.rect(self.screen, (62, 44, 26), bg, border_radius=7)
            if taken:
                pygame.draw.rect(self.screen, (92, 62, 34), box, border_radius=7)
            pygame.draw.rect(self.screen,
                             (255, 170, 80) if taken else (60, 70, 110),
                             box, 3 if taken else 1, border_radius=7)
            if i == self.sel_en:
                pygame.draw.rect(self.screen, COL_TEXT,
                                 box.inflate(6, 6), 2, border_radius=9)
            color = COL_TEXT if (taken or i == self.sel_en) else COL_DIM
            lines = _wrap(item["name"])
            dy = box.centery - (len(lines) * 14) // 2 + 7
            for ln in lines:
                img = name_f.render(ln, True, color)
                self.screen.blit(img, img.get_rect(center=(box.centerx, dy)))
                dy += 14

        item = ENEMY_EFFECTS[EE_KEYS[self.sel_en]]
        taken = EE_KEYS[self.sel_en] in self.sel_enemy_keys
        img = get_font(14).render("%s — %s   [счёт -%d%%]   [%s]"
                                  % (item["name"], item["desc"],
                                     round(item["score_cut"] * 100),
                                     "ВЗЯТО" if taken else "свободно"),
                                  True, (255, 190, 110))
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y + 28)))
        img2 = get_font(12, bold=False).render(
            "Максимум %d эффекта; дебафф -10%% очков, бафф -5%% — и это НЕ "
            "открывает облегчения" % MAX_ENEMY_EFFECTS, True, COL_DIM)
        self.screen.blit(img2, img2.get_rect(center=(SCREEN_W / 2, y + 44)))

    def _choice_panel(self, title, keys, idx, table, y):
        """Компактная панель выбора: заголовок сверху, карточки в ряд."""
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
            pygame.draw.rect(self.screen, COL_P1 if sel else (60, 70, 110), box,
                             3 if sel else 1, border_radius=7)
            dlines = _wrap(item["desc"])
            name_y = box.y + (11 if len(dlines) > 1 else 14)
            img = name_f.render(item["name"], True, COL_TEXT if sel else COL_DIM)
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
        img = get_font(20).render("Esc / Enter — назад", True, COL_P1)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 668)))

    def _draw_match_end(self):
        win = self.score[0] > self.score[1]
        color = COL_P1 if win else COL_P2
        rec = "  НОВЫЙ РЕКОРД!" if self.new_record else ""
        self._banner("ПОБЕДА!" if win else "ПОРАЖЕНИЕ", color,
                     "Счёт %d : %d      Enter — реванш   A — ангар   "
                     "T — таблица   M — меню" % tuple(self.score),
                     sub2="ОЧКИ: %d  (множитель x%.2f)   МЕСТО В ТАБЛИЦЕ: #%d%s"
                          % (self.final_score, self.score_mult,
                             max(1, self.table_place), rec))

    # ----- HUD во время боя -----
    def _hp_bar(self, x, y, tank, right=False):
        w, h = 260, 14
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, (30, 36, 60), rect, border_radius=4)
        k = tank.hp / tank.max_hp
        fill = rect.copy()
        fill.w = max(2, int(w * k))
        if right:
            fill.x = x + w - fill.w
        color = tank.color if k > 0.3 else (255, 90, 90)
        pygame.draw.rect(self.screen, color, fill, border_radius=4)
        pygame.draw.rect(self.screen, (70, 80, 120), rect, 1, border_radius=4)

    def _build_label(self, t, who):
        """«ИГРОК — шасси + корпус + дуло + перк + стихия» с автоподбором
        размера шрифта: длинная сборка не должна налезать на центральный счёт."""
        label = "%s — %s + %s + %s + %s + %s" % (
            who, t.chassis["name"], t.hull["name"], t.weapon["name"],
            t.perk["name"], t.elem["name"])
        size = 22
        while size > 13 and get_font(size).size(label)[0] > 500:
            size -= 1
        return get_font(size).render(label, True, t.color)

    def _draw_hud(self):
        p, b = self.player, self.bot_tank
        # --- игрок (слева) ---
        self.screen.blit(self._build_label(p, "ИГРОК"), (70, 62))
        self._hp_bar(70, 92, p)
        self._mini_info(p, 70, 116,
                        extra=("НА ВРАГА %d" % len(self.build[7]))
                        if self.build[7] else "")
        # --- бот (справа) ---
        img = self._build_label(b, "БОТ")
        self.screen.blit(img, img.get_rect(topright=(SCREEN_W - 70, 62)))
        self._hp_bar(SCREEN_W - 330, 92, b, right=True)
        self._mini_info(b, SCREEN_W - 70, 116, right=True,
                        extra=("ЭФФЕКТЫ ИГРОКА %d" % len(self.build[7]))
                        if self.build[7] else "")
        # --- счёт по центру ---
        img = get_font(44).render("%d : %d" % tuple(self.score), True, COL_TEXT)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 86)))
        img = get_font(17, bold=False).render("до %d побед  ·  карта «%s»"
                                              % (ROUNDS_TO_WIN, self.arena.name),
                                              True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 120)))
        pts = int(self.points * self.score_mult)
        label = "ОЧКИ %d" % pts
        if abs(self.score_mult - 1.0) > 1e-9:
            label += "  ·  жребий x%.2f" % self.score_mult
        img = get_font(15, bold=False).render(label, True, COL_GOLD)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 141)))

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
        # эффекты и бонусы
        sfx = []
        if t.mag_size > 1:
            sfx.append("ОБОЙМА %d/%d" % (t.mag_ammo, t.mag_size))
        if t.armor:
            sfx.append("броня %d" % t.armor)
        if t.element_key != "none":
            sfx.append("стихия: %s" % t.elem["name"])
        if t.mine_carried > 0:
            sfx.append("МИНА x%d (E)" % t.mine_carried)
        if t.barrier_charges > 0:
            sfx.append("СТЕНА x%d (Q)" % t.barrier_charges)
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
            sfx.append("ЭМИ!")
        if t.burn_t > 0:
            sfx.append("ПОЖАР!")
        if t.mud_t > 0:
            sfx.append("УВЯЗ!")
        if t.shock_t > 0:
            sfx.append("ТОК!")
        if t.curses_keys:
            sfx.append("ПРОКЛЯТЬЯ %d" % len(t.curses_keys))
        if t.blessings_keys:
            sfx.append("ОБЛЕГЧЕНИЯ %d" % len(t.blessings_keys))
        if extra:
            sfx.append(extra)
        row_y = y + 32
        if sfx:
            img = get_font(16, bold=False).render("   ".join(sfx), True, (160, 200, 255))
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

    # ================= главный цикл =================
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    return
                self.on_keydown(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()
