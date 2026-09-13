# -*- coding: utf-8 -*-
"""Снаряды с рикошетами от стен и препятствий + элементальные заряды.
v2.9: РАЗРЫВНЫЕ СНАРЯДЫ (he=True) — при гибели снаряд взрывается осколками:
взрыв задевает всех ЧУЖАКОВ в радиусе (владелец и его союзники целы)."""
import math
import pygame
from settings import (BULLET_SPEED, BULLET_DAMAGE, BULLET_BOUNCES,
                      VAMP_HEAL_RATIO, HE_SPLASH_RADIUS, HE_SPLASH_DAMAGE)

ELEMENT_COLORS = {
    "fire":     (255, 110, 0),
    "water":    (80, 170, 255),
    "earth":    (180, 130, 60),
    "electric": (255, 240, 110),
    "air":      (190, 235, 255),
    "ice":      (120, 255, 255),
    "poison":   (150, 255, 60),
    "vamp":     (255, 80, 160),
}


class Bullet:
    def __init__(self, x, y, angle, owner, damage=BULLET_DAMAGE, speed_mult=1.0,
                 element=None, bounces=None, big=False, he=False):
        rad = math.radians(angle)
        self.x = float(x)
        self.y = float(y)
        v = BULLET_SPEED * speed_mult
        self.vx = math.cos(rad) * v
        self.vy = math.sin(rad) * v
        self.owner = owner
        self.damage = damage
        # рикошеты: базовые из настроек; перк «Рикошет» добавляет свои
        self.bounces = BULLET_BOUNCES if bounces is None else bounces
        self.age = 0.0
        self.dead = False
        self.element = element
        # v2.9: разрывной снаряд — взрывается осколками при гибели
        self.he = he
        self.color = ELEMENT_COLORS.get(element, owner.color)
        if he:
            self.color = (255, 120, 50)   # разрывные видны своей оранжевой вспышкой
        self.big = big or speed_mult > 1.1   # тяжёлые снаряды рисуются крупнее
        self.prev = (self.x, self.y)  # точка в начале кадра (для шлейфа и отскока)

    def _he_blast(self, tanks, effects, sounds, direct=None):
        """Осколочный взрыв разрывного снаряда (v2.9): всех ЧУЖИХ в радиусе
        (кроме получившего прямое попадание — тот уже отболел) задевает
        HE_SPLASH_DAMAGE. Свои (та же команда) и сам владелец целы."""
        if not self.he:
            return
        effects.ring(self.x, self.y, (255, 120, 50), HE_SPLASH_RADIUS, 0.35)
        effects.burst(self.x, self.y, (255, 120, 50), 14, 260, 0.4, 4)
        effects.shake(3, 0.15)
        sounds.play("explode")
        oteam = getattr(self.owner, "team", None)
        for t in tanks:
            if t is direct or not t.alive or t is self.owner:
                continue
            if oteam is not None and getattr(t, "team", None) == oteam:
                continue   # свои осколками не задеваем
            if (t.x - self.x) ** 2 + (t.y - self.y) ** 2 < HE_SPLASH_RADIUS ** 2:
                t.take_damage(HE_SPLASH_DAMAGE, effects, sounds)
                effects.float_text(t.x, t.y - 44, "ОСКОЛКИ", (255, 120, 50))

    def update(self, dt, arena, tanks, effects, sounds):
        self.age += dt
        self.prev = (self.x, self.y)
        steps = 3  # подшаги, чтобы не проскочить препятствие за кадр
        for _ in range(steps):
            if self.dead:
                return
            self.x += self.vx * dt / steps
            self.y += self.vy * dt / steps

            # ----- столкновение со стенами и препятствиями -----
            for r in arena.rects:
                if r.collidepoint(self.x, self.y):
                    if self.bounces > 0:
                        self.bounces -= 1
                        # определяем сторону попадания по минимальной глубине
                        dl = self.x - r.left
                        dr = r.right - self.x
                        dtp = self.y - r.top
                        db = r.bottom - self.y
                        m = min(dl, dr, dtp, db)
                        if m in (dl, dr):
                            self.vx = -self.vx
                            self.x = self.prev[0]
                        else:
                            self.vy = -self.vy
                            self.y = self.prev[1]
                        effects.burst(self.x, self.y, self.color, 5, 130, 0.25, 3)
                        sounds.play("ric")
                    else:
                        effects.burst(self.x, self.y, self.color, 6, 150, 0.3, 3)
                        self._he_blast(tanks, effects, sounds)   # разрыв у стены
                        self.dead = True
                    break
            if self.dead:
                return

            # ----- попадание в танк -----
            for t in tanks:
                if not t.alive:
                    continue
                if t is self.owner and self.age < 0.25:
                    continue  # даём вылететь из своего ствола
                # КОМАНДНЫЕ РЕЖИМЫ (v2.2): своих не бьём — снаряд пролетает
                # сквозь союзника (в FFA у каждого танка своя команда)
                if (t is not self.owner
                        and getattr(t, "team", None) == getattr(self.owner, "team", None)):
                    continue
                if (t.x - self.x) ** 2 + (t.y - self.y) ** 2 < (t.radius + 4) ** 2:
                    t.take_damage(self.damage, effects, sounds)
                    # РАЗРЫВНЫЕ (v2.9): осколки по чужакам рядом (цель исключена —
                    # прямое попадание уже отболело)
                    self._he_blast(tanks, effects, sounds, direct=t)
                    # ПРАВИЛО СВОЕЙ СТИХИИ: земля/ток/вода/лёд/яд не действуют
                    # на того, кто выпустил снаряд (рикошет не замедляет себя);
                    # урон при само-попадании честно остаётся
                    if self.element and t is not self.owner:
                        t.apply_element(self.element, self.vx, self.vy,
                                        arena, effects, sounds)
                    # ВАМПИРИЗМ: стрелявшему возвращается часть урона снаряда
                    if (self.element == "vamp" and self.owner is not None
                            and self.owner is not t and self.owner.alive):
                        self.owner.heal(
                            max(1, int(round(self.damage * VAMP_HEAL_RATIO))),
                            effects)
                    effects.burst(self.x, self.y, self.color, 10, 220, 0.4, 3)
                    self.dead = True
                    return

    def draw(self, surf, ox=0, oy=0):
        x, y = int(self.x + ox), int(self.y + oy)
        px, py = int(self.prev[0] + ox), int(self.prev[1] + oy)
        r = 5 if self.big else 4
        pygame.draw.line(surf, self.color, (px, py), (x, y), r)   # шлейф
        pygame.draw.circle(surf, self.color, (x, y), r)
        pygame.draw.circle(surf, (255, 255, 255), (x, y), max(2, r - 2))
