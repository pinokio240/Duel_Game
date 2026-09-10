# -*- coding: utf-8 -*-
"""
Танк: «танковое» управление, стрельба, броня, бонусы.
Скорость считается честно: скорость шасси * (1 - вес корпуса).
"""
import math
import pygame
from settings import (CHASSIS, HULL, TANK_RADIUS, PU_SHIELD_TIME,
                      PU_BOOST_TIME, PU_TRIPLE_SHOTS, PU_REPAIR_HP,
                      PU_RAPID_TIME, PU_RAPID_MULT)
from bullet import Bullet


class Tank:
    def __init__(self, x, y, angle, chassis_key, hull_key, color):
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)  # градусы, 0 = вправо, по часовой
        self.ch_key, self.hull_key = chassis_key, hull_key
        self.chassis = CHASSIS[chassis_key]
        self.hull = HULL[hull_key]
        self.color = color
        self.light = tuple(min(c + 100, 255) for c in color)
        self.radius = TANK_RADIUS
        self.max_hp = self.hull["hp"]
        self.hp = self.max_hp
        self.armor = self.chassis["armor"]  # сглаживание урона
        self.cooldown = 0.0
        self.alive = True
        self.flash = 0.0          # белая вспышка при получении урона
        self._stuck = 0.0         # бот: застрял ли у стены
        # активные бонусы
        self.shield_t = 0.0
        self.boost_t = 0.0
        self.triple = 0
        self.rapid_t = 0.0        # скорострел
        self.frozen_t = 0.0       # ЭМИ-заморозка
        self.laser_charges = 0    # заряды лазера
        self._sprite = self._make_sprite()

    # ----- характеристики с учётом бонусов -----
    @property
    def speed(self):
        if self.frozen_t > 0:
            return 0.0
        s = self.chassis["speed"] * (1.0 - self.hull["weight"])
        if self.boost_t > 0:
            s *= 1.6
        return s

    @property
    def turn_speed(self):
        return self.chassis["turn"]  # градусов/сек

    @property
    def reload_time(self):
        r = self.hull["reload"]
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
        # ствол (смотрит вправо — по нулевому углу)
        pygame.draw.rect(s, self.light, (44, 22, 19, 7), border_radius=2)
        pygame.draw.rect(s, self.color, (41, 19, 7, 13), border_radius=2)
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
        for a in angles:
            bullets.append(Bullet(mx, my, a, self))
        self.cooldown = self.reload_time
        effects.burst(mx, my, self.light, 5, 130, 0.18, 3)
        sounds.play("shoot")

    # ----- урон и бонусы -----
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
            self.hp = 0
            self.alive = False
            effects.burst(self.x, self.y, self.color, 42, 430, 0.9, 6)
            effects.burst(self.x, self.y, (255, 255, 255), 16, 260, 0.6, 4)
            effects.ring(self.x, self.y, self.color, 100, 0.5)
            effects.shake(9, 0.4)
            sounds.play("explode")
        else:
            effects.burst(self.x, self.y, self.color, 6, 160, 0.3, 3)
            sounds.play("hit")

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

    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.flash = max(0.0, self.flash - dt)
        self.shield_t = max(0.0, self.shield_t - dt)
        self.boost_t = max(0.0, self.boost_t - dt)
        self.rapid_t = max(0.0, self.rapid_t - dt)
        self.frozen_t = max(0.0, self.frozen_t - dt)

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
