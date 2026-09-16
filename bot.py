# -*- coding: utf-8 -*-
"""
ИИ бота: держит дистанцию, обходит препятствия ПО ШИРИНЕ ТАНКА (узкие щели
не считают проходимыми), уворачивается от пуль и мин, выбирается из
застреваний, СОБИРАЕТ бонусы (ремонт, щит, лазер...), ставит мины под
догоняющего и строит стены-барьеры между собой и целью.
v2.1: РЕЖИМЫ 1вс1вс1 — цель выбирается КАЖДЫЙ САМ ЗА СЕБЯ: ближайший
чужой танк (в том числе другой бот), а пули/мины ЛЮБОГО чужака опасны.
Сложность настраивается пресетом (1 лёгкий / 2 норм / 3 хардкор).
v3.2: ШТУРМ — защитники держатся точки, строят форт и ЧИНЯТ стены;
атакующие, когда цель не видна, давят на точку захвата.
"""
import math
import random
from settings import (CHASSIS, HULL, WEAPONS, PERKS, ELEMENTS, DIFF_PRESETS,
                      ASSAULT_POINT_R)

# сколько какой бонус стоит для бота (чем больше — тем охотнее едет)
PU_VALUE = {
    "repair": 3.0, "shield": 2.4, "freeze": 2.4, "laser": 2.2,
    "triple": 1.8, "rapid": 1.8, "boost": 1.5, "barrier": 1.3,
    "mine": 1.2, "smoke": 0.7,
    "turret": 1.6, "he": 1.4,          # v2.9: турель и разрывные
    "wall_strong": 1.4, "wall_heavy": 1.5, "wall_ultra": 1.6,  # v3.2
}


def _ang_diff(a, b):
    """Кратчайшая разница углов в градусах: куда и насколько поворачивать."""
    return ((a - b + 180) % 360) - 180


def random_build():
    """Случайная сборка бота (шасси, корпус, дуло, перк, стихия) —
    каждый матч он ездит на новой машине."""
    return (random.choice(list(CHASSIS)), random.choice(list(HULL)),
            random.choice(list(WEAPONS)), random.choice(list(PERKS)),
            random.choice(list(ELEMENTS)))


class BotAI:
    def __init__(self, tank, difficulty=2):
        self.t = tank
        self.preset = DIFF_PRESETS.get(difficulty, DIFF_PRESETS[2])
        self.orbit = 1          # направление орбиты вокруг цели
        self.orbit_t = 0.0      # до смены направления орбиты
        self.fire_delay = 0.3   # небольшая пауза между решениями стрелять
        self.aim_noise = random.uniform(-self.preset["aim"], self.preset["aim"])
        self.unstick_t = 0.0    # время отхода после застревания
        self.unstick_turn = 1   # в какую сторону крутиться при отходе
        # прокачка: сбор бонусов с обязательством (чтобы не дёргаться)
        self.pu_target = None
        self.pu_t = 0.0
        # ручные бустеры
        self.drop_cd = 0.0      # пауза между минами
        self.wall_cd = 0.0      # пауза между стенами
        self.turret_cd = 0.0    # v2.9: пауза между турелями
        self.emp_cd = 0.0       # v3.0: пауза между ЭМИ-зарядами
        self.invisible_t = 0.0  # v3.3: как долго цель прячется в тени
        # v2.1: цель (в 1на1 — игрок, в FFA — ближайший чужой танк)
        self.target = None

    # ---------- помощники ----------

    def _pick_target(self, game):
        """Ближайший живой ЧУЖОЙ танк — в FFA это может быть другой бот,
        в командных режимах (2на2, босс) — только танк чужой команды (v2.2)."""
        t = self.t
        cands = [o for o in game.tanks
                 if o is not t and o.alive
                 and getattr(o, "team", None) != getattr(t, "team", None)]
        if not cands:
            return None
        return min(cands, key=lambda o: (o.x - t.x) ** 2 + (o.y - t.y) ** 2)

    def _threat(self, game):
        """Чужая пуля, которая РЕАЛЬНО опасна: близко и летит точно в нас.
        В FFA опасны пули ЛЮБОГО чужака (бот тоже может подстрелить бота)."""
        t = self.t
        best, best_d = None, 1e9
        for b in game.bullets:
            if b.owner is t:
                continue
            bx, by = t.x - b.x, t.y - b.y
            d = math.hypot(bx, by)
            if d > self.preset["threat"] or d < 1:
                continue
            sp = math.hypot(b.vx, b.vy) + 1e-6
            dot = (bx * b.vx + by * b.vy) / (d * sp)
            if dot > 0.93 and d < best_d:
                best, best_d = b, d
        return best

    def _mine_ahead(self, game):
        """Чужая мина по курсу — объезжаем."""
        t = self.t
        best, best_d = None, 170
        rad = math.radians(t.angle)
        for m in game.mines:
            if m.owner is t:
                continue
            mx, my = t.x - m.x, t.y - m.y
            d = math.hypot(mx, my)
            if d < 1 or d > best_d:
                continue
            dot = (mx * math.cos(rad) + my * math.sin(rad)) / d
            if dot > 0.55:
                best, best_d = m, d
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
        """Видно ли точку с учётом препятствий И дымовых завес."""
        return not game.vision_blocked(self.t.x, self.t.y, x, y)

    def _path_clear(self, game, tx, ty):
        """Проходима ли дорога ПО ШИРИНЕ ТАНКА: проверяем не только луч
        по центру, но и два параллельных луча по бортам. Узкая щель,
        в которую геометрически «влезает» взгляд, но не влезает танк,
        больше не считается дорогой — бот сразу едет в обход."""
        t = self.t
        dx, dy = tx - t.x, ty - t.y
        d = math.hypot(dx, dy)
        if d < 1:
            return True
        ox, oy = -dy / d * (t.radius + 6), dx / d * (t.radius + 6)
        a = game.arena
        if a.line_blocked(t.x, t.y, tx, ty):
            return False
        if a.line_blocked(t.x + ox, t.y + oy, tx + ox, ty + oy):
            return False
        if a.line_blocked(t.x - ox, t.y - oy, tx - ox, ty - oy):
            return False
        return True

    def _pick_powerup(self, game):
        """Выбрать стоящий бонус: ценим ремонт на низком HP, не дарим
        бонус чужакам (если кто-то заметно ближе) и едем только если есть
        проходимая дорога по ширине танка."""
        t = self.t
        others = [o for o in game.tanks if o is not t and o.alive]
        best, best_score = None, 0.0
        for pu in game.powerups:
            d = math.hypot(pu.x - t.x, pu.y - t.y)
            if d > 560:
                continue
            if others:
                dn = min(math.hypot(pu.x - o.x, pu.y - o.y) for o in others)
                if dn * 1.5 < d:
                    continue    # чужак ближе — не подносить же ему
            val = PU_VALUE.get(pu.kind, 1.0)
            if pu.kind == "repair" and t.hp < t.max_hp * 0.5:
                val += 2.5
            if not self._path_clear(game, pu.x, pu.y):
                continue
            score = val * 300.0 / (120.0 + d)
            if score > best_score:
                best, best_score = pu, score
        return best

    # ---------- основное ----------

    def update(self, dt, game):
        t = self.t
        if not t.alive:
            return
        # v2.1: цель — ближайший чужой живой танк (умерла — перевыбираем)
        if self.target is None or not self.target.alive:
            self.target = self._pick_target(game)
        p = self.target
        if p is None or not p.alive:
            return
        if t.frozen_t > 0:
            return  # обездвижен ЭМИ — сидим и страдаем

        self.drop_cd = max(0.0, self.drop_cd - dt)
        self.wall_cd = max(0.0, self.wall_cd - dt)
        self.turret_cd = max(0.0, self.turret_cd - dt)
        self.emp_cd = max(0.0, self.emp_cd - dt)
        self.pu_t = max(0.0, self.pu_t - dt)

        dx, dy = p.x - t.x, p.y - t.y
        dist = math.hypot(dx, dy)
        ang_to = math.degrees(math.atan2(dy, dx))

        self._use_items(game, dist, ang_to)

        # v3.4: ПРИКАЗЫ КОМАНДИРА — «держи позицию» и «за мной» важнее
        # собственного ИИ: движением управляет приказ, но стрелять и
        # пользоваться предметами (мины/стены/турели/ремонт) бот не перестаёт.
        order = getattr(t, "order", None)
        if order in ("hold", "follow"):
            # задавили в стену (или построили её вплотную) — приказ
            # подождёт: сначала выбираемся, как и обычный ИИ
            if (game.arena.circle_collides(t.x, t.y, t.radius * 0.9)
                    or t._stuck > 0.4):
                self.unstick_t = max(self.unstick_t, 0.5)
                self.unstick_turn = random.choice((-1, 1))
                t._stuck = 0.0
            if self.unstick_t > 0:
                self.unstick_t -= dt
                t.control(dt, game.arena, -1, self.unstick_turn,
                          tuple(game.tanks))
                self._try_fire(dt, game, p, ang_to)
                return
        if order == "hold":
            # стоим на месте, только доворачиваем ствол на цель
            d = _ang_diff(ang_to, t.angle)
            turn = 1 if d > 4 else (-1 if d < -4 else 0)
            t.control(dt, game.arena, 0, turn, tuple(game.tanks))
            self._try_fire(dt, game, p, ang_to)
            return
        if order == "follow":
            cmd = getattr(game, "player", None)
            if cmd is not None and cmd.alive and cmd is not t:
                cdx, cdy = cmd.x - t.x, cmd.y - t.y
                cd = math.hypot(cdx, cdy) + 1e-6
                if cd > 250:
                    dd = _ang_diff(math.degrees(math.atan2(cdy, cdx)), t.angle)
                    turn = 1 if dd > 3 else (-1 if dd < -3 else 0)
                    t.control(dt, game.arena, 1 if abs(dd) < 55 else 0,
                              turn, tuple(game.tanks))
                else:
                    # у командира — разворачиваемся на врага и держим оборону
                    dd = _ang_diff(ang_to, t.angle)
                    turn = 1 if dd > 4 else (-1 if dd < -4 else 0)
                    t.control(dt, game.arena, 0, turn, tuple(game.tanks))
                self._try_fire(dt, game, p, ang_to)
                return
            # командир погиб — «за мной» потеряло смысл, воюем сами

        forward, turn = 0, 0
        desired = None

        if self.unstick_t > 0:
            # отход после застревания: пятимся и подворачиваем
            self.unstick_t -= dt
            forward = -1
            turn = self.unstick_turn
        else:
            threat = self._threat(game)
            mine = None if threat is not None else self._mine_ahead(game)
            if threat is not None:
                # уклонение: уход перпендикулярно траектории пули
                desired = math.degrees(math.atan2(threat.vy, threat.vx)) + 90 * self._side(threat)
                forward = 1
            elif mine is not None:
                # отъезд от мины: прямо от неё
                desired = math.degrees(math.atan2(t.y - mine.y, t.x - mine.x))
                forward = 1
            else:
                desired = self._choose_direction(game, ang_to, dist)
                if abs(_ang_diff(desired, t.angle)) < 75:
                    forward = 1
                # v3.2: ШТУРМ — задачи важнее погони:
                # защитник далеко от точки — домой; атакующий не видит
                # цель — давит на захват. v3.3: роли по assault_def/atk_team
                # (игрок мог выбрать АТАКУ и штурмовать сам), и давить на
                # точку в здании можно с любой дистанции, пока цель не видна
                if getattr(game, "is_assault", False):
                    capx, capy = game.cap_xy
                    dp = math.hypot(t.x - capx, t.y - capy)
                    if (t.team == getattr(game, "assault_def_team", 0)
                            and dp > ASSAULT_POINT_R * 2.6 and dist > 320):
                        desired = math.degrees(math.atan2(capy - t.y,
                                                          capx - t.x))
                    elif (t.team == getattr(game, "assault_atk_team", 1)
                          and not self._visible(game, p.x, p.y)
                          and dp > ASSAULT_POINT_R * 1.5):
                        desired = math.degrees(math.atan2(capy - t.y,
                                                          capx - t.x))

            if desired is not None:
                d = _ang_diff(desired, t.angle)
                if abs(d) > 3:
                    turn = 1 if d > 0 else -1

            # упёрлись в препятствие — входим в режим отхода
            if t._stuck > 0.4:
                self.unstick_t = random.uniform(0.4, 0.7)
                self.unstick_turn = random.choice((-1, 1))
                t._stuck = 0.0

        t.control(dt, game.arena, forward, turn, tuple(game.tanks))
        self._try_fire(dt, game, p, ang_to)
        # v3.3: атакующий в ШТУРМЕ крушит чужие и казённые стены, если
        # живых врагов не видно — иначе здание не пройти
        if (getattr(game, "is_assault", False)
                and t.team == getattr(game, "assault_atk_team", 1)):
            self._breach_fire(game, p)

    # ---------- куда едем ----------

    def _use_items(self, game, dist, ang_to=None):
        """Ручные бустеры: мины под догоняющего, стены между собой и целью.
        v3.2: в ШТУРМЕ защитники строят и ЧИНЯТ форт, атакующие бережут
        снаряды для стен."""
        t = self.t
        p = self.target
        if p is None:
            return
        # v3.2: ШТУРМ — поведение защитников (v3.3: сторона обороны —
        # assault_def_team, игрок мог сам стать атакой)
        assault = getattr(game, "is_assault", False)
        if assault and t.team == getattr(game, "assault_def_team", 0):
            capx, capy = game.cap_xy
            dp = math.hypot(t.x - capx, t.y - capy)
            # чиним потрёпанные свои стены, пока враг далеко (dist — до цели)
            if dist > 450:
                game._repair_step(t, True, 1 / 60.0)
            # мины на подходах: ставим под собой, пока стоим у точки
            if (t.mine_carried > 0 and self.drop_cd <= 0
                    and dp < ASSAULT_POINT_R * 2.2):
                if game._place_mine(t):
                    self.drop_cd = 3.0
            # стены форта: ставим наружу от точки (на пути атаки),
            # даже если враг ещё далеко — форт должен вырасти ДО штурма
            if (t.wall_total() > 0 and self.wall_cd <= 0
                    and dp < ASSAULT_POINT_R * 3.2
                    and (dist < 520 or dp < ASSAULT_POINT_R * 1.6)):
                wall_ang = math.degrees(math.atan2(t.y - capy, t.x - capx)) \
                    if dist > 520 else math.degrees(
                        math.atan2(p.y - t.y, p.x - t.x))
                if game._place_barrier(t, wall_ang):
                    self.wall_cd = 2.2
        # мина: цель давит сзади на средней дистанции — кидаем под нос
        if (t.mine_carried > 0 and self.drop_cd <= 0 and 115 < dist < 460):
            rad = math.radians(t.angle)
            dx, dy = p.x - t.x, p.y - t.y
            d = math.hypot(dx, dy) + 1e-6
            dot = (dx * math.cos(rad) + dy * math.sin(rad)) / d
            if dot < -0.25:          # цель именно сзади
                if game._place_mine(t):
                    self.drop_cd = 2.0
        # стена: игрок близко — строим поперёк линии огня (любой ярус,
        # _place_barrier сама возьмёт самую обычную из имеющихся)
        if (t.wall_total() > 0 and self.wall_cd <= 0 and dist < 520):
            if game._place_barrier(t, math.degrees(math.atan2(p.y - t.y, p.x - t.x))):
                self.wall_cd = 3.5
        # v2.9: турель — цель держит дистанцию, ставим станок подальше от себя:
        # он прикроет позицию, пока бот маневрирует
        if (t.turret_charges > 0 and self.turret_cd <= 0 and dist > 420):
            if game._place_turret(t):
                self.turret_cd = 8.0
        # v3.0: ЭМИ-заряд (билд «Связист») — если рядом ДВОЕ и больше
        # чужаков, разряд встает их насмерть: всех заморозит на 2.5 с
        if t.emp_charges > 0 and self.emp_cd <= 0:
            near = [o for o in game.tanks
                    if (o.alive and o is not t
                        and getattr(o, "team", None) != getattr(t, "team", None)
                        and (o.x - t.x) ** 2 + (o.y - t.y) ** 2 < 480 ** 2)]
            if len(near) >= 2 and game._use_emp(t):
                self.emp_cd = 12.0
        # v3.1: «КРУГОВОЙ АД» (билд) — цель вплотную? Одноразовый залп
        # из 45 снарядов во все стороны: в упор почти не увернуться
        if t.nova_charges > 0 and dist < 340 and p.alive:
            game._fire_nova(t)

    def _choose_direction(self, game, ang_to, dist):
        """Выбор направления: ремонт / бонус / фланг / дистанция."""
        t = self.t
        p = self.target   # v2.1: в FFA цель — ближайший чужой танк
        # 1) подбит и видит ремонт ПО ПРОХОДИМОЙ дороге — едем за ним
        if t.hp < t.max_hp * 0.45:
            repair = self._nearest_repair(game)
            if (repair is not None and
                    self._path_clear(game, repair.x, repair.y)):
                return math.degrees(math.atan2(repair.y - t.y, repair.x - t.x))
        # 2) задумались о полезном бонусе (дорога уже проверена в _pick_powerup)
        if self.pu_t > 0 and self.pu_target in game.powerups:
            return math.degrees(math.atan2(self.pu_target.y - t.y,
                                           self.pu_target.x - t.x))
        self.pu_target = self._pick_powerup(game)
        self.pu_t = 1.2 if self.pu_target is not None else 0.0
        if self.pu_target is not None:
            return math.degrees(math.atan2(self.pu_target.y - t.y,
                                           self.pu_target.x - t.x))
        # 3) цель скрыта препятствием, стеной или дымом — заходим с фланга;
        # v3.3: если цель прячется УЖЕ ДОЛГО — рвёмся напролом: орбита
        # может вечнопетлять в «тени» препятствия (найденный зависший
        # паттерн стресс-теста: бот кружит, стоячая цель в тени — вечность)
        if not self._visible(game, p.x, p.y):
            self.invisible_t += 1 / 60.0
            if self.invisible_t > 4.0:
                self.invisible_t = 0.0
                return ang_to               # прямо на цель — выйдем из тени
            return self._flank_angle(ang_to, dist)
        self.invisible_t = 0.0
        # 4) цель видна: сближение / отход / орбита
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

    def _breach_wall(self, game):
        """v3.3: ближайшая НЕ СВОЯ стена-барьер в радиусе 340 px —
        чужая казённая стена здания или личная стена врага."""
        t = self.t
        best, best_d = None, 340.0
        for br in getattr(game, "barriers", []):
            if getattr(br, "team", None) == t.team:
                continue          # свои не крушим
            d = br._dist(t.x, t.y)
            if d < best_d:
                best, best_d = br, d
        return best

    def _breach_fire(self, game, p):
        """v3.3: ПРОЛОМАНИЕ СТЕН — цель не видна, а рядом чужая стена:
        доворачиваем и долбим её снарядами, пока не откроется проход."""
        t = self.t
        if self.fire_delay > 0 or t.cooldown > 0 or not p.alive:
            return
        if self._visible(game, p.x, p.y):
            return                # враг виден — снаряды ему, не стене
        br = self._breach_wall(game)
        if br is None:
            return
        aim = math.degrees(math.atan2(br.y - t.y, br.x - t.x))
        if abs(_ang_diff(aim, t.angle)) < 10:
            game.fire_weapon(t)
            self.fire_delay = random.uniform(self.preset["fire_min"],
                                             max(0.35, self.preset["fire_max"]))

    def _try_fire(self, dt, game, p, ang_to):
        t = self.t
        self.fire_delay -= dt
        if self.fire_delay > 0:
            return
        aim = ang_to + self.aim_noise
        if abs(_ang_diff(aim, t.angle)) < 9 and self._visible(game, p.x, p.y):
            game.fire_weapon(t)
            self.aim_noise = random.uniform(-self.preset["aim"], self.preset["aim"])
            self.fire_delay = random.uniform(self.preset["fire_min"], self.preset["fire_max"])
