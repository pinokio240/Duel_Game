# -*- coding: utf-8 -*-
"""Арена: 3 варианта расстановки препятствий, стены, коллизии, лучи."""
import math
import random
import pygame
from settings import SCREEN_W, SCREEN_H, COL_WALL, COL_GRID, COL_BG

WALL_T = 60  # толщина внешних стен

# Три симметричных раскладки арены
LAYOUTS = [
    # «Классика»: центральная колонна и блоки по сторонам
    [(600, 300, 80, 120),
     (330, 160, 130, 36), (820, 160, 130, 36),
     (330, 524, 130, 36), (820, 524, 130, 36),
     (140, 330, 36, 60), (1104, 330, 36, 60)],
    # «Крестовина»: длинные козырьки и точки-укрытия
    [(600, 320, 80, 80),
     (400, 180, 36, 36), (844, 180, 36, 36),
     (400, 504, 36, 36), (844, 504, 36, 36),
     (480, 140, 320, 36), (480, 544, 320, 36)],
    # «Колонны»: зал с колоннами, узкие проходы для снарядов
    [(330, 210, 40, 130), (330, 380, 40, 130),
     (910, 210, 40, 130), (910, 380, 40, 130),
     (610, 330, 60, 60)],
]


class Arena:
    def __init__(self, variant=0):
        self.variant = variant % len(LAYOUTS)
        w, h = SCREEN_W, SCREEN_H
        self.walls = [
            pygame.Rect(0, 0, w, WALL_T),
            pygame.Rect(0, h - WALL_T, w, WALL_T),
            pygame.Rect(0, 0, WALL_T, h),
            pygame.Rect(w - WALL_T, 0, WALL_T, h),
        ]
        self.obstacles = [pygame.Rect(r) for r in LAYOUTS[self.variant]]
        self.rects = self.walls + self.obstacles
        self._bg = self._make_background()

    # ----- фон: неоновая сетка -----
    def _make_background(self):
        bg = pygame.Surface((SCREEN_W, SCREEN_H))
        bg.fill(COL_BG)
        for gx in range(0, SCREEN_W, 48):
            pygame.draw.line(bg, COL_GRID, (gx, 0), (gx, SCREEN_H))
        for gy in range(0, SCREEN_H, 48):
            pygame.draw.line(bg, COL_GRID, (0, gy), (SCREEN_W, gy))
        return bg

    def draw(self, surf, ox=0, oy=0):
        surf.blit(self._bg, (int(ox), int(oy)))
        for r in self.obstacles:
            glow = r.inflate(12, 12)
            pygame.draw.rect(surf, (36, 44, 84), glow.move(int(ox), int(oy)), border_radius=8)
            pygame.draw.rect(surf, COL_WALL, r.move(int(ox), int(oy)), border_radius=6)
            pygame.draw.rect(surf, (150, 165, 230), r.move(int(ox), int(oy)), 2, border_radius=6)

    # ----- коллизии -----
    @staticmethod
    def _circle_rect(x, y, radius, rect):
        cx = max(rect.left, min(x, rect.right))
        cy = max(rect.top, min(y, rect.bottom))
        return (x - cx) ** 2 + (y - cy) ** 2 < radius * radius

    def circle_collides(self, x, y, radius):
        return any(self._circle_rect(x, y, radius, r) for r in self.rects)

    def point_blocked(self, x, y):
        return any(r.collidepoint(x, y) for r in self.rects)

    def line_blocked(self, x1, y1, x2, y2, step=24):
        """Есть ли препятствие на линии (проверка: видит ли бот цель)."""
        d = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(d // step))
        for i in range(1, n):
            t = i / n
            if self.point_blocked(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
                return True
        return False

    def raycast(self, x, y, angle, max_dist=2000.0, step=6.0):
        """Куда попадёт мгновенный луч из (x, y) под углом angle.
        Возвращает точку попадания в стену/препятствие или конец луча."""
        rad = math.radians(angle)
        dx, dy = math.cos(rad) * step, math.sin(rad) * step
        dist = 0.0
        while dist < max_dist:
            x += dx
            y += dy
            dist += step
            if self.point_blocked(x, y):
                return x, y
        return x, y

    def free_spot(self, avoid=(), avoid_dist=150):
        """Случайная свободная точка (для появления бонусов)."""
        for _ in range(200):
            x = random.uniform(WALL_T + 70, SCREEN_W - WALL_T - 70)
            y = random.uniform(WALL_T + 70, SCREEN_H - WALL_T - 70)
            if self.circle_collides(x, y, 30):
                continue
            if all((x - ax) ** 2 + (y - ay) ** 2 > avoid_dist ** 2 for ax, ay in avoid):
                return x, y
        return SCREEN_W / 2, SCREEN_H / 2
