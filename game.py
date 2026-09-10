# -*- coding: utf-8 -*-
"""Игровая логика: меню, выбор танка, раунды, счёт, HUD."""
import random
import pygame
from settings import (SCREEN_W, SCREEN_H, FPS, TITLE, COL_TEXT, COL_DIM,
                      COL_P1, COL_P2, COL_GOLD, ROUNDS_TO_WIN, ROUND_BANNER_T,
                      ROUND_PAUSE_T, CHASSIS, HULL, POWERUP_INTERVAL,
                      POWERUP_MAX)
from arena import Arena
from tank import Tank
from bot import BotAI, random_build
from powerup import PowerUp, PU_INFO
from effects import Effects, get_font
from sound import SoundBank

CH_KEYS = list(CHASSIS)
HU_KEYS = list(HULL)


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

        # объекты боя
        self.player = None
        self.bot_tank = None
        self.ai = None
        self.bullets = []
        self.powerups = []
        self.powerup_t = POWERUP_INTERVAL * 0.6

        self._fake_keys = None  # только для автотестов

    # ================= создание боя =================
    def _reset_round(self):
        cx, cy = SCREEN_W / 2, SCREEN_H / 2
        self.player = Tank(cx - 400, cy, 0, self.build[0], self.build[1], COL_P1)
        self.bot_tank = Tank(cx + 400, cy, 180, self.bot_build[0], self.bot_build[1], COL_P2)
        self.ai = BotAI(self.bot_tank)
        self.bullets = []
        self.powerups = []
        self.powerup_t = POWERUP_INTERVAL * 0.6
        self.effects.particles.clear()
        self.effects.texts.clear()

    def start_match(self):
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
            elif k == pygame.K_m:
                self.state = "menu"
        elif self.state == "match_end":
            if k == pygame.K_RETURN:
                self.start_match()
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
            self.player.try_shoot(self.bullets, self.effects, self.sounds)

        for b in self.bullets:
            b.update(dt, self.arena, (self.player, self.bot_tank),
                     self.effects, self.sounds)
        self.bullets = [b for b in self.bullets if not b.dead]

        self._powerups_step(dt)

        if not self.player.alive or not self.bot_tank.alive:
            self.winner = 0 if self.bot_tank.alive else 1
            self.score[self.winner] += 1
            self.state = "round_end"
            self.timer = ROUND_PAUSE_T
            self.sounds.play("round")

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
                    t.apply_powerup(pu.kind)
                    info = PU_INFO[pu.kind]
                    self.effects.float_text(t.x, t.y - 54, info["name"], info["color"])
                    self.sounds.play("pickup")
                    self.powerups.remove(pu)
                    break

    # ================= отрисовка =================
    def draw(self):
        ox, oy = self.effects.offset()
        self.world.fill((0, 0, 0))
        self.arena.draw(self.world, ox, oy)

        in_battle = self.state in ("intro", "fight", "round_end", "pause", "match_end")
        if in_battle:
            for pu in self.powerups:
                pu.draw(self.world, ox, oy)
            for b in self.bullets:
                b.draw(self.world, ox, oy)
            if self.bot_tank.alive:
                self.bot_tank.draw(self.world, ox, oy)
            if self.player.alive:
                self.player.draw(self.world, ox, oy)
            self.effects.draw(self.world, ox, oy)
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
                txt = "РАУНД ЗА ИГРОКОМ" if self.winner == 0 else "РАУНД ЗА БОТОМ"
                self._banner(txt, COL_P1 if self.winner == 0 else COL_P2)
            elif self.state == "match_end":
                self._draw_match_end()
            elif self.state == "pause":
                self._banner("ПАУЗА", COL_TEXT, "Esc — продолжить, M — меню")

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
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 190)))
        sub = get_font(30, bold=False).render("танковая дуэль", True, COL_GOLD)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W / 2, 275)))
        lines = [
            "W/S — вперёд и назад      A/D — поворот      Пробел — выстрел",
            "Перед боем соберите танк: шасси даёт скорость, корпус — броню.",
            "Но помните: если нагрузить всё тяжёлое — будете ползти как сарай.",
            "",
            "Enter — начать",
        ]
        y = 380
        for s in lines:
            img = get_font(24, bold=False).render(s, True, COL_DIM)
            self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, y)))
            y += 40
        hint = get_font(26).render("Enter — в ангар", True, COL_P1)
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_W / 2, y + 30)))

    def _draw_select(self):
        get_font(44)
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
            pygame.draw.rect(self.screen, COL_P1 if sel else (60, 70, 110), box, 3 if sel else 1,
                             border_radius=8)
            img = get_font(28).render(item["name"], True, COL_TEXT if sel else COL_DIM)
            self.screen.blit(img, img.get_rect(center=(box.centerx, box.y + 24)))
            img2 = get_font(18, bold=False).render(item["desc"], True, COL_DIM)
            self.screen.blit(img2, img2.get_rect(center=(box.centerx, box.y + 56)))

    def _draw_match_end(self):
        win = self.score[0] > self.score[1]
        color = COL_P1 if win else COL_P2
        self._banner("ПОБЕДА!" if win else "ПОРАЖЕНИЕ", color,
                     "Счёт %d : %d      Enter — реванш, M — меню" % tuple(self.score))

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
        img = get_font(24).render("ИГРОК — %s + %s" % (p.chassis["name"], p.hull["name"]), True, COL_P1)
        self.screen.blit(img, (70, 66))
        self._hp_bar(70, 98, p)
        self._mini_info(p, 70, 122)
        # --- бот (справа) ---
        img = get_font(24).render("БОТ — %s + %s" % (b.chassis["name"], b.hull["name"]), True, COL_P2)
        self.screen.blit(img, img.get_rect(topright=(SCREEN_W - 70, 66)))
        self._hp_bar(SCREEN_W - 330, 98, b, right=True)
        self._mini_info(b, SCREEN_W - 70, 122, right=True)
        # --- счёт по центру ---
        img = get_font(46).render("%d : %d" % tuple(self.score), True, COL_TEXT)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 92)))
        img = get_font(20, bold=False).render("до %d побед" % ROUNDS_TO_WIN, True, COL_DIM)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W / 2, 126)))

    def _mini_info(self, t, x, y, right=False):
        # перезарядка
        k = 1 - t.cooldown / t.reload_time
        bar = pygame.Rect(0, 0, 120, 6)
        if right:
            bar.x, bar.y = x - 120, y
        else:
            bar.x, bar.y = x, y
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
        # броня и бонусы
        sfx = []
        if t.armor:
            sfx.append("броня %d" % t.armor)
        if t.shield_t > 0:
            sfx.append("ЩИТ %.0f" % t.shield_t)
        if t.triple > 0:
            sfx.append("ВЕЕР x%d" % t.triple)
        if t.boost_t > 0:
            sfx.append("ТУРБО %.0f" % t.boost_t)
        if sfx:
            img = get_font(16, bold=False).render("   ".join(sfx), True, (160, 200, 255))
            if right:
                self.screen.blit(img, img.get_rect(topright=(x, y + 32)))
            else:
                self.screen.blit(img, (x, y + 32))

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
