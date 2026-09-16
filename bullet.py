# -*- coding: utf-8 -*-
"""Снаряды с рикошетами от стен и препятствий + элементальные заряды.
v2.9: РАЗРЫВНЫЕ СНАРЯДЫ (he=True) — при гибели снаряд взрывается осколками:
взрыв задевает всех ЧУЖАКОВ в радиусе (владелец и его союзники целы).
v3.0: ТИПЫ СНАРЯДОВ (shell) — у каждого танка свой тип боеприпаса:
  "std"  — обычный (как всегда);
  "he"   — разрывной: тот же осколочный взрыв, что у зарядов «Р»;
  "ap"   — бронебойный: пробивает броню (pierce), без рикошетов;
  "fire" — зажигательный: на месте гибели снаряда остаётся ОГНЕННАЯ
           ЛУЖА (game подхватывает координату из self.zone).
v3.4: ЗВЁЗДНЫЙ (shell="star") — при попадании разрывается на 5 снарядов
В ФОРМЕ ЗВЕЗДЫ (лучи через 72°): star_children() зовёт игра после гибели.
Осколки слабее, живут недолго (life) и повторно не разрываются."""
import math
import pygame
from settings import (BULLET_SPEED, BULLET_DAMAGE, BULLET_BOUNCES,
                      VAMP_HEAL_RATIO, HE_SPLASH_RADIUS, HE_SPLASH_DAMAGE,
                      STAR_SHARDS, STAR_SHARD_DAMAGE, STAR_SHARD_SPEED_MULT,
                      STAR_SHARD_LIFE, STAR_SHARD_GRACE)

ELEMENT_COLORS = {
    "fire":     (255, 110, 0),
    "water":    (80, 170, 255),
    "earth":    (180, 130, 60),
    "electric": (255, 240, 110),
    "air":      (190, 235, 255),
    "ice":      (120, 255, 255),
    "poison":   (150, 255, 60),
    "vamp":     (255, 80, 160),
}


class Bullet:
    def __init__(self, x, y, angle, owner, damage=BULLET_DAMAGE, speed_mult=1.0,
                 element=None, bounces=None, big=False, he=False,
                 shell="std", pierce=False, star=False, life=None,
                 no_hit_t=0.0):
        rad = math.radians(angle)
        self.x = float(x)
        self.y = float(y)
        v = BULLET_SPEED * speed_mult
        self.vx = math.cos(rad) * v
        self.vy = math.sin(rad) * v
        self.owner = owner
        self.damage = damage
        # рикошеты: базовые из настроек; перк «Рикошет» добавляет свои
        self.bounces = BULLET_BOUNCES if bounces is None else bounces
        self.age = 0.0
        self.dead = False
        self.element = element
        # v2.9: разрывной снаряд — взрывается осколками при гибели
        self.he = he
        # v3.0: тип снаряда (std/he/ap/fire) и пробой брони (бронебойный)
        self.shell = shell
        self.pierce = bool(pierce) or shell == "ap"
        if he or shell == "he":
            self.he = True
        # v3.0: зажигательный — куда упасть огненной луже при гибели
        # (None — лужи не будет); game читает это поле после гибели снаряда
        self.zone = None
        # v3.4: звёздный разрыв — только у ЦЕНТРАЛЬНОГО снаряда залпа
        # (у дробовика осколки-звезда лишь у первой дробины, иначе артобстрел)
        self.star_split = bool(star)
        self._split_done = False
        # v3.4: ограничение дальности осколков (None — летит до стены)
        self.life = life
        # v3.4: первые мгновения осколки не бьют танки (рождаются в цели)
        self.no_hit_t = no_hit_t
        self.color = ELEMENT_COLORS.get(element, owner.color)
        if self.he:
            self.color = (255, 120, 50)   # разрывные видны своей оранжевой вспышкой
        if shell == "ap":
            self.color = (110, 255, 235)  # бронебойный — ледяной циан
        elif shell == "fire":
            self.color = (255, 70, 40)    # зажигательный — алый пламень
        elif shell == "star":
            self.color = (255, 226, 90)   # v3.4: звёздный — золотая звезда
        self.big = big or speed_mult > 1.1   # тяжёлые снаряды рисуются крупнее
        self.prev = (self.x, self.y)  # точка в начале кадра (для шлейфа и отскока)

    def _he_blast(self, tanks, effects, sounds, direct=None):
        """Осколочный взрыв разрывного снаряда (v2.9): всех ЧУЖИХ в радиусе
        (кроме получившего прямое попадание — тот уже отболел) задевает
        HE_SPLASH_DAMAGE. Свои (та же команда) и сам владелец целы."""
        if not self.he:
            return
        effects.ring(self.x, self.y, (255, 120, 50), HE_SPLASH_RADIUS, 0.35)
        effects.burst(self.x, self.y, (255, 120, 50), 14, 260, 0.4, 4)
        effects.shake(3, 0.15)
        sounds.play("explode")
        oteam = getattr(self.owner, "team", None)
        for t in tanks:
            if t is direct or not t.alive or t is self.owner:
                continue
            if oteam is not None and getattr(t, "team", None) == oteam:
                continue   # свои осколками не задеваем
            if (t.x - self.x) ** 2 + (t.y - self.y) ** 2 < HE_SPLASH_RADIUS ** 2:
                t.take_damage(HE_SPLASH_DAMAGE, effects, sounds)
                effects.float_text(t.x, t.y - 44, "ОСКОЛКИ", (255, 120, 50))

    def star_children(self):
        """v3.4: ЗВЁЗДНЫЙ СНАРЯД — 5 осколков ЗВЕЗДОЙ (лучи через 72°).
        Игра вызывает ПОСЛЕ гибели снаряда (стена, танк, барьер, турель).
        Осколки слабее и медленнее, живут STAR_SHARD_LIFE секунд,
        повторно не разрываются и первые мгновения не бьют танки
        (рождаются внутри цели)."""
        if self._split_done:
            return []
        self._split_done = True
        base = math.degrees(math.atan2(self.vy, self.vx))
        out = []
        for i in range(STAR_SHARDS):
            a = base + i * 360.0 / STAR_SHARDS
            rad = math.radians(a)
            # рождаются чуть впереди точки попадания — вдоль своего луча
            sx = self.x + math.cos(rad) * 8.0
            sy = self.y + math.sin(rad) * 8.0
            out.append(Bullet(sx, sy, a, self.owner,
                              damage=STAR_SHARD_DAMAGE,
                              speed_mult=STAR_SHARD_SPEED_MULT, bounces=1,
                              life=STAR_SHARD_LIFE, no_hit_t=STAR_SHARD_GRACE))
        return out

    def update(self, dt, arena, tanks, effects, sounds):
        self.age += dt
        # v3.4: осколки звезды живут недолго — угасли, не долетев
        if self.life is not None and self.age >= self.life:
            effects.burst(self.x, self.y, self.color, 4, 90, 0.2, 2)
            self.star_split = False   # угас вхолостую — звезды не будет
            self.dead = True
            return
        self.prev = (self.x, self.y)
        steps = 3  # подшаги, чтобы не проскочить препятствие за кадр
        for _ in range(steps):
            if self.dead:
                return
            self.x += self.vx * dt / steps
            self.y += self.vy * dt / steps

            # ----- столкновение со стенами и препятствиями -----
            for r in arena.rects:
                if r.collidepoint(self.x, self.y):
                    if self.bounces > 0:
                        self.bounces -= 1
                        # определяем сторону попадания по минимальной глубине
                        dl = self.x - r.left
                        dr = r.right - self.x
                        dtp = self.y - r.top
                        db = r.bottom - self.y
                        m = min(dl, dr, dtp, db)
                        if m in (dl, dr):
                            self.vx = -self.vx
                            self.x = self.prev[0]
                        else:
                            self.vy = -self.vy
                            self.y = self.prev[1]
                        effects.burst(self.x, self.y, self.color, 5, 130, 0.25, 3)
                        sounds.play("ric")
                    else:
                        effects.burst(self.x, self.y, self.color, 6, 150, 0.3, 3)
                        if self.shell == "fire":
                            self.zone = (self.x, self.y)   # лужа и у стены
                        self._he_blast(tanks, effects, sounds)   # разрыв у стены
                        self.dead = True
                    break
            if self.dead:
                return

            # ----- попадание в танк -----
            for t in tanks:
                if not t.alive:
                    continue
                if t is self.owner and self.age < 0.25:
                    continue  # даём вылететь из своего ствола
                if self.age < self.no_hit_t:
                    continue  # v3.4: осколки звезды рождаются в цели — импа не бьём
                # КОМАНДНЫЕ РЕЖИМЫ (v2.2): своих не бьём — снаряд пролетает
                # сквозь союзника (в FFA у каждого танка своя команда)
                if (t is not self.owner
                        and getattr(t, "team", None) == getattr(self.owner, "team", None)):
                    continue
                if (t.x - self.x) ** 2 + (t.y - self.y) ** 2 < (t.radius + 4) ** 2:
                    t.take_damage(self.damage, effects, sounds,
                                  pierce=self.pierce)
                    # РАЗРЫВНЫЕ (v2.9): осколки по чужакам рядом (цель исключена —
                    # прямое попадание уже отболело)
                    self._he_blast(tanks, effects, sounds, direct=t)
                    # ПРАВИЛО СВОЕЙ СТИХИИ: земля/ток/вода/лёд/яд не действуют
                    # на того, кто выпустил снаряд (рикошет не замедляет себя);
                    # урон при само-попадании честно остаётся
                    if self.element and t is not self.owner:
                        t.apply_element(self.element, self.vx, self.vy,
                                        arena, effects, sounds)
                    # ВАМПИРИЗМ: стрелявшему возвращается часть урона снаряда
                    if (self.element == "vamp" and self.owner is not None
                            and self.owner is not t and self.owner.alive):
                        self.owner.heal(
                            max(1, int(round(self.damage * VAMP_HEAL_RATIO))),
                            effects)
                    effects.burst(self.x, self.y, self.color, 10, 220, 0.4, 3)
                    if self.shell == "fire":
                        self.zone = (self.x, self.y)   # огненная лужа на месте попадания
                    self.dead = True
                    return

    def draw(self, surf, ox=0, oy=0):
        x, y = int(self.x + ox), int(self.y + oy)
        px, py = int(self.prev[0] + ox), int(self.prev[1] + oy)
        r = 5 if self.big else 4
        pygame.draw.line(surf, self.color, (px, py), (x, y), r)   # шлейф
        pygame.draw.circle(surf, self.color, (x, y), r)
        pygame.draw.circle(surf, (255, 255, 255), (x, y), max(2, r - 2))
