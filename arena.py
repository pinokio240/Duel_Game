# -*- coding: utf-8 -*-
"""Арена: 16 вариантов расстановки препятствий, стены, коллизии, лучи.
v2.1: РАНДОМИЗАЦИЯ — перед боем карта может зеркально отразиться и получить
несколько случайных баррикад, а сама арена переразыгрывается КАЖДЫЙ РАУНД.
v2.2: КАРТЫ ПОБОЛЬШЕ — мир 1920x1080 вместо окна 1280x720: раскладки
масштабируются в 1.5 раза, камера следует за игроком (в game.py)."""
import math
import random
import pygame
from settings import (SCREEN_W, SCREEN_H, COL_WALL, COL_GRID, COL_BG,
                      PROP_MAX, ARENA_W, ARENA_H)

WALL_T = 60  # толщина внешних стен в исходной раскладке (масштабируется ниже)

# Масштаб мира: 1920/1280 = 1.5 — все раскладки растягиваются до большого мира
_S = ARENA_W / float(SCREEN_W)
WALL_TS = int(WALL_T * _S)          # стены тоже толще (90 px)


def _scaled_layout(rects):
    """Раскладка из исходных координат 1280x720 — в мир 1920x1080."""
    return [(int(x * _S), int(y * _S), max(1, int(w * _S)), max(1, int(h * _S)))
            for (x, y, w, h) in rects]

# Восемь симметричных раскладок арены (все зеркалятся по центру)
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
    # «Уголки»: угловые L-блоки и пятачок в центре
    [(170, 130, 140, 36), (970, 554, 140, 36),
     (170, 130, 36, 140), (1074, 450, 36, 140),
     (970, 130, 140, 36), (170, 554, 140, 36),
     (1074, 130, 36, 140), (170, 450, 36, 140),
     (600, 330, 80, 60)],
    # «Полоса»: три горизонтальные стены со сдвигом — заходишь с фланга
    [(240, 190, 170, 36), (870, 494, 170, 36),
     (640, 190, 170, 36), (470, 494, 170, 36),
     (510, 342, 260, 36)],
    # «Соты»: поле колонн-точек, вечная погоня по диагоналям
    [(300, 180, 56, 56), (924, 484, 56, 56),
     (560, 180, 56, 56), (664, 484, 56, 56),
     (300, 484, 56, 56), (924, 180, 56, 56),
     (430, 332, 56, 56), (794, 332, 56, 56),
     (612, 332, 56, 56)],
    # «Мосты»: центральная колонна с проходом, ступени по углам
    [(590, 120, 100, 180), (590, 420, 100, 180),
     (300, 120, 140, 36), (840, 564, 140, 36),
     (300, 564, 140, 36), (840, 120, 140, 36)],
    # «Бункер»: большая коробка в центре и точки по диагоналям
    [(560, 280, 160, 160),
     (350, 180, 36, 36), (894, 504, 36, 36),
     (350, 504, 36, 36), (894, 180, 36, 36)],
    # «Веер»: лучи блоков от центра — кружим по дугам
    [(600, 120, 80, 80), (600, 520, 80, 80),
     (280, 140, 90, 90), (910, 490, 90, 90),
     (280, 490, 90, 90), (910, 140, 90, 90),
     (164, 330, 36, 100), (1080, 330, 36, 100),
     (595, 320, 90, 80)],
    # «Шахты»: сетка столбов-колонн, вечный поиск просвета
    [(160, 160, 50, 50), (1070, 510, 50, 50),
     (160, 510, 50, 50), (1070, 160, 50, 50),
     (160, 340, 50, 50), (1070, 330, 50, 50),
     (420, 160, 60, 36), (800, 524, 60, 36),
     (420, 524, 60, 36), (800, 160, 60, 36),
     (600, 330, 80, 60)],
    # ----- шесть новых арен v2.1 -----
    # «Вилка»: стена по центру с проёмом, укрытия по сторонам
    [(620, 60, 40, 170), (620, 490, 40, 170),
     (380, 180, 90, 36), (810, 180, 90, 36),
     (380, 504, 90, 36), (810, 504, 90, 36),
     (140, 330, 36, 60), (1104, 330, 36, 60)],
    # «Кольцо»: стены по кругу с диагональными проходами и столб в центре
    [(600, 150, 80, 36), (600, 534, 80, 36),
     (430, 340, 36, 80), (814, 340, 36, 80),
     (470, 210, 36, 36), (774, 210, 36, 36),
     (470, 474, 36, 36), (774, 474, 36, 36),
     (612, 340, 56, 40)],
    # «Зигзаг»: три горизонтальные стены со сдвигом и разрывом по центру
    [(140, 170, 280, 36), (860, 170, 280, 36),
     (420, 342, 130, 36), (730, 342, 130, 36),
     (140, 514, 280, 36), (860, 514, 280, 36)],
    # «Казармы»: две стены-перегородки с дверями по центру
    [(300, 60, 36, 220), (300, 400, 36, 260),
     (944, 60, 36, 220), (944, 400, 36, 260),
     (560, 100, 160, 36), (560, 584, 160, 36),
     (612, 330, 56, 60)],
    # «Ступени»: две диагонали блоков — нырки по лестнице
    [(180, 130, 100, 36), (300, 250, 100, 36),
     (420, 370, 100, 36), (540, 490, 100, 36),
     (1000, 130, 100, 36), (880, 250, 100, 36),
     (760, 370, 100, 36), (640, 490, 100, 36),
     (612, 330, 56, 56)],
    # «Бухта»: боковые карманы и козырьки сверху/снизу
    [(140, 240, 36, 240), (1104, 240, 36, 240),
     (300, 100, 200, 36), (780, 100, 200, 36),
     (300, 584, 200, 36), (780, 584, 200, 36),
     (560, 250, 40, 40), (680, 430, 40, 40)],
]

MAP_NAMES = ["Классика", "Крестовина", "Колонны", "Уголки",
             "Полоса", "Соты", "Мосты", "Бункер", "Веер", "Шахты",
             "Вилка", "Кольцо", "Зигзаг", "Казармы", "Ступени", "Бухта"]

# классические точки появления танков в ИСХОДНЫХ координатах (масштабируются)
_SPAWN_SRC = ((240, 360), (1040, 360))
_SPAWN_COLS = [(int(x * _S), int(y * _S)) for x, y in _SPAWN_SRC]


class Arena:
    def __init__(self, variant=0, shuffle=False):
        """shuffle=True — случайное зеркало и/или случайные баррикады:
        одна и та же карта каждый раз играет по-новому."""
        self.variant = variant % len(LAYOUTS)
        w, h = ARENA_W, ARENA_H
        self.w = w
        self.h = h
        self.walls = [
            pygame.Rect(0, 0, w, WALL_TS),
            pygame.Rect(0, h - WALL_TS, w, WALL_TS),
            pygame.Rect(0, 0, WALL_TS, h),
            pygame.Rect(w - WALL_TS, 0, WALL_TS, h),
        ]
        obs = [pygame.Rect(r) for r in _scaled_layout(LAYOUTS[self.variant])]
        tags = []
        if shuffle:
            mx, my = (random.random() < 0.5, random.random() < 0.5)
            if mx:   # зеркалим по горизонтали
                obs = [pygame.Rect(w - r.x - r.w, r.y, r.w, r.h) for r in obs]
            if my:   # и по вертикали
                obs = [pygame.Rect(r.x, h - r.y - r.h, r.w, r.h) for r in obs]
            if mx or my:
                tags.append("зеркало")
            added = self._add_props(obs, w, h)
            if added:
                tags.append("+%d баррикад" % added)
        self.obstacles = obs
        self.rects = self.walls + self.obstacles
        self.name = MAP_NAMES[self.variant] + (" ★" if tags else "")
        self.dynamic = []   # живые препятствия (стены-барьеры), меняются в бою
        self._bg = self._make_background()

    @staticmethod
    def _add_props(obs, w, h):
        """Накидать 0..PROP_MAX случайных баррикад в свободные места —
        подальше от стен, других препятствий и точек появления танков.
        Баррикады крупнее в большом мире (v2.2)."""
        added = 0
        for _ in range(70):
            if added >= PROP_MAX:
                break
            if added and random.random() < 0.4:
                break            # бывает и пара баррикад, и ноль
            pw, ph = random.choice(((54, 54), (84, 42), (42, 84), (72, 72)))
            x = random.uniform(WALL_TS + 100, w - WALL_TS - 100 - pw)
            y = random.uniform(WALL_TS + 90, h - WALL_TS - 90 - ph)
            r = pygame.Rect(int(x), int(y), pw, ph)
            if any(r.inflate(110, 110).colliderect(o) for o in obs):
                continue
            cx, cy = r.center
            if any((cx - sx) ** 2 + (cy - sy) ** 2 < 210 ** 2
                   for sx, sy in _SPAWN_COLS):
                continue
            obs.append(r)
            added += 1
        return added

    def set_dynamic(self, blockers):
        self.dynamic = blockers

    def walls_only(self):
        """Вид арены без барьеров — для снарядов (те бьют барьеры отдельно)."""
        return _WallsView(self)

    # ----- фон: неоновая сетка на весь большой мир -----
    def _make_background(self):
        bg = pygame.Surface((self.w, self.h))
        bg.fill(COL_BG)
        for gx in range(0, self.w, 48):
            pygame.draw.line(bg, COL_GRID, (gx, 0), (gx, self.h))
        for gy in range(0, self.h, 48):
            pygame.draw.line(bg, COL_GRID, (0, gy), (self.w, gy))
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
        if any(self._circle_rect(x, y, radius, r) for r in self.rects):
            return True
        return any(d.blocks_circle(x, y, radius) for d in self.dynamic)

    def point_blocked(self, x, y):
        if any(r.collidepoint(x, y) for r in self.rects):
            return True
        return any(d.blocks_point(x, y) for d in self.dynamic)

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
            x = random.uniform(WALL_TS + 70, self.w - WALL_TS - 70)
            y = random.uniform(WALL_TS + 70, self.h - WALL_TS - 70)
            if self.circle_collides(x, y, 30):
                continue
            if all((x - ax) ** 2 + (y - ay) ** 2 > avoid_dist ** 2 for ax, ay in avoid):
                return x, y
        return self.w / 2, self.h / 2


class _WallsView:
    """Тонкая обёртка: та же арена, но без динамических барьеров.
    Нужна снарядам — те взаимодействуют с барьерами через урон в game.py."""

    def __init__(self, arena):
        self._a = arena

    @property
    def rects(self):
        return self._a.rects

    def circle_collides(self, x, y, radius):
        return any(self._a._circle_rect(x, y, radius, r) for r in self._a.rects)

    def point_blocked(self, x, y):
        return any(r.collidepoint(x, y) for r in self._a.rects)

    def line_blocked(self, x1, y1, x2, y2, step=24):
        d = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(d // step))
        for i in range(1, n):
            t = i / n
            if self.point_blocked(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
                return True
        return False
