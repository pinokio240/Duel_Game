# -*- coding: utf-8 -*-
"""ТУРЕЛЬ (v2.9): размещаемый станок — ставится танком по R, сама ищет
ближайшего чужака в радиусе, целится и стреляет. Служит команде владельца,
пробивается снарядами; v3.1.1 — ПОСТОЯННАЯ, таймера жизни нет
(как у мин и стен), гибнет только от урона. Рисуется как неоновый
треугольный станок с коротким стволом, поворачивается к цели."""
import math
import pygame
from settings import TURRET_HP, TURRET_RANGE, TURRET_COOLDOWN


class Turret:
    def __init__(self, x, y, owner):
        self.x = float(x)
        self.y = float(y)
        self.owner = owner
        # у чьей команды служит: в командах — команда владельца,
        # в FFA — уникальный team владельца (только он «свой»)
        self.team = owner.team
        self.hp = TURRET_HP
        self.max_hp = TURRET_HP
        self.t = 0.0            # время с установки (для анимации)
        self.cd = 0.8           # «прогрев» после установки
        self.angle = owner.angle  # куда смотрит ствол
        self.alive = True
        self.radius = 16
        self.color = owner.color
        self.light = owner.light

    # снаряды турели совместимы с логикой Bullet: у «владельца» снаряда
    # читают color, team, alive, x, y, radius
    @property
    def light_color(self):
        return self.light

    def expired(self):
        # v3.1.1: таймера жизни больше нет — только от урона
        return self.hp <= 0

    def take_damage(self, dmg, effects, sounds):
        if not self.alive:
            return
        self.hp -= dmg
        effects.burst(self.x, self.y, self.color, 5, 140, 0.3, 3)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            effects.burst(self.x, self.y, self.color, 18, 300, 0.5, 4)
            effects.ring(self.x, self.y, self.color, 60, 0.4)
            effects.shake(4, 0.2)
            sounds.play("explode")

    def update(self, dt):
        self.t += dt
        self.cd = max(0.0, self.cd - dt)

    def aim(self, game):
        """Ближайший живой ЧУЖОЙ танк в радиусе с чистой линией огня
        (или None). Чужак — тот, у кого team другой; дым обзор не режет
        (турель на радарах), но стены — заслон."""
        best, best_d = None, TURRET_RANGE
        for t in game.tanks:
            if not t.alive or t.team == self.team:
                continue
            d = math.hypot(t.x - self.x, t.y - self.y)
            if d >= best_d:
                continue
            if game.arena.line_blocked(self.x, self.y, t.x, t.y):
                continue
            best, best_d = t, d
        return best

    def draw(self, surf, ox=0, oy=0):
        x, y = int(self.x + ox), int(self.y + oy)
        k = self.hp / self.max_hp
        # v3.1.1: мигаем не перед «рассыпанием», а когда вот-вот сломается
        blink = k < 0.35 and int(self.t * 6) % 2 == 0
        core = (90, 95, 115) if blink else self.color
        # платформа
        pygame.draw.circle(surf, (30, 36, 60), (x, y), 14)
        pygame.draw.circle(surf, core, (x, y), 14, 2)
        # короткий ствол, поворачивается за целью
        rad = math.radians(self.angle)
        ex = x + math.cos(rad) * 20
        ey = y + math.sin(rad) * 20
        pygame.draw.line(surf, core, (x, y), (ex, ey), 5)
        pygame.draw.circle(surf, self.light, (ex, ey), 3)
        # огонёк в центре: мигает, пока турель жива
        if math.sin(self.t * 6) > 0:
            pygame.draw.circle(surf, self.light, (x, y), 3)
        # полоска прочности — только когда турель потрепана
        if k < 0.999:
            w = 28
            r = pygame.Rect(x - w // 2, y - 24, w, 4)
            pygame.draw.rect(surf, (30, 36, 60), r, border_radius=2)
            f = r.copy()
            f.w = max(0, int(w * k))
            if f.w > 0:
                pygame.draw.rect(surf, core, f, border_radius=2)
