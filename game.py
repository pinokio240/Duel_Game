# -*- coding: utf-8 -*-
"""Игровая логика: меню, ангар, раунды, бонусы, мины/дым/лазер, HUD."""
import math
import json
import os
import random
import pygame
from settings import (SCREEN_W, SCREEN_H, FPS, TITLE, COL_TEXT, COL_DIM,
                      COL_P1, COL_P2, COL_GOLD, ROUNDS_TO_WIN, ROUND_BANNER_T,
                      ROUND_PAUSE_T, CHASSIS, HULL, POWERUP_INTERVAL,
                      POWERUP_MAX, PU_MINE_DAMAGE, PU_MINE_RADIUS, PU_MINE_MAX,
                      PU_MINE_LIFE, PU_LASER_DAMAGE, PU_SMOKE_TIME,
                      PU_SMOKE_RADIUS, PU_FREEZE_TIME, DIFF_PRESETS,
                      BOT_DIFFICULTY)
from arena import Arena, LAYOUTS
from tank import Tank
from bot import BotAI, random_build
from powerup import PowerUp, Mine, PU_INFO
from effects import Effects, get_font
from sound import SoundBank

CH_KEYS = list(CHASSIS)
HU_KEYS = list(HULL)
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
        self.state = "menu"       # menu/select/intro/fight/round_end/match_end/pause
        self.timer = 0.0
        self.build = ("medium", "medium")   # сборка игрока
        self.bot_build = ("medium", "medium")
        self.sel_ch, self.sel_hu = 1, 1     # курсоры в меню выбора
        self.score = [0, 0]
        self.round = 1
        self.winner = 0
        self.difficulty = BOT_DIFFICULTY

        # объекты боя
        self.player = None
        self.bot_tank = None
        self.ai = None
        self.bullets = []
        self.powerups = []
        self.mines = []
        self.smokes = []
        self.powerup_t = POWERUP_INTERVAL * 0.6

        self._fake_keys = None  # только для автотестов
        self.stats = self._load_stats()

    # ================= статистика матчей =================
    def _load_stats(self):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            return {"wins": int(d.get("wins", 0)),
                    "losses": int(d.get("losses", 0)),
                    "draws": int(d.get("draws", 0))}
        except Exception:
            return {"wins": 0, "losses": 0, "draws": 0}

    def _save_stats(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f)
        except Exception:
            pass

    # ================= создание боя =================
    def _reset_round(self):
        cx, cy = SCREEN_W / 2, SCREEN_H / 2
        self.player = Tank(cx - 400, cy, 0, self.build[0], self.build[1], COL_P1)
        self.bot_tank = Tank(cx + 400, cy, 180, self.bot_build[0], self.bot_build[1], COL_P2)
        self.ai = BotAI(self.bot_tank, self.difficulty)
        self.bullets = []
        self.powerups = []
        self.mines = []
        self.smokes = []
        self.powerup_t = POWERUP_INTERVAL * 0.6
        self.effects.particles.clear()
        self.effects.texts.clear()

    def start_match(self):
        self.arena = Arena(random.randrange(len(LAYOUTS)))  # случайная арена на матч
        self.bot_build = random_build()
        self.score = [0, 0]
        self.round = 1
        self._reset_round()
        self.state = "intro"
        self.timer = ROUND_BANNER_T
        self.sounds.play("round")

    # ================= ввод (клавиатура по событиям) =================
    def on_keydown(self, e):
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if self.state == "menu":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "select"
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
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self.build = (CH_KEYS[self.sel_ch], HU_KEYS[self.sel_hu])
                self.start_match()
            elif k == pygame.K_ESCAPE:
                self.state = "menu"
        elif self.state == "fight":
            if k == pygame.K_ESCAPE:
                self.state = "pause"
        elif self.state == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.state = "fight"
            elif k == pygame.K_a:
                self.state = "select"   # выход в ангар
            elif k == pygame.K_m:
                self.state = "menu"
        elif self.state == "match_end":
            if k == pygame.K_RETURN:
                self.start_match()
            elif k == pygame.K_a:
                self.state = "select"   # в ангар за новой сборкой
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
                    elif self.score[1] > self.score[0]:
                        self.stats["losses"] += 1
                    else:
                        self.stats["draws"] += 1
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

        self.player.update(dt)
        self.bot_tank.update(dt)
        self.player.control(dt, self.arena, fwd, tn, (self.bot_tank,))
        self.ai.update(dt, self)
        if keys[pygame.K_SPACE]:
            self.fire_weapon(self.player)

        for b in self.bullets:
            b.update(dt, self.arena, (self.player, self.bot_tank),
                     self.effects, self.sounds)
        self.bullets = [b for b in self.bullets if not b.dead]

        self._mines_step(dt)
        self._smokes_step(dt)
        self._powerups_step(dt)

        if not self.player.alive or not self.bot_tank.alive:
            if self.player.alive:
                self.winner = 0   # выжил игрок
            elif self.bot_tank.alive:
                self.winner = 1   # выжил бот
            else:
                self.winner = -1  # оба подорвались — ничья, очко никому
            if self.winner >= 0:
                self.score[self.winner] += 1
            self.state = "round_end"
            self.timer = ROUND_PAUSE_T
            self.sounds.play("round")

    # ================= оружие (снаряды и лазер) =================
    def fire_weapon(self, t):
        """Единая точка стрельбы: если есть заряды лазера — луч, иначе снаряд."""
        if not t.alive or t.frozen_t > 0 or t.cooldown > 0:
            return
        if t.laser_charges > 0:
            t.laser_charges -= 1
            self.fire_laser(t)
            t.cooldown = t.reload_time
        else:
            t.try_shoot(self.bullets, self.effects, self.sounds)

    def fire_laser(self, shooter):
        """Мгновенный луч: пробивает всё до первой стены, поджигает первого врага."""
        rad = math.radians(shooter.angle)
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
            hit.take_damage(PU_LASER_DAMAGE, self.effects, self.sounds)
        self.sounds.play("laser")

    # ================= зрение (стены + дым) =================
    def vision_blocked(self, x1, y1, x2, y2):
        if self.arena.line_blocked(x1, y1, x2, y2):
            return True
        for s in self.smokes:
            if s.life > 0 and _seg_circle(x1, y1, x2, y2, s.x, s.y, s.radius):
                return True
        return False

    # ================= мины и дым =================
    def _place_mine(self, t):
        rad = math.radians(t.angle)
        mx, my = t.x, t.y
        for d in (46, 30, 16, 0):
            mx = t.x - math.cos(rad) * d
            my = t.y - math.sin(rad) * d
            if not self.arena.point_blocked(mx, my):
                break
        own = [m for m in self.mines if m.owner is t]
        if len(own) >= PU_MINE_MAX:
            self.mines.remove(own[0])
        self.mines.append(Mine(mx, my, t))
        self.sounds.play("mine")

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
        if pu.kind == "mine":
            self._place_mine(t)
        elif pu.kind == "smoke":
            self.smokes.append(Smoke(t.x, t.y))
            self.sounds.play("smoke")
        elif pu.kind == "freeze":
            enemy = self.bot_tank if t is self.player else self.player
            if enemy.alive:
                enemy.frozen_t = PU_FREEZE_TIME
                self.effects.float_text(enemy.x, enemy.y - 54, "ЭМИ!", info["color"])
            self.sounds.play("freeze")
        else:
            t.apply_powerup(pu.kind)
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
        elif in_battle:
            self._draw_hud()
            if self.state == "intro":
                self._banner("РАУНД %d" % self.round, COL_GOLD)
            elif self.state == "round_end":
                if self.winner == 0:
                    self._banner("РАУНД ЗА ИГРОКОМ", COL_P1)
                elif self.winner == 1:
                    self._banner("РАУНД ЗА БОТОМ", COL_P2)
                else:
                    self._banner("НИЧЬЯ", COL_TEXT)
            elif self.state == "match_end":
                self._draw_match_end()
            elif self.state == "pause":
                self._banner("ПАУЗА", COL_TEXT,
                             "Esc — продолжить   A — ангар   M — меню")

    def _banner(self, text, color, sub=""):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((5, 6, 14, 150))
        self.screen.blit(dim, (0, 0))
        img = get_font(72).render(text, True, color)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 - 20)))
        if sub:
            img2 = get_font(26, bold=False).render(sub, True, COL_DIM)
            self.screen.blit(img2, img2.get_rect(center=(SCREEN_W / 2, SCREEN_H / 2 + 40)))

    def _draw_menu(self):
        img = get_font(110).render("DUEL", True, COL_TEXT)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 170)))
        sub = get_font(30, bold=False).render("танковая дуэль", True, COL_GOLD)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W / 2, 255)))
        lines = [
            "W/S — вперёд и назад      A/D — поворот      Пробел — выстрел",
            "Перед боем соберите танк: шасси даёт скорость, корпус — броню.",
            "9 видов бонусов на арене: мины, лазер, дым, ЭМИ и другие.",
            "Но помните: если нагрузить всё тяжёлое — будете ползти как сарай.",
        ]
        y = 340
        for s in lines:
            img = get_font(24, bold=False).render(s, True, COL_DIM)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y)))
            y += 40
        # выбор сложности
        y += 10
        img = get_font(22, bold=False).render("Сложность бота (1/2/3):", True, COL_DIM)
        self.screen.blit(img, img.get_rect(midright=(SCREEN_W / 2 - 120, y)))
        for i, dkey in enumerate((1, 2, 3)):
            color = COL_GOLD if self.difficulty == dkey else (70, 80, 120)
            img = get_font(22).render("%d %s" % (dkey, DIFF_NAMES[dkey]), True, color)
            self.screen.blit(img, (SCREEN_W / 2 - 100 + i * 135, y - img.get_height() / 2))
        # статистика матчей
        y += 52
        st = "Побед: %d   Поражений: %d   Ничьих: %d" % (
            self.stats["wins"], self.stats["losses"], self.stats["draws"])
        img = get_font(20, bold=False).render(st, True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y)))
        # призыв
        img = get_font(28).render("Enter — в ангар", True, COL_P1)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y + 56)))
        # версия
        img = get_font(16, bold=False).render("v1.1", True, (60, 66, 95))
        self.screen.blit(img, (SCREEN_W - 60, SCREEN_H - 34))

    def _draw_select(self):
        t1 = get_font(44).render("АНГАР", True, COL_TEXT)
        self.screen.blit(t1, t1.get_rect(center=(SCREEN_W / 2, 70)))

        ch = CHASSIS[CH_KEYS[self.sel_ch]]
        hu = HULL[HU_KEYS[self.sel_hu]]
        speed = ch["speed"] * (1 - hu["weight"])

        # --- панели выбора ---
        self._choice_panel("ШАССИ   (A / D)", CH_KEYS, self.sel_ch, CHASSIS, 170)
        self._choice_panel("КОРПУС   (W / S)", HU_KEYS, self.sel_hu, HULL, 400)

        # --- итоговые характеристики ---
        x, y = SCREEN_W / 2, 560
        rows = [
            "Скорость: %.0f px/с    Прочность: %d    Броня: %d    Перезарядка: %.2f с"
            % (speed, hu["hp"], ch["armor"], hu["reload"]),
        ]
        if speed < 110:
            rows.append("ВНИМАНИЕ: с такой сборкой вы будете ОЧЕНЬ медленными!")
        rows.append("Enter — в бой      Esc — назад")
        for i, s in enumerate(rows):
            color = (255, 120, 90) if i == 1 else (COL_TEXT if i != len(rows) - 1 else COL_P1)
            img = get_font(26 if i != 1 else 24).render(s, True, color)
            self.screen.blit(img, img.get_rect(center=(x, y + i * 40)))

        # превью танка игрока
        preview = Tank(0, 0, 0, CH_KEYS[self.sel_ch], HU_KEYS[self.sel_hu], COL_P1)
        img = pygame.transform.scale2x(preview._sprite)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 318)))

    def _choice_panel(self, title, keys, idx, table, y):
        t = get_font(28).render(title, True, COL_GOLD)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W / 2, y - 38)))
        n = len(keys)
        for i, key in enumerate(keys):
            item = table[key]
            x = SCREEN_W / 2 + (i - (n - 1) / 2) * 330
            sel = (i == idx)
            box = pygame.Rect(0, 0, 300, 84)
            box.center = (int(x), y)
            bg = pygame.Rect(box.x - 6, box.y - 6, box.w + 12, box.h + 12)
            pygame.draw.rect(self.screen, (30, 40, 75), bg, border_radius=10)
            pygame.draw.rect(self.screen, COL_P1 if sel else (60, 70, 110), box,
                             3 if sel else 1, border_radius=8)
            img = get_font(28).render(item["name"], True, COL_TEXT if sel else COL_DIM)
            self.screen.blit(img, img.get_rect(center=(box.centerx, box.y + 24)))
            img2 = get_font(18, bold=False).render(item["desc"], True, COL_DIM)
            self.screen.blit(img2, img2.get_rect(center=(box.centerx, box.y + 56)))

    def _draw_match_end(self):
        win = self.score[0] > self.score[1]
        color = COL_P1 if win else COL_P2
        self._banner("ПОБЕДА!" if win else "ПОРАЖЕНИЕ", color,
                     "Счёт %d : %d      Enter — реванш   A — ангар   M — меню" % tuple(self.score))

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

    def _draw_hud(self):
        p, b = self.player, self.bot_tank
        # --- игрок (слева) ---
        img = get_font(24).render("ИГРОК — %s + %s" % (p.chassis["name"], p.hull["name"]),
                                  True, COL_P1)
        self.screen.blit(img, (70, 62))
        self._hp_bar(70, 94, p)
        self._mini_info(p, 70, 118)
        # --- бот (справа) ---
        img = get_font(24).render("БОТ — %s + %s" % (b.chassis["name"], b.hull["name"]),
                                  True, COL_P2)
        self.screen.blit(img, img.get_rect(topright=(SCREEN_W - 70, 62)))
        self._hp_bar(SCREEN_W - 330, 94, b, right=True)
        self._mini_info(b, SCREEN_W - 70, 118, right=True)
        # --- счёт по центру ---
        img = get_font(46).render("%d : %d" % tuple(self.score), True, COL_TEXT)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 90)))
        img = get_font(20, bold=False).render("до %d побед" % ROUNDS_TO_WIN, True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 124)))

    def _mini_info(self, t, x, y, right=False):
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
        if t.armor:
            sfx.append("броня %d" % t.armor)
        if t.shield_t > 0:
            sfx.append("ЩИТ %.0f" % t.shield_t)
        if t.triple > 0:
            sfx.append("ВЕЕР x%d" % t.triple)
        if t.boost_t > 0:
            sfx.append("ТУРБО %.0f" % t.boost_t)
        if t.rapid_t > 0:
            sfx.append("СКОРОСТРЕЛ %.0f" % t.rapid_t)
        if t.laser_charges > 0:
            sfx.append("ЛАЗЕР x%d" % t.laser_charges)
        if t.frozen_t > 0:
            sfx.append("ЭМИ!")
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
