# -*- coding: utf-8 -*-
"""
ИИ бота: держит дистанцию, обходит препятствия по флангу, уворачивается
от пуль, выбирается из застреваний и ездит за ремонтом, когда подбит.
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
        self.orbit = 1          # направление орбиты вокруг игрока
        self.orbit_t = 0.0      # до смены направления орбиты
        self.fire_delay = 0.3   # небольшая пауза между решениями стрелять
        self.aim_noise = random.uniform(-4, 4)
        self.unstick_t = 0.0    # время отхода после застревания
        self.unstick_turn = 1   # в какую сторону крутиться при отходе

    # ---------- помощники ----------

    def _threat(self, game):
        """Пуля игрока, которая РЕАЛЬНО опасна: близко и летит точно в нас."""
        t = self.t
        best, best_d = None, 1e9
        for b in game.bullets:
            if b.owner is not game.player:
                continue
            bx, by = t.x - b.x, t.y - b.y
            d = math.hypot(bx, by)
            if d > 340 or d < 1:
                continue
            sp = math.hypot(b.vx, b.vy) + 1e-6
            dot = (bx * b.vx + by * b.vy) / (d * sp)
            if dot > 0.93 and d < best_d:
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

    def _visible(self, game, x, y):
        return not game.arena.line_blocked(self.t.x, self.t.y, x, y)

    # ---------- основное ----------

    def update(self, dt, game):
        t = self.t
        p = game.player
        if not t.alive or not p.alive:
            return

        dx, dy = p.x - t.x, p.y - t.y
        dist = math.hypot(dx, dy)
        ang_to = math.degrees(math.atan2(dy, dx))

        forward, turn = 0, 0
        desired = None

        if self.unstick_t > 0:
            # отход после застревания: пятимся и подворачиваем
            self.unstick_t -= dt
            forward = -1
            turn = self.unstick_turn
        else:
            threat = self._threat(game)
            if threat is not None:
                # уклонение: уход перпендикулярно траектории пули
                desired = math.degrees(math.atan2(threat.vy, threat.vx)) + 90 * self._side(threat)
                forward = 1
            else:
                desired = self._choose_direction(game, ang_to, dist)
                if abs(_ang_diff(desired, t.angle)) < 75:
                    forward = 1

            if desired is not None:
                d = _ang_diff(desired, t.angle)
                if abs(d) > 3:
                    turn = 1 if d > 0 else -1

            # упёрлись в препятствие — входим в режим отхода
            if t._stuck > 0.4:
                self.unstick_t = random.uniform(0.4, 0.7)
                self.unstick_turn = random.choice((-1, 1))
                t._stuck = 0.0

        t.control(dt, game.arena, forward, turn, (p,))
        self._try_fire(dt, game, p, ang_to)

    # ---------- куда едем ----------

    def _choose_direction(self, game, ang_to, dist):
        """Выбор направления: ремонт / фланг / дистанция."""
        t = self.t
        p = game.player
        # 1) подбит и видит ремонт по прямой — едем за ним
        if t.hp < t.max_hp * 0.45:
            repair = self._nearest_repair(game)
            if repair is not None and self._visible(game, repair.x, repair.y):
                return math.degrees(math.atan2(repair.y - t.y, repair.x - t.x))
        # 2) игрок скрыт препятствием — не долбимся в стену, заходим с фланга
        if not self._visible(game, p.x, p.y):
            return self._flank_angle(ang_to, dist)
        # 3) игрок виден: сближение / отход / орбита
        return self._combat_angle(ang_to, dist)

    def _flank_angle(self, ang_to, dist):
        """Объезд препятствия: смещаемся в сторону, где открытый путь."""
        self.orbit_t -= 1 / 60
        if self.orbit_t <= 0:
            self.orbit = random.choice((-1, 1))
            self.orbit_t = random.uniform(1.2, 2.5)
        if dist > 360:
            return ang_to + 55 * self.orbit   # обходим по дуге
        return ang_to + 90 * self.orbit       # кружим вокруг укрытия

    def _combat_angle(self, ang_to, dist):
        """Держим комфортную дистанцию ~230-360, иначе орбита."""
        self.orbit_t -= 1 / 60
        if self.orbit_t <= 0:
            self.orbit = random.choice((-1, 1))
            self.orbit_t = random.uniform(1.2, 2.5)
        if dist > 360:
            return ang_to                     # сближаемся
        if dist < 230:
            return ang_to + 180               # отъезжаем
        return ang_to + 90 * self.orbit       # орбита

    # ---------- стрельба ----------

    def _try_fire(self, dt, game, p, ang_to):
        t = self.t
        self.fire_delay -= dt
        if t.cooldown > 0 or self.fire_delay > 0:
            return
        aim = ang_to + self.aim_noise
        if abs(_ang_diff(aim, t.angle)) < 9 and self._visible(game, p.x, p.y):
            t.try_shoot(game.bullets, game.effects, game.sounds)
            self.aim_noise = random.uniform(-4, 4)
            self.fire_delay = random.uniform(0.1, 0.45)
