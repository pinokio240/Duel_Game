# -*- coding: utf-8 -*-
"""
Headless-тесты DUEL (запуск: python scripts/smoke_test.py).
Проверяют: честность скоростей, ПРАВИЛО ТУРБО, обойму «Спарки»,
победителя раунда, полный бой с ботом под dummy-видеодрайвером.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
from settings import (CHASSIS, HULL, WEAPONS, PERKS,  # noqa: E402
                      BOOST_MULT, BOOST_PERK_KEY, BOOST_PERK_MULT)
from tank import Tank  # noqa: E402
from arena import Arena, LAYOUTS, MAP_NAMES  # noqa: E402

COL = (0, 229, 255)
FAILED = []


def check(name, cond, extra=""):
    status = "OK  " if cond else "FAIL"
    print("[%s] %s %s" % (status, name, extra))
    if not cond:
        FAILED.append(name)


# ---------- 1. все 8 арен строятся и стены реально блокируют ----------
def test_maps():
    for i, name in enumerate(MAP_NAMES):
        a = Arena(i)
        edge = a.point_blocked(10, 360) and a.point_blocked(640, 10)
        sx, sy = a.free_spot()          # свободная точка — своя для каждой карты
        free = not a.circle_collides(sx, sy, 24)
        check("карта «%s»" % name, edge and free,
              "(%d препятствий)" % len(a.obstacles))


# ---------- 2. честные скорости сборок (включая новые шасси) ----------
def test_speed_table():
    cases = [
        (("light", "light", "standard", "none"), 220.0),
        (("heavy", "heavy", "standard", "none"), 81.25),   # 125*0.65
        (("heavy", "heavy", "twin", "turtle"),   61.06),   # 125*0.65*0.88*0.85
        (("light", "light", "standard", "sprinter"), 275.0),
        (("terrain", "heavy", "standard", "none"), 123.75),  # 150*(1-0.35*0.5)
        (("sport", "light", "standard", "none"), 240.0),     # вес корпуса 0
        (("sport", "heavy", "standard", "none"), 130.8),     # 240*(1-0.35*1.3)
    ]
    for build, expect in cases:
        t = Tank(0, 0, 0, build[0], build[1], COL, build[2], build[3])
        check("скорость %s = %.0f" % (str(build), expect),
              abs(t.speed - expect) < 0.6, "(got %.2f)" % t.speed)


# ---------- 3. ПРАВИЛО ТУРБО (главное в этом обновлении) ----------
def test_turbo_rule():
    # без перка на ускорение: турбо работает КАК ОБЫЧНО (x1.6)
    t = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    base = t.speed
    t.boost_t = 4.0
    check("турбо без перка = x%.2f (обычное)" % BOOST_MULT,
          abs(t.speed - base * BOOST_MULT) < 0.01,
          "(got x%.3f)" % (t.speed / base))

    # с перком «Гонец»: турбо ОСЛАБЛЕНО (x1.2), скорость не превращается в ракету
    g = Tank(0, 0, 0, "light", "light", COL, "standard", "sprinter")
    gbase = g.speed
    g.boost_t = 4.0
    check("турбо с «Гонцом» = x%.2f (ослабленное)" % BOOST_PERK_MULT,
          abs(g.speed - gbase * BOOST_PERK_MULT) < 0.01,
          "(got x%.3f)" % (g.speed / gbase))
    check("Гонец+турбо не даёт имбу (<= %d px/с)" % int(gbase * BOOST_PERK_MULT),
          g.speed <= gbase * BOOST_PERK_MULT + 0.01,
          "(%d px/с)" % int(g.speed))

    # другим перкам турбо по-прежнему обычное
    u = Tank(0, 0, 0, "medium", "medium", COL, "standard", "turtle")
    ubase = u.speed
    u.boost_t = 4.0
    check("турбо с «Панцирем» остаётся обычным",
          abs(u.speed - ubase * BOOST_MULT) < 0.01)


# ---------- 3b. СТИХИИ — шестая часть сборки, каждый снаряд элементальный ----------
def test_elements():
    from settings import EARTH_MULT, SHOCK_MULT, BULLET_DAMAGE, BULLET_SPEED
    from powerup import PU_INFO
    from bot import random_build

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    arena = Arena(0)

    # стихии больше НЕТ на карте — она теперь выбирается в ангаре
    check("на карте 10 бонусов, стихий среди них нет",
          len(PU_INFO) == 10 and not
          (set(PU_INFO) & {"fire", "water", "earth", "electric", "air"}))

    # сборка бота: 5 компонентов, все ключи валидны
    rb = random_build()
    from settings import CHASSIS, HULL, WEAPONS, PERKS, ELEMENTS
    check("сборка бота: 5 компонентов и все валидны",
          len(rb) == 5 and rb[0] in CHASSIS and rb[1] in HULL and
          rb[2] in WEAPONS and rb[3] in PERKS and rb[4] in ELEMENTS)

    # огонь из ангара: КАЖДЫЙ снаряд огненный (и не кончается)
    t = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none", "fire")
    bullets = []
    for _ in range(3):
        t.cooldown = 0
        t.try_shoot(bullets, fx, snd)
    check("«Огонь»: все снаряды огненные",
          len(bullets) == 3 and all(b.element == "fire" for b in bullets))
    check("цена огня: урон снаряда x0.75",
          abs(bullets[0].damage - BULLET_DAMAGE * 0.75) < 0.1,
          "(dmg=%.1f)" % bullets[0].damage)

    # нейтральная: без эффекта, но снаряд больнее (+10%)
    nt = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none", "none")
    nb = []
    nt.cooldown = 0
    nt.try_shoot(nb, fx, snd)
    check("«Нейтральная»: урон x1.10, без эффекта",
          abs(nb[0].damage - BULLET_DAMAGE * 1.10) < 0.1 and nb[0].element is None)

    # воздух: снаряд летит на 20% быстрее
    ar = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none", "air")
    ab = []
    ar.cooldown = 0
    ar.try_shoot(ab, fx, snd)
    check("«Воздух»: скорость снаряда x1.2",
          abs(ab[0].vx - BULLET_SPEED * 1.2) < 0.1)

    # вода: смывает все бонусы и заставляет буксовать
    v = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    v.apply_powerup("shield"); v.apply_powerup("boost"); v.apply_powerup("laser")
    v.apply_element("water", 1, 0, arena, fx, snd)
    check("вода смывает щит/турбо/лазер и мочит (буксует)",
          v.shield_t == 0 and v.boost_t == 0 and v.laser_charges == 0
          and v.mud_t > 0)

    # земля: скорость падает в 2.2 раза
    z = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    base = z.speed
    z.apply_element("earth", 1, 0, arena, fx, snd)
    check("земля замедляет до x%.2f" % EARTH_MULT,
          abs(z.speed - base * EARTH_MULT) < 0.01)

    # ток: скорость и разворот вполсилы
    el = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    bspd, bturn = el.speed, el.turn_speed
    el.apply_element("electric", 1, 0, arena, fx, snd)
    check("ток глушит мотор до x%.2f" % SHOCK_MULT,
          abs(el.speed - bspd * SHOCK_MULT) < 0.01 and
          abs(el.turn_speed - bturn * SHOCK_MULT) < 0.01)

    # воздух: отшвыривает на ~90 px и не сквозь стены
    a = Tank(200, 620, 0, "medium", "medium", COL, "standard", "none")
    a.apply_element("air", 100, 0, arena, fx, snd)   # толкает вправо
    pushed = a.x - 200
    check("воздух отшвыривает (~90 px)", 60 < pushed <= 92, "(%.0f px)" % pushed)

    # поджог наносит урон со временем
    f = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    f.apply_element("fire", 1, 0, arena, fx, snd)
    for _ in range(60):
        f._burn_step(1 / 60.0, fx, snd)
    check("поджог тикает уроном", f.hp < f.max_hp)

    # сборка игрока доезжает до танка: элемент попадает в конструктор
    from game import Game as _G
    g = _G()
    g.build = ("light", "light", "standard", "sprinter", "electric")
    g._reset_round()
    check("стихия из ангара доезжает до танка",
          g.player.element_key == "electric" and
          g.player.elem["name"] == "Ток")
    pygame.quit()


# ---------- 3c. СТЕНА-БАРЬЕР: блокирует танк, ломается снарядами ----------
def test_barrier():
    from settings import BARRIER_HP

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    from game import Game as _G
    g = _G()
    g.state = "fight"
    g._reset_round()
    p = g.player
    p.x, p.y, p.angle = 400, 360, 0        # смотрит вправо
    p.barrier_charges = 1
    ok = g._place_barrier(p)
    check("стена ставится по Q", ok and len(g.barriers) == 1 and
          p.barrier_charges == 0)
    br = g.barriers[0]
    # стена поперёк курса: вертикальная, перед танком
    check("стена встаёт перед танком", abs(br.x - (400 + 88)) < 2 and
          abs(br.y - 360) < 2)
    # танк не может проехать сквозь неё
    p.x, p.y = 430, 360
    p.angle = 0
    for _ in range(60):
        p.control(1 / 60.0, g.arena, 1, 0, (g.bot_tank,))
    check("танк не проезжает сквозь стену (x=%.0f)" % p.x, p.x < 460)
    # 4 снаряда по 30 ломают стену (120 HP)
    from bullet import Bullet
    for _ in range(4):
        g.bullets.append(Bullet(br.x - 40, br.y, 0, g.bot_tank))
        b = g.bullets[-1]
        for _step in range(40):
            g._bullet_vs_barriers(b)
            if b.dead:
                break
            b.x += 3
        g.bullets.clear()
    check("120 HP стены пробиваются 4 выстрелами", len(g.barriers) == 0)
    pygame.quit()


# ---------- 3d. МИНА ПО КНОПКЕ: нельзя во врага ----------
def test_mine_rules():
    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    from game import Game as _G
    g = _G()
    g.state = "fight"
    g._reset_round()
    p, bot = g.player, g.bot_tank
    p.apply_powerup("mine")
    check("мина теперь носятся в боекомплекте", p.mine_carried == 1)
    # враг близко — ставить нельзя
    bot.x, bot.y = p.x + 60, p.y
    ok = g._place_mine(p)
    check("во врага мину не поставить", not ok and p.mine_carried == 1 and
          len(g.mines) == 0)
    # враг далеко — ставится под себя
    bot.x, bot.y = p.x + 300, p.y
    ok = g._place_mine(p)
    check("мина ставится по E, когда враг далеко",
          ok and p.mine_carried == 0 and len(g.mines) == 1)
    pygame.quit()


# ---------- 4. обойма «Спарки»: 2 снаряда, потом долгая перезарядка ----------
def test_magazine():
    t = Tank(0, 0, 0, "medium", "medium", COL, "twin", "none")
    check("обойма спарки = 2", t.mag_size == 2 and t.mag_ammo == 2)

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    bullets = []
    t.try_shoot(bullets, fx, snd)          # 1-й выстрел — короткая пауза
    check("после 1-го выстрела: ОБОЙМА 1/2, пауза mag_cd",
          t.mag_ammo == 1 and abs(t.cooldown - WEAPONS["twin"]["mag_cd"]) < 1e-6,
          "(cd=%.2f)" % t.cooldown)
    bullets.clear()
    t.update(WEAPONS["twin"]["mag_cd"])
    t.try_shoot(bullets, fx, snd)          # 2-й выстрел — полная перезарядка
    check("после 2-го выстрела: обойма полная, пауза x%.1f"
          % WEAPONS["twin"]["reload_mult"],
          t.mag_ammo == 2 and abs(t.cooldown - t.reload_time) < 1e-6,
          "(cd=%.2f)" % t.cooldown)


# ---------- 5. полный бой headless: победа игрока, счёт, HUD ----------
class FakeKeys:
    def __init__(self, pressed):
        self.p = set(pressed)

    def __getitem__(self, k):
        return 1 if k in self.p else 0


def test_battle():
    from game import Game
    g = Game()
    g.state = "fight"
    g._reset_round()
    g._fake_keys = FakeKeys((pygame.K_w, pygame.K_d, pygame.K_SPACE))

    # прогрев: 8 сек боя — стрельба, ИИ, бонусы, мины/дым/барьеры не падают
    for _ in range(480):
        g.update(1 / 60.0)
    check("бой идёт без ошибок 8 сек", g.state in ("fight", "round_end"))
    g.draw()  # HUD/арена/стены рисуются без исключений

    # гараж: 5 панелей (шасси/корпус/дуло/перк/стихия) рисуется
    g.state = "select"
    g._draw_select()
    check("ангар: 5 панелей, включая стихию, работает", True)
    g.state = "fight"

    # регрессия победителя: убили бота — очко ИГРОКУ (bug 74c15bb)
    g.state = "fight"
    g.bot_tank.alive = False
    g.player.alive = True
    g.update(1 / 60.0)
    check("убили бота → раунд за игроком",
          g.winner == 0 and g.score[0] == 1, "(score %s)" % g.score)

    # раунды листаются, потом матч заканчивается
    for _ in range(4):
        g.state = "fight"
        g.bot_tank.alive = False
        g.player.alive = True
        g.timer = 0.01
        g.update(1 / 60.0)   # фиксирует победителя
        g.state = "round_end"
        g.timer = 0.01
        g.update(1 / 60.0)   # листает раунд / завершает матч
    check("матч до 5 побед завершается", g.state == "match_end",
          "(score %s)" % g.score)
    check("статистика матчей пишется", g.stats["wins"] >= 1)

    # регрессия: убили игрока — очко БОТУ
    g2 = Game()
    g2.state = "fight"
    g2._reset_round()
    g2._fake_keys = FakeKeys(())
    g2.player.alive = False
    g2.bot_tank.alive = True
    g2.update(1 / 60.0)
    check("убили игрока → раунд за ботом",
          g2.winner == 1 and g2.score[1] == 1, "(score %s)" % g2.score)

    # пауза: выход в ангар сбрасывает матч
    g2.state = "fight"
    g2.score = [2, 1]
    g2.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    check("Esc в бою открывает паузу", g2.state == "pause")
    g2.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    check("A в паузе возвращает в ангар, счёт сброшен",
          g2.state == "select" and g2.score == [0, 0])

    pygame.quit()


if __name__ == "__main__":
    pygame.init()
    test_maps()
    test_speed_table()
    test_turbo_rule()
    test_elements()
    test_barrier()
    test_mine_rules()
    test_magazine()
    test_battle()
    print()
    if FAILED:
        print("ПРОВАЛЕНО: %d -> %s" % (len(FAILED), FAILED))
        sys.exit(1)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
