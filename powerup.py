# -*- coding: utf-8 -*-
"""Бонусы, которые появляются в бою: щит, веер, ускорение, ремонт."""
import math
import pygame
from effects import get_font

PU_INFO = {
    "shield": {"letter": "Щ", "color": (90, 140, 255), "name": "ЩИТ",
               "hint": "урон x0.4 на 5 сек"},
    "triple": {"letter": "В", "color": (255, 208, 0), "name": "ВЕЕР",
               "hint": "3 тройных выстрела"},
    "boost":  {"letter": "У", "color": (60, 230, 120), "name": "УСКОРЕНИЕ",
               "hint": "+60% скорости на 4 сек"},
    "repair": {"letter": "+", "color": (255, 90, 90), "name": "РЕМОНТ",
               "hint": "+40 к прочности"},
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
