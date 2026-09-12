# -*- coding: utf-8 -*-
"""
Танк: «танковое» управление, стрельба, броня, бонусы.
Скорость считается честно: скорость шасси * (1 - вес корпуса)
* множитель дула * множитель перка. Хотели имбу? Их нет.
"""
import math
import random
import pygame
from settings import (CHASSIS, HULL, WEAPONS, PERKS, ELEMENTS, CURSES, BLESSINGS,
                      TANK_RADIUS, BULLET_DAMAGE,
                      PU_SHIELD_TIME, PU_BOOST_TIME, PU_TRIPLE_SHOTS, PU_REPAIR_HP,
                      PU_RAPID_TIME, PU_RAPID_MULT,
                      BOOST_MULT, BOOST_PERK_KEY, BOOST_PERK_MULT,
                      FIRE_TIME, FIRE_DPS,
                      EARTH_TIME, EARTH_MULT, SHOCK_TIME, SHOCK_MULT,
                      AIR_PUSH, WATER_CLEAR_DMG, WATER_SLOW_TIME,
                      PU_MINE_CARRY, BARRIER_MAX)
from bullet import Bullet, ELEMENT_COLORS


class Tank:
    def __init__(self, x, y, angle, chassis_key, hull_key, color,
                 weapon_key="standard", perk_key="none", element_key="none",
                 curses=(), blessings=(), extra_mods=None):
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)  # градусы, 0 = вправо, по часовой
        self.ch_key, self.hull_key = chassis_key, hull_key
        self.wpn_key, self.perk_key = weapon_key, perk_key
        self.element_key = element_key      # шестая часть сборки — стихия
        self.chassis = CHASSIS[chassis_key]
        self.hull = HULL[hull_key]
        self.weapon = WEAPONS[weapon_key]
        self.perk = PERKS[perk_key]
        self.elem = ELEMENTS[element_key]
        # жребий: проклятья и облегчения (только у игрока, берутся в ангаре)
        self.curses_keys = tuple(curses)
        self.blessings_keys = tuple(blessings)
        self.mods = {"hp_mult": 1.0, "speed_mult": 1.0, "reload_mult": 1.0,
                     "spread_deg": 0.0, "bullet_speed_mult": 1.0,
                     "turn_mult": 1.0, "boost_mult": 1.0, "damage_mult": 1.0}
        for _table, _keys in ((CURSES, self.curses_keys),
                              (BLESSINGS, self.blessings_keys)):
            for _key in _keys:
                for _f, _v in _table[_key]["mods"].items():
                    if _f == "spread_deg":
                        self.mods[_f] += _v
                    else:
                        self.mods[_f] *= _v
        # эффекты НА ВРАГА: готовый словарь модов (баффы/дебаффы боту)
        if extra_mods:
            for _f, _v in extra_mods.items():
                if _f == "spread_deg":
                    self.mods[_f] += _v
                else:
                    self.mods[_f] *= _v
        self.color = color
        self.light = tuple(min(c + 100, 255) for c in color)
        self.radius = TANK_RADIUS
        self.max_hp = max(20, int(round(self.hull["hp"] * self.perk["hp_mult"]
                                        * self.mods["hp_mult"])))
        self.hp = self.max_hp
        self.armor = self.chassis["armor"]  # сглаживание урона
        self.cooldown = 0.0
        self.alive = True
        self.flash = 0.0          # белая вспышка при получении урона
        self._stuck = 0.0         # бот: застрял ли у стены
        # обойма (для спарки): сколько снарядов осталось до полной перезарядки
        self.mag_size = self.weapon["mag"]
        self.mag_ammo = self.mag_size
        # активные бонусы
        self.shield_t = 0.0
        self.boost_t = 0.0
        self.triple = 0
        self.rapid_t = 0.0        # скорострел
        self.frozen_t = 0.0       # ЭМИ-заморозка
        self.laser_charges = 0    # заряды лазера
        # негативные эффекты от стихий врага (свою стихию мы зарядили в ангаре)
        self.burn_t = 0.0         # поджог: тикает уроном, броня не спасает
        self._burn_tick = 0.0
        self.mud_t = 0.0          # земля: вязнет
        self.shock_t = 0.0        # ток: мотор вполсилы
        # ручные бустеры: мины и стены-барьеры носятся в боекомплекте
        self.mine_carried = 0
        self.barrier_charges = 0
        self._sprite = self._make_sprite()

    # ----- характеристики с учётом бонусов, дула и перка -----
    @property
    def speed(self):
        if self.frozen_t > 0:
            return 0.0
        s = self.chassis["speed"] * (1.0 - self.hull["weight"]
                                     * self.chassis.get("wmult", 1.0))
        s *= self.weapon["move_mult"] * self.perk["speed_mult"]
        s *= self.mods["speed_mult"]        # жребий: форсаж или ржавые гусеницы
        if self.mud_t > 0:
            s *= EARTH_MULT     # увяз в земле
        if self.shock_t > 0:
            s *= SHOCK_MULT     # ток: мотор вполсилы
        if self.boost_t > 0:
            # правило турбо: с перком «Гонец» ускорение слабее,
            # без перка — турбо работает как обычно; жребий может
            # ослабить (Текущий бак) или усилить (Гоночный бак) турбо
            s *= (BOOST_PERK_MULT if self.perk_key == BOOST_PERK_KEY
                  else BOOST_MULT) * self.mods["boost_mult"]
        return s

    @property
    def turn_speed(self):
        t = (self.chassis["turn"] * self.perk["turn_mult"]
             * self.mods["turn_mult"])   # градусов/сек; жребий: Юркость и др.
        if self.shock_t > 0:
            t *= SHOCK_MULT
        return t

    @property
    def reload_time(self):
        r = (self.hull["reload"] * self.weapon["reload_mult"]
             * self.perk["reload_mult"] * self.mods["reload_mult"])
        if self.rapid_t > 0:
            r *= PU_RAPID_MULT
        return r

    # ----- неоновый спрайт (рисуется один раз, вращается каждый кадр) -----
    def _make_sprite(self):
        s = pygame.Surface((64, 50), pygame.SRCALPHA)
        glow = pygame.Surface((64, 50), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*self.color, 55), (6, 2, 48, 46), border_radius=10)
        pygame.draw.rect(glow, (*self.color, 90), (10, 6, 40, 38), border_radius=8)
        s.blit(glow, (0, 0))
        # гусеницы
        pygame.draw.rect(s, (52, 58, 84), (10, 2, 38, 10), border_radius=3)
        pygame.draw.rect(s, (52, 58, 84), (10, 38, 38, 10), border_radius=3)
        for i in range(4):
            pygame.draw.line(s, (30, 34, 52), (14 + i * 9, 3), (14 + i * 9, 11), 2)
            pygame.draw.line(s, (30, 34, 52), (14 + i * 9, 39), (14 + i * 9, 47), 2)
        # корпус
        pygame.draw.rect(s, self.color, (14, 10, 32, 30), border_radius=6)
        pygame.draw.rect(s, self.light, (18, 14, 24, 22), 2, border_radius=5)
        # ствол(ы) — вид зависит от выбранного дула (смотрят вправо)
        if self.wpn_key == "twin":
            # спарка: два тонких ствола друг над другом
            pygame.draw.rect(s, self.light, (42, 18, 20, 5), border_radius=2)
            pygame.draw.rect(s, self.light, (42, 27, 20, 5), border_radius=2)
            pygame.draw.rect(s, self.color, (39, 16, 7, 18), border_radius=2)
        elif self.wpn_key == "long":
            # дальняя: длинный толстый ствол с раструбом
            pygame.draw.rect(s, self.light, (44, 22, 26, 7), border_radius=2)
            pygame.draw.rect(s, self.light, (66, 21, 5, 9), border_radius=1)
            pygame.draw.rect(s, self.color, (41, 19, 7, 13), border_radius=2)
        else:
            pygame.draw.rect(s, self.light, (44, 22, 19, 7), border_radius=2)
            pygame.draw.rect(s, self.color, (41, 19, 7, 13), border_radius=2)
        # стихия: цветной ореол на срезе ствола — видно, чем стреляем
        if self.element_key != "none":
            col = ELEMENT_COLORS[self.element_key]
            pygame.draw.circle(s, col, (62, 25), 3)
            pygame.draw.circle(s, col, (62, 25), 6, 1)
        return s

    # ----- движение -----
    def control(self, dt, arena, forward=0, turn=0, tanks=()):
        """forward: 1 вперёд / -1 назад; turn: 1 по часовой / -1 против."""
        if not self.alive or self.frozen_t > 0:
            return
        self.angle = (self.angle + turn * self.turn_speed * dt) % 360
        ox, oy = self.x, self.y
        if forward:
            step = self.speed * dt * forward
            nx = self.x + math.cos(math.radians(self.angle)) * step
            ny = self.y + math.sin(math.radians(self.angle)) * step
            # раздельная проверка осей — танк «скользит» вдоль стен
            if not arena.circle_collides(nx, self.y, self.radius):
                self.x = nx
            if not arena.circle_collides(self.x, ny, self.radius):
                self.y = ny
        # застревание (использует бот, чтобы отъезжать от стен)
        moved = math.hypot(self.x - ox, self.y - oy)
        if forward == 1 and moved < self.speed * dt * 0.35:
            self._stuck += dt
        else:
            self._stuck = 0.0
        # расталкивание танков
        for o in tanks:
            if o is self or not o.alive or not self.alive:
                continue
            dx, dy = self.x - o.x, self.y - o.y
            d = math.hypot(dx, dy)
            min_d = self.radius + o.radius
            if 0 < d < min_d:
                push = (min_d - d) / 2
                px, py = dx / d * push, dy / d * push
                if not arena.circle_collides(self.x + px, self.y + py, self.radius):
                    self.x += px
                    self.y += py
                if not arena.circle_collides(o.x - px, o.y - py, o.radius):
                    o.x -= px
                    o.y -= py

    # ----- стрельба -----
    def try_shoot(self, bullets, effects, sounds):
        if not self.alive or self.cooldown > 0 or self.frozen_t > 0:
            return
        rad = math.radians(self.angle)
        mx = self.x + math.cos(rad) * (self.radius + 14)
        my = self.y + math.sin(rad) * (self.radius + 14)
        angles = [self.angle]
        if self.triple > 0:
            angles = [self.angle - 12, self.angle, self.angle + 12]
            self.triple -= 1
        # стихия из ангара заряжает КАЖДЫЙ снаряд: цена — часть урона
        dmg = (BULLET_DAMAGE * self.weapon["damage_mult"]
               * self.elem["damage_mult"] * self.mods["damage_mult"])
        spd = (self.weapon["speed_mult"] * self.elem["speed_mult"]
               * self.mods["bullet_speed_mult"])
        elem = self.element_key if self.element_key != "none" else None
        # «Разбитый прицел» разбрасывает снаряды, «Твёрдые руки» лечат прицел
        sp = max(0.0, self.mods["spread_deg"])
        for a in angles:
            if sp > 0:
                a = a + random.uniform(-sp, sp)
            bullets.append(Bullet(mx, my, a, self, damage=dmg, speed_mult=spd,
                                  element=elem))
        # обойма: пока есть второй снаряд — короткая пауза, потом полная перезарядка
        if self.mag_ammo > 1:
            self.mag_ammo -= 1
            self.cooldown = self.weapon["mag_cd"] * (PU_RAPID_MULT if self.rapid_t > 0 else 1.0)
        else:
            self.mag_ammo = self.mag_size
            self.cooldown = self.reload_time
        effects.burst(mx, my, self.light, 5, 130, 0.18, 3)
        sounds.play("shoot")

    # ----- урон и бонусы -----
    def _die(self, effects, sounds):
        self.hp = 0
        self.alive = False
        effects.burst(self.x, self.y, self.color, 42, 430, 0.9, 6)
        effects.burst(self.x, self.y, (255, 255, 255), 16, 260, 0.6, 4)
        effects.ring(self.x, self.y, self.color, 100, 0.5)
        effects.shake(9, 0.4)
        sounds.play("explode")

    def take_damage(self, dmg, effects, sounds):
        if not self.alive:
            return
        if self.shield_t > 0:
            dmg *= 0.4
        dmg = max(5, round(dmg - self.armor))
        self.hp -= dmg
        self.flash = 0.12
        effects.float_text(self.x, self.y - 36, "-%d" % dmg, (255, 130, 130))
        if self.hp <= 0:
            self._die(effects, sounds)
        else:
            effects.burst(self.x, self.y, self.color, 6, 160, 0.3, 3)
            sounds.play("hit")

    # ----- эффекты стихий (получатель — этот танк) -----
    def apply_element(self, elem, vx, vy, arena, effects, sounds):
        """В нас попал элементальный снаряд. vx/vy — направление полёта."""
        if elem == "fire":
            self.burn_t = FIRE_TIME
            self._burn_tick = 0.0
            effects.float_text(self.x, self.y - 50, "ПОЖАР!", (255, 110, 0))
        elif elem == "earth":
            self.mud_t = EARTH_TIME
            effects.float_text(self.x, self.y - 50, "УВЯЗ!", (180, 130, 60))
        elif elem == "electric":
            self.shock_t = SHOCK_TIME
            effects.float_text(self.x, self.y - 50, "ТОК!", (255, 240, 110))
        elif elem == "water":
            washed = []
            if self.shield_t > 0: washed.append("щит")
            if self.boost_t > 0: washed.append("турбо")
            if self.rapid_t > 0: washed.append("скорострел")
            if self.triple > 0: washed.append("веер")
            if self.laser_charges > 0: washed.append("лазер")
            self.shield_t = self.boost_t = self.rapid_t = 0.0
            self.triple = 0
            self.laser_charges = 0
            self.take_damage(WATER_CLEAR_DMG, effects, sounds)
            self.mud_t = max(self.mud_t, WATER_SLOW_TIME)   # мокрый — буксует
            msg = "СМЫТО: " + ", ".join(washed) if washed else "СМЫТО"
            effects.float_text(self.x, self.y - 50, msg, (80, 170, 255))
        elif elem == "air":
            sp = math.hypot(vx, vy) + 1e-6
            dx, dy = vx / sp * AIR_PUSH, vy / sp * AIR_PUSH
            step = 8.0
            n = int(AIR_PUSH / step)
            for _ in range(n):
                nx, ny = self.x + dx / n, self.y + dy / n
                if arena.circle_collides(nx, ny, self.radius):
                    break
                self.x, self.y = nx, ny
            effects.float_text(self.x, self.y - 50, "ПОРЫВ!", (190, 235, 255))

    def _burn_step(self, dt, effects, sounds):
        """Поджог: тикает уроном, броня не спасает."""
        if self.burn_t <= 0 or not self.alive:
            return
        self.burn_t -= dt
        self._burn_tick -= dt
        if self._burn_tick <= 0:
            self._burn_tick = 0.5
            self.hp -= FIRE_DPS * 0.5
            effects.burst(self.x, self.y, (255, 110, 0), 3, 90, 0.3, 2)
            if self.hp <= 0:
                self._die(effects, sounds)

    def apply_powerup(self, kind):
        if kind == "shield":
            self.shield_t = PU_SHIELD_TIME
        elif kind == "boost":
            self.boost_t = PU_BOOST_TIME
        elif kind == "triple":
            self.triple = PU_TRIPLE_SHOTS
        elif kind == "repair":
            self.hp = min(self.max_hp, self.hp + PU_REPAIR_HP)
        elif kind == "rapid":
            self.rapid_t = PU_RAPID_TIME
        elif kind == "laser":
            self.laser_charges += 2
        elif kind == "mine":
            # мина больше не ставится сама — носим в боекомплекте (клавиша E)
            self.mine_carried = min(self.mine_carried + 1, PU_MINE_CARRY)
        elif kind == "barrier":
            self.barrier_charges = min(self.barrier_charges + 1, BARRIER_MAX)

    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.flash = max(0.0, self.flash - dt)
        self.shield_t = max(0.0, self.shield_t - dt)
        self.boost_t = max(0.0, self.boost_t - dt)
        self.rapid_t = max(0.0, self.rapid_t - dt)
        self.frozen_t = max(0.0, self.frozen_t - dt)
        self.mud_t = max(0.0, self.mud_t - dt)
        self.shock_t = max(0.0, self.shock_t - dt)
        self.burn_t = max(0.0, self.burn_t - dt)

    # ----- отрисовка -----
    def draw(self, surf, ox=0, oy=0):
        img = pygame.transform.rotate(self._sprite, -self.angle)
        rect = img.get_rect(center=(int(self.x + ox), int(self.y + oy)))
        surf.blit(img, rect.topleft)
        cx, cy = int(self.x + ox), int(self.y + oy)
        if self.flash > 0:
            pygame.draw.circle(surf, (255, 255, 255), (cx, cy), self.radius + 3, 2)
        if self.shield_t > 0:
            pygame.draw.circle(surf, (90, 140, 255), (cx, cy), self.radius + 7, 2)
        if self.frozen_t > 0:
            pygame.draw.circle(surf, (160, 240, 255), (cx, cy), self.radius + 9, 2)
            pygame.draw.circle(surf, (160, 240, 255), (cx, cy), self.radius + 13, 1)
        if self.burn_t > 0:
            pygame.draw.circle(surf, (255, 110, 0), (cx, cy), self.radius + 9, 2)
        if self.mud_t > 0:
            pygame.draw.circle(surf, (180, 130, 60), (cx, cy), self.radius + 7, 2)
        if self.shock_t > 0:
            pygame.draw.circle(surf, (255, 240, 110), (cx, cy), self.radius + 11, 1)
