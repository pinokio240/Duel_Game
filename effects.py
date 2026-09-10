# -*- coding: utf-8 -*-
"""Визуальные эффекты: частицы, кольца взрывов, всплывающий текст, тряска экрана."""
import math
import random
import pygame

# ----- Общий кэш шрифтов (используется всей игрой) -----
_FONTS = {}

def get_font(size, bold=True):
    key = (size, bold)
    if key not in _FONTS:
        try:
            # На Windows возьмётся Consolas (кириллица есть), в Linux — DejaVu
            _FONTS[key] = pygame.font.SysFont("consolas,arial,dejavusansmono", size, bold=bold)
        except Exception:
            _FONTS[key] = pygame.font.Font(None, size)
    return _FONTS[key]


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color")
    def __init__(self, x, y, vx, vy, life, size, color):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.size, self.color = size, color


class Ring:
    __slots__ = ("x", "y", "max_r", "life", "max_life", "color")
    def __init__(self, x, y, max_r, life, color):
        self.x, self.y = x, y
        self.max_r, self.life, self.max_life = max_r, life, life
        self.color = color


class FloatText:
    __slots__ = ("x", "y", "text", "life", "max_life", "color")
    def __init__(self, x, y, text, color):
        self.x, self.y, self.text, self.color = x, y, text, color
        self.life = self.max_life = 0.9


class Effects:
    """Копилка всех эффектов. Одна на всю игру."""

    def __init__(self):
        self.particles = []
        self.rings = []
        self.texts = []
        self.shake_t = 0.0
        self.shake_dur = 1.0
        self.shake_mag = 0.0

    # ----- создание эффектов -----
    def burst(self, x, y, color, n=14, speed=220, life=0.5, size=4):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(speed * 0.2, speed)
            self.particles.append(Particle(
                x, y, math.cos(a) * s, math.sin(a) * s,
                random.uniform(life * 0.4, life),
                random.randint(2, size), color))

    def ring(self, x, y, color, max_r=70, life=0.4):
        self.rings.append(Ring(x, y, max_r, life, color))

    def float_text(self, x, y, text, color):
        self.texts.append(FloatText(x, y, text, color))

    def shake(self, mag=6, dur=0.3):
        self.shake_mag = max(self.shake_mag, mag)
        self.shake_t = max(self.shake_t, dur)
        self.shake_dur = dur

    def offset(self):
        """Смещение камеры от тряски (для подрагивания всего экрана)."""
        if self.shake_t <= 0:
            return 0, 0
        k = self.shake_t / self.shake_dur
        return (random.uniform(-1, 1) * self.shake_mag * k,
                random.uniform(-1, 1) * self.shake_mag * k)

    # ----- обновление и отрисовка -----
    def update(self, dt):
        self.shake_t = max(0.0, self.shake_t - dt)
        for p in self.particles[:]:
            p.life -= dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= (1 - 2.5 * dt)
            p.vy *= (1 - 2.5 * dt)
            if p.life <= 0:
                self.particles.remove(p)
        for r in self.rings[:]:
            r.life -= dt
            if r.life <= 0:
                self.rings.remove(r)
        for t in self.texts[:]:
            t.life -= dt
            t.y -= 40 * dt
            if t.life <= 0:
                self.texts.remove(t)

    def draw(self, surf, ox=0, oy=0):
        for p in self.particles:
            k = p.life / p.max_life
            r = max(1, int(p.size * k))
            pygame.draw.circle(surf, p.color, (int(p.x + ox), int(p.y + oy)), r)
        for r in self.rings:
            k = 1 - r.life / r.max_life
            rad = int(r.max_r * k)
            if rad > 2:
                pygame.draw.circle(surf, r.color, (int(r.x + ox), int(r.y + oy)), rad, 3)
        for t in self.texts:
            k = t.life / t.max_life
            font = get_font(20)
            img = font.render(t.text, True, t.color)
            img.set_alpha(int(255 * min(1.0, k * 1.5)))
            surf.blit(img, img.get_rect(center=(int(t.x + ox), int(t.y + oy))))
