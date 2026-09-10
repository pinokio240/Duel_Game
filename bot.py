# -*- coding: utf-8 -*-
"""
ИИ бота: держит дистанцию, целится с небольшим разбросом,
уворачивается от пуль, летит за ремонтом, когда подбит.
"""
import math
import random
from settings import CHASSIS, HULL


def _ang_diff(a, b):
    """Кратчайшая разница углов в градусах: куда и насколько поворачивать."""
    return ((a - b + 180) % 360) - 180


def random_build():
    """Случайная сборка бота — каждый матч он ездит на новой машине."""
    return random.choice(list(CHASSIS)), random.choice(list(HULL))


class BotAI:
    def __init__(self, tank):
        self.t = tank
        self.orbit = 1
        self.orbit_t = 0.0
        self.fire_delay = 0.3
        self.aim_noise = random.uniform(-5, 5)

    # ----- поиск угрозы: пуля игрока, летящая примерно в бота -----
    def _threat(self, game):
        t = self.t
        best, best_d = None, 1e9
        for b in game.bullets:
            if b.owner is not game.player:
                continue
            bx, by = t.x - b.x, t.y - b.y
            d = math.hypot(bx, by)
            if d > 440 or d < 1:
                continue
            sp = math.hypot(b.vx, b.vy) + 1e-6
            dot = (bx * b.vx + by * b.vy) / (d * sp)
            if dot > 0.85 and d < best_d:  # пуля смотрит в бота
                best, best_d = b, d
        return best

    def _side(self, bullet):
        """С какой стороны от траектории пули находится бот."""
        t = self.t
        cross = bullet.vx * (t.y - bullet.y) - bullet.vy * (t.x - bullet.x)
        return 1 if cross >= 0 else -1

    def _nearest_repair(self, game):
        t = self.t
        cands = [p for p in game.powerups if p.kind == "repair"]
        if not cands:
            return None
        return min(cands, key=lambda p: (t.x - p.x) ** 2 + (t.y - p.y) ** 2)

    def update(self, dt, game):
        t = self.t
        p = game.player
        if not t.alive or not p.alive:
            return

        dx, dy = p.x - t.x, p.y - t.y
        dist = math.hypot(dx, dy)
        ang_to = math.degrees(math.atan2(dy, dx))
        forward, turn = 0, 0

        threat = self._threat(game)
        if threat is not None:
            # уклонение: уход перпендикулярно траектории пули
            desired = math.degrees(math.atan2(threat.vy, threat.vx)) + 90 * self._side(threat)
            forward = 1
        elif t.hp < t.max_hp * 0.45:
            repair = self._nearest_repair(game)
            if repair is not None:
                desired = math.degrees(math.atan2(repair.y - t.y, repair.x - t.x))
            else:
                desired = self._combat_angle(dt, ang_to, dist)
        else:
            desired = self._combat_angle(dt, ang_to, dist)

        # застрял у препятствия — сдаём назад
        if t._stuck > 0.45:
            desired = t.angle + 180
            forward = 1

        d = _ang_diff(desired, t.angle)
        if abs(d) > 3:
            turn = 1 if d > 0 else -1
        # едем вперёд, если смотрим примерно туда, куда надо
        if forward == 0 and abs(d) < 70:
            forward = 1

        t.control(dt, game.arena, forward, turn, (p,))

        # ----- стрельба: целиться и ждать перезарядки + линии видимости -----
        self.fire_delay -= dt
        aim = ang_to + self.aim_noise
        if (abs(_ang_diff(aim, t.angle)) < 9 and t.cooldown <= 0
                and self.fire_delay <= 0
                and not game.arena.line_blocked(t.x, t.y, p.x, p.y)):
            t.try_shoot(game.bullets, game.effects, game.sounds)
            self.aim_noise = random.uniform(-5, 5)
            self.fire_delay = random.uniform(0.1, 0.45)

    def _combat_angle(self, dt, ang_to, dist):
        """Держим комфортную дистанцию ~230-360, иначе орбитим вокруг игрока."""
        self.orbit_t -= dt
        if self.orbit_t <= 0:
            self.orbit = random.choice((-1, 1))
            self.orbit_t = random.uniform(0.8, 1.8)
        if dist > 360:
            return ang_to
        if dist < 230:
            return ang_to + 180
        return ang_to + 90 * self.orbit
