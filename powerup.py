# -*- coding: utf-8 -*-
"""Бонусы: 12 видов + мины, которые танки ставят на арене.
Стихии на карте не выпадают — они выбираются в ангаре (часть сборки).
v2.9: добавились ТУРЕЛЬ (Т) и РАЗРЫВНЫЕ (Р)."""
import math
import pygame
from effects import get_font

PU_INFO = {
    "shield": {"letter": "Щ", "color": (70, 110, 255), "name": "ЩИТ",
               "hint": "урон x0.4 на 5 сек"},
    "triple": {"letter": "В", "color": (255, 208, 0), "name": "ВЕЕР",
               "hint": "3 выстрела веером; с «Лазером» — лазерный веер"},
    "boost":  {"letter": "У", "color": (60, 230, 120), "name": "ТУРБО",
               "hint": "+60% скорости (с «Гонцом» — +20%)"},
    "repair": {"letter": "+", "color": (255, 90, 90), "name": "РЕМОНТ",
               "hint": "+40 к прочности"},
    "mine":   {"letter": "М", "color": (255, 140, 0), "name": "МИНА",
               "hint": "ставится за кормой, 50 урона"},
    "laser":  {"letter": "Л", "color": (190, 120, 255), "name": "ЛАЗЕР",
               "hint": "мгновенный луч; с «Веером» — лазерный веер"},
    "smoke":  {"letter": "Д", "color": (170, 180, 200), "name": "ДЫМ",
               "hint": "завеса: бот сквозь неё не видит"},
    "rapid":  {"letter": "С", "color": (0, 255, 180), "name": "СКОРОСТРЕЛ",
               "hint": "перезарядка x2.2 на 5 сек"},
    "freeze": {"letter": "Э", "color": (160, 240, 255), "name": "ЭМИ",
               "hint": "валит всех чужих на 2.5 сек, свои целы"},
    # ----- стена-бустер -----
    "barrier": {"letter": "Б", "color": (205, 210, 225), "name": "СТЕНА",
               "hint": "ставится по Q: 120 прочности, не проехать"},
    # ----- v2.9: турель и разрывные -----
    "turret": {"letter": "Т", "color": (120, 230, 150), "name": "ТУРЕЛЬ",
               "hint": "ставится по R: сама стреляет по чужакам 25 с"},
    "he":      {"letter": "Р", "color": (255, 120, 50), "name": "РАЗРЫВНЫЕ",
               "hint": "6 выстрелов с осколками: задевает чужаков рядом"},
}

_FONTS = {}


def _font(size):
    if size not in _FONTS:
        _FONTS[size] = get_font(size)
    return _FONTS[size]


class PowerUp:
    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        self.kind = kind
        self.t = 0.0  # время жизни для пульсации

    def update(self, dt):
        self.t += dt

    def draw(self, surf, ox=0, oy=0):
        info = PU_INFO[self.kind]
        x, y = int(self.x + ox), int(self.y + oy)
        r = int(14 + 2 * math.sin(self.t * 5))  # пульсация
        pygame.draw.circle(surf, (26, 32, 58), (x, y), r + 8)
        pygame.draw.circle(surf, info["color"], (x, y), r, 2)
        img = _font(24).render(info["letter"], True, info["color"])
        surf.blit(img, img.get_rect(center=(x, y)))


class Mine:
    """Мина: ставится за кормой, взводится через 0.6 с, бьёт только врага."""

    def __init__(self, x, y, owner):
        self.x = x
        self.y = y
        self.owner = owner
        self.t = 0.0
        self.armed = False

    def update(self, dt):
        self.t += dt
        if not self.armed and self.t > 0.6:
            self.armed = True

    def draw(self, surf, ox=0, oy=0):
        x, y = int(self.x + ox), int(self.y + oy)
        blink = (math.sin(self.t * (10 if self.armed else 4)) + 1) / 2
        color = (255, 140, 0) if self.armed else (150, 150, 160)
        pygame.draw.circle(surf, (40, 30, 20), (x, y), 8)
        pygame.draw.circle(surf, color, (x, y), 8, 2)
        # шипы по сторонам
        for a in range(4):
            ang = a * math.pi / 2 + self.t * 0.8
            pygame.draw.line(surf, color, (x, y),
                             (x + int(12 * math.cos(ang)), y + int(12 * math.sin(ang))), 2)
        # огонёк в центре, мигает
        if blink > 0.5:
            pygame.draw.circle(surf, color, (x, y), 3)
