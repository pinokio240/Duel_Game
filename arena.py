# -*- coding: utf-8 -*-
"""Арена: 16 вариантов расстановки препятствий, стены, коллизии, лучи.
v2.1: РАНДОМИЗАЦИЯ — перед боем карта может зеркально отразиться и получить
несколько случайных баррикад, а сама арена переразыгрывается КАЖДЫЙ РАУНД.
v2.2: КАРТЫ ПОБОЛЬШЕ — мир больше окна 1280x720: камера следует за игроком
(в game.py).
v2.5: РАЗМЕРЫ ПОД РЕЖИМ: обычные карты 2752x1548 (ещё x1.5 площади к v2.4),
командные 3888x2187 (ещё x3 площади к v2.4) — каждая арена несёт свой
размер, масштаб раскладки и толщину стен."""
import math
import random
import pygame
from settings import (SCREEN_W, SCREEN_H, COL_WALL, COL_GRID, COL_BG,
                      PROP_MAX, ARENA_W, ARENA_H,
                      TEAM_ARENA_W, TEAM_ARENA_H)

WALL_T = 60  # толщина внешних стен в исходной раскладке (масштабируется)

# Масштаб/стены ДЛЯ ОБЫЧНОЙ карты (по умолчанию) — оставлены для совместимости;
# каждая арена с v2.5 считает свои значения в __init__ (self.wall_t).
_S = ARENA_W / float(SCREEN_W)
WALL_TS = int(WALL_T * _S)

# классические точки появления танков в ИСХОДНЫХ координатах
_SPAWN_SRC = ((240, 360), (1040, 360))


def _scaled_layout(rects, s):
    """Раскладка из исходных координат 1280x720 — в мир масштаба s."""
    return [(int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s)))
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


class Arena:
    def __init__(self, variant=0, shuffle=False, team=False):
        """shuffle=True — случайное зеркало и/или случайные баррикады:
        одна и та же карта каждый раз играет по-новому.
        team=True — БОЛЬШАЯ карта: крупнее обычной (v2.5), там много
        танков; с v2.7 на них играют и большие FFA (6-10 танков)."""
        self.variant = variant % len(LAYOUTS)
        self.w, self.h = ((TEAM_ARENA_W, TEAM_ARENA_H) if team
                          else (ARENA_W, ARENA_H))
        s = self.w / float(SCREEN_W)      # масштаб исходной раскладки
        self.wall_t = int(WALL_T * s)     # толщина внешних стен
        self.spawn_cols = [(int(x * s), int(y * s)) for x, y in _SPAWN_SRC]
        w, h = self.w, self.h
        wt = self.wall_t
        self.walls = [
            pygame.Rect(0, 0, w, wt),
            pygame.Rect(0, h - wt, w, wt),
            pygame.Rect(0, 0, wt, h),
            pygame.Rect(w - wt, 0, wt, h),
        ]
        obs = [pygame.Rect(r) for r in _scaled_layout(LAYOUTS[self.variant], s)]
        tags = []
        if shuffle:
            mx, my = (random.random() < 0.5, random.random() < 0.5)
            if mx:   # зеркалим по горизонтали
                obs = [pygame.Rect(w - r.x - r.w, r.y, r.w, r.h) for r in obs]
            if my:   # и по вертикали
                obs = [pygame.Rect(r.x, h - r.y - r.h, r.w, r.h) for r in obs]
            if mx or my:
                tags.append("зеркало")
            added = self._add_props(obs)
            if added:
                tags.append("+%d баррикад" % added)
        self.obstacles = obs
        self.rects = self.walls + self.obstacles
        self.name = (MAP_NAMES[self.variant]
                     + (" [большая]" if team else "")
                     + (" ★" if tags else ""))
        self.dynamic = []   # живые препятствия (стены-барьеры), меняются в бою
        self._bg = self._make_background()

    def _add_props(self, obs):
        """Накидать 0..PROP_MAX случайных баррикад в свободные места —
        подальше от стен, других препятствий и точек появления танков.
        Размер баррикад и отступы тянутся за масштабом карты (v2.5)."""
        s = self.w / float(SCREEN_W)
        k = s / 1.5           # базовые размеры рассчитаны на масштаб 1.5
        wt, w, h = self.wall_t, self.w, self.h
        added = 0
        for _ in range(70):
            if added >= PROP_MAX:
                break
            if added and random.random() < 0.4:
                break            # бывает и пара баррикад, и ноль
            pw, ph = random.choice(((54, 54), (84, 42), (42, 84), (72, 72)))
            pw, ph = max(20, int(pw * k)), max(20, int(ph * k))
            x = random.uniform(wt + 100 * k, w - wt - 100 * k - pw)
            y = random.uniform(wt + 90 * k, h - wt - 90 * k - ph)
            r = pygame.Rect(int(x), int(y), pw, ph)
            if any(r.inflate(int(110 * k), int(110 * k)).colliderect(o)
                   for o in obs):
                continue
            cx, cy = r.center
            if any((cx - sx) ** 2 + (cy - sy) ** 2 < (210 * k) ** 2
                   for sx, sy in self.spawn_cols):
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
            x = random.uniform(self.wall_t + 70, self.w - self.wall_t - 70)
            y = random.uniform(self.wall_t + 70, self.h - self.wall_t - 70)
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
