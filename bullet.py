# -*- coding: utf-8 -*-
"""Снаряды с рикошетами от стен и препятствий."""
import math
import pygame
from settings import BULLET_SPEED, BULLET_DAMAGE, BULLET_BOUNCES


class Bullet:
    def __init__(self, x, y, angle, owner, damage=BULLET_DAMAGE, speed_mult=1.0):
        rad = math.radians(angle)
        self.x = float(x)
        self.y = float(y)
        v = BULLET_SPEED * speed_mult
        self.vx = math.cos(rad) * v
        self.vy = math.sin(rad) * v
        self.owner = owner
        self.damage = damage
        self.bounces = BULLET_BOUNCES
        self.age = 0.0
        self.dead = False
        self.color = owner.color
        self.big = speed_mult > 1.1   # тяжёлый снаряд «Дальней» рисуется крупнее
        self.prev = (self.x, self.y)  # точка в начале кадра (для шлейфа и отскока)

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
                if (t.x - self.x) ** 2 + (t.y - self.y) ** 2 < (t.radius + 4) ** 2:
                    t.take_damage(self.damage, effects, sounds)
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
