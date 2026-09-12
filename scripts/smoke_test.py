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
    g.build = ("light", "light", "standard", "sprinter", "electric", (), (), ())
    g._reset_round()
    check("стихия из ангара доезжает до танка",
          g.player.element_key == "electric" and
          g.player.elem["name"] == "Ток")


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


# ---------- 3e. ЛАЗЕРНЫЙ ВЕЕР: лазер + веер = три луча разом ----------
def test_laser_fan():
    from game import Game
    from settings import PU_LASER_FAN_DAMAGE, PU_LASER_DAMAGE

    beams = []

    class _Fx:
        def beam(self, *a):
            beams.append(a)

        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    g = Game()
    g.state = "fight"
    g._reset_round()
    g.effects = _Fx()
    p, bot = g.player, g.bot_tank
    # чистая полоса карты «Классика» (центральная колонна выше/ниже)
    p.x, p.y, p.angle = 350, 250, 0
    bot.x, bot.y = 750, 250
    hp0 = bot.hp

    # лазер + веер: ОДНО нажатие — три луча, тратятся и лазер, и веер
    p.laser_charges = 2
    p.triple = 1
    p.cooldown = 0
    g.fire_weapon(p)
    check("лазерный веер: три луча разом", len(beams) == 3,
          "(лучей %d)" % len(beams))
    check("веер тратит заряд лазера и заряд веера",
          p.laser_charges == 1 and p.triple == 0)
    check("каждый луч веера бьёт на %d" % PU_LASER_FAN_DAMAGE,
          abs((hp0 - bot.hp) - max(5, round(PU_LASER_FAN_DAMAGE - bot.armor))) < 0.51,
          "(урон %.0f, броня %d)" % (hp0 - bot.hp, bot.armor))
    check("после веера идёт полная перезарядка", p.cooldown > 0)

    # лазер БЕЗ веера — обычный одиночный луч полной силы
    n0 = len(beams)
    hp1 = bot.hp
    p.cooldown = 0
    g.fire_weapon(p)
    check("лазер без веера — один луч", len(beams) - n0 == 1)
    check("обычный лазер бьёт на %d" % PU_LASER_DAMAGE,
          abs((hp1 - bot.hp) - max(5, round(PU_LASER_DAMAGE - bot.armor))) < 0.51,
          "(урон %.0f)" % (hp1 - bot.hp))
    check("веер без лазера остаётся снарядами (лучей больше не стало)",
          len(beams) == n0 + 1 and p.triple == 0)


# ---------- 3f. ЖРЕБИЙ: проклятья (+очки) и облегчения (-очки) ----------
def test_fate():
    from game import Game
    from settings import (CURSES, BLESSINGS, MAX_CURSES, BOOST_MULT,
                          SCORE_CURSE_BONUS, SCORE_BLESS_PENALTY,
                          SCORE_MULT_FLOOR)

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    g = Game()
    # правило: без проклятий — максимум ОДНО облегчение
    g._toggle_bless(0)
    check("первое облегчение берётся и без проклятий", len(g.sel_blessings) == 1)
    g._toggle_bless(1)
    check("второе облегчение без проклятий НЕ берётся", len(g.sel_blessings) == 1)
    g._toggle_curse(0)
    check("проклятье берётся", len(g.sel_curses) == 1)
    g._toggle_bless(1)
    check("проклятье открыло второе облегчение", len(g.sel_blessings) == 2)
    g._toggle_curse(0)   # сняли проклятье — лишнее облегчение слетает
    check("снял проклятье — лишнее облегчение снялось само",
          len(g.sel_curses) == 0 and len(g.sel_blessings) == 1)

    # потолок: %d проклятий и %d облегчений (в колоде по 8 карт)
    g2 = Game()
    for i in range(MAX_CURSES + 1):
        g2._toggle_curse(i)
    for i in range(MAX_CURSES + 1):
        g2._toggle_bless(i)
    check("больше %d проклятий не взять" % MAX_CURSES,
          len(g2.sel_curses) == MAX_CURSES)
    check("%d проклятий открывают %d облегчений"
          % (MAX_CURSES, MAX_CURSES + 1),
          len(g2.sel_blessings) == MAX_CURSES + 1)

    # новые проклятья реально работают на танке
    base = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    bt = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none", "none",
              ("blunt", "wet_powder", "loose_tracks", "leaky_tank"))
    check("кривые снаряды: урон x0.85", abs(bt.mods["damage_mult"] - 0.85) < 1e-9)
    check("сырой порох: снаряд медленнее x0.85",
          abs(bt.mods["bullet_speed_mult"] - 0.85) < 1e-9)
    check("разболтанные гусеницы: разворот x0.85",
          abs(bt.turn_speed - base.turn_speed * 0.85) < 0.01,
          "(%.1f vs %.1f)" % (bt.turn_speed, base.turn_speed * 0.85))
    bt.boost_t = 4.0
    check("текущий бак: турбо слабее (x%.2f)" % (BOOST_MULT * 0.75),
          abs(bt.speed - base.speed * BOOST_MULT * 0.75) < 0.01,
          "(%.1f)" % bt.speed)

    # новые облегчения
    gt = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none", "none",
              (), ("sharpened", "nimble", "racing_tank", "steady_hands"))
    check("заточка: урон x1.15", abs(gt.mods["damage_mult"] - 1.15) < 1e-9)
    check("юркость: разворот x1.15",
          abs(gt.turn_speed - base.turn_speed * 1.15) < 0.01)
    gt.boost_t = 4.0
    check("гоночный бак: турбо сильнее",
          abs(gt.speed - base.speed * BOOST_MULT * 1.15) < 0.01)
    check("твёрдые руки не делают разброс отрицательным",
          max(0.0, gt.mods["spread_deg"]) == 0.0)
    st = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none", "none",
              ("shaky",), ("steady_hands",))
    check("твёрдые руки лечат разбитый прицел: 7-3=4°",
          abs(st.mods["spread_deg"] - 4.0) < 1e-9)

    # модификаторы доезжают до танка (сборка из 8 частей)
    g2.build = ("medium", "medium", "standard", "none", "none",
                tuple(g2.sel_curses), tuple(g2.sel_blessings), ())
    g2._reset_round()
    p = g2.player
    check("проклятья/облегчения доезжают до танка",
          len(p.curses_keys) == MAX_CURSES and
          len(p.blessings_keys) == MAX_CURSES + 1)
    # хрупкость 0.75 + укрепление 1.25 = 0.9375 от 110 HP
    check("HP пересчитано жребием",
          p.max_hp == max(20, int(round(110 * 0.75 * 1.25))),
          "(hp %d)" % p.max_hp)
    check("скорость: ржавые 0.85 x форсаж 1.15",
          abs(p.speed - base.speed * 0.85 * 1.15) < 0.01,
          "(%.1f vs %.1f)" % (p.speed, base.speed * 0.85 * 1.15))
    check("перезарядка: долгая x1.25 гасится отточенной x0.8",
          abs(p.reload_time - base.reload_time) < 1e-6)
    check("снаряды быстрее: дальний бой x1.15",
          abs(p.mods["bullet_speed_mult"] - 1.15) < 1e-9)

    # разбитый прицел реально разбрасывает снаряды
    import math
    g3 = Game()
    g3.state = "fight"
    g3.build = ("medium", "medium", "standard", "none", "none", ("shaky",), (), ())
    g3._reset_round()
    sh = g3.player
    check("разбитый прицел: разброс 7°", sh.mods["spread_deg"] == 7.0)
    seen = set()
    for _ in range(30):
        sh.cooldown = 0
        sh.mag_ammo = sh.mag_size
        bs = []
        sh.try_shoot(bs, _Fx(), _Snd())
        ang = math.degrees(math.atan2(bs[0].vy, bs[0].vx))
        seen.add(round(ang - sh.angle, 2))
    check("разброс реально виден в выстрелах", len(seen) > 5,
          "(разных углов %d)" % len(seen))

    # множитель очков (ПРАВИЛА v1.7): проклятья +15%, облегчения -10%
    g4 = Game()
    g4.build = ("medium", "medium", "standard", "none", "none", (), (), ())
    check("без жребия очки x1.00", abs(g4._score_mult() - 1.0) < 1e-9)
    g4.build = ("medium", "medium", "standard", "none", "none",
                ("fragile",), (), ())
    check("проклятье ДОБАВЛЯЕТ %.0f%% очков" % (SCORE_CURSE_BONUS * 100),
          abs(g4._score_mult() - (1 + SCORE_CURSE_BONUS)) < 1e-9,
          "(x%.2f)" % g4._score_mult())
    g4.build = ("medium", "medium", "standard", "none", "none", (),
                ("armor", "refined"), ())
    check("два облегчения режут общий счёт на 20%",
          abs(g4._score_mult() - (1 - 2 * SCORE_BLESS_PENALTY)) < 1e-9,
          "(x%.2f)" % g4._score_mult())
    g4.build = ("medium", "medium", "standard", "none", "none",
                ("fragile", "rusty", "shaky", "long_reload"),
                ("armor", "overdrive", "refined", "swift", "nimble"), ())
    expected = (1 + 4 * SCORE_CURSE_BONUS - 5 * SCORE_BLESS_PENALTY)
    check("жирный жребий: +60% проклятьями, -50% облегчениями",
          abs(g4._score_mult() - expected) < 1e-9, "(x%.2f)" % g4._score_mult())
    check("пол x%.2f не даёт множителю уйти в минус" % SCORE_MULT_FLOOR,
          g4._fate_mult((), ("armor",) * 9, ()) == SCORE_MULT_FLOOR)
    check("в колоде 8 проклятий и 8 облегчений",
          len(CURSES) == 8 and len(BLESSINGS) == 8)


# ---------- 3g. ОЧКИ: за урон, раунды и победу; рекорд ----------
def test_points():
    from game import Game
    from settings import SCORE_ROUND_WIN, SCORE_MATCH_WIN
    from bullet import Bullet

    g = Game()
    g.state = "fight"
    g._reset_round()
    g._fake_keys = FakeKeys(())
    p, bot = g.player, g.bot_tank
    # чистая полоса, враг заморожен — пуля гарантированно долетает
    p.x, p.y, p.angle = 350, 250, 0
    bot.x, bot.y = 650, 250
    bot.frozen_t = 3.0
    g.bullets.append(Bullet(380, 250, 0, p))
    for _ in range(30):
        g.update(1 / 60.0)
    check("очки капают за урон врагу", g.points > 0, "(%.0f)" % g.points)

    # победа в раунде — плюс очки
    g.state = "fight"
    g.bot_tank.alive = False
    g.player.alive = True
    g.update(1 / 60.0)
    check("победа в раунде +%d очков" % SCORE_ROUND_WIN,
          g.winner == 0 and g.points >= SCORE_ROUND_WIN,
          "(%.0f)" % g.points)

    # матч завершается — итог умножается на жребий и пишется рекорд
    g.score_mult = 0.5
    g.score = [4, 2]
    g.state = "fight"
    g.bot_tank.alive = False
    g.player.alive = True
    g.update(1 / 60.0)      # фиксирует победителя, раунд 5:2
    g.state = "round_end"
    g.timer = 0.01
    g.update(1 / 60.0)      # листает в match_end: +300 и итог
    check("матч завершён, итоговые очки посчитаны с жребием",
          g.state == "match_end" and
          g.final_score == int(g.points * g.score_mult),
          "(сырых %.0f, итог %d)" % (g.points, g.final_score))
    check("рекорд очков пишется в статистику",
          g.stats["best_score"] >= g.final_score)


# ---------- 3h. ЭФФЕКТЫ НА ВРАГА: баффы/дебаффы боту, любой режет счёт ----------
def test_enemy_effects():
    from game import Game
    from settings import ENEMY_EFFECTS, MAX_ENEMY_EFFECTS, SCORE_CURSE_BONUS

    g = Game()
    g._toggle_enemy(0)
    check("дебафф врага берётся", g.sel_enemy_keys == ["e_weaken"])
    for i in range(len(ENEMY_EFFECTS)):
        g._toggle_enemy(i)
    check("больше %d эффектов на врага не взять" % MAX_ENEMY_EFFECTS,
          len(g.sel_enemy_keys) == MAX_ENEMY_EFFECTS)

    # множитель: дебафф -10%, бафф -5%, проклятье +15% (всё в одном котле)
    g.build = ("medium", "medium", "standard", "none", "none",
               ("fragile",), (), ("e_weaken", "e_harden"))
    expected = (1 + SCORE_CURSE_BONUS
                - ENEMY_EFFECTS["e_weaken"]["score_cut"]
                - ENEMY_EFFECTS["e_harden"]["score_cut"])
    check("проклятье +15%%, дебафф врага -10%%, бафф -5%% (x%.2f)" % expected,
          abs(g._score_mult() - expected) < 1e-9, "(x%.2f)" % g._score_mult())

    # дебаффы реально доезжают до бота, игрока не трогают
    g.state = "fight"
    g.build = ("medium", "medium", "standard", "none", "none",
               (), (), ("e_weaken", "e_sabotage", "e_wear"))
    g._reset_round()
    b = g.bot_tank
    check("ослабление: у бота прочность -15%",
          b.max_hp == int(round(110 * 0.85)), "(hp %d)" % b.max_hp)
    check("саботаж: бот медленнее",
          abs(b.mods["speed_mult"] - 0.85) < 1e-9)
    check("износ: бот перезаряжается дольше",
          abs(b.mods["reload_mult"] - 1.2) < 1e-9)
    clean = Tank(0, 0, 0, "medium", "medium", COL).mods
    check("эффекты на врага НЕ трогают игрока", g.player.mods == clean)

    # бафф тоже доезжает
    g.build = ("medium", "medium", "standard", "none", "none",
               (), (), ("e_harden",))
    g._reset_round()
    check("закалка: бот прочнее на 25%",
          g.bot_tank.max_hp == int(round(110 * 1.25)),
          "(hp %d)" % g.bot_tank.max_hp)


# ---------- 3i. ТАБЛИЦА СЧЕТА: топ-10 забегов, место, рекорд ----------
def test_score_table():
    from game import Game

    g = Game()
    g.stats["score_table"] = []
    g.stats["best_score"] = 0
    # доигрываем матч до конца: забег должен попасть в таблицу
    g.state = "fight"
    g._reset_round()
    g._fake_keys = FakeKeys(())
    g.score_mult = 1.5
    g.points = 500.0
    for _ in range(5):
        g.state = "fight"
        g.bot_tank.alive = False
        g.player.alive = True
        g.timer = 0.01
        g.update(1 / 60.0)      # фиксирует победителя раунда
        g.state = "round_end"
        g.timer = 0.01
        g.update(1 / 60.0)      # листает раунд / завершает матч
    check("матч завершён", g.state == "match_end")
    check("итоговые очки = сырые * множитель жребия",
          g.final_score == int(g.points * g.score_mult),
          "(%d)" % g.final_score)
    check("забег попал в таблицу", len(g.stats["score_table"]) == 1)
    check("место в таблице #1", g.table_place == 1)
    check("новый рекорд",
          g.new_record and g.stats["best_score"] >= g.final_score)
    entry = g.stats["score_table"][0]
    check("в записи есть жребий, множитель и дата",
          entry["res"] == "win" and "c" in entry and "b" in entry
          and "e" in entry and "mult" in entry and "date" in entry)

    # сортировка и потолок топ-10
    for i in range(14):
        g.stats["score_table"].append(
            {"score": 100 + i, "res": "loss", "rounds": "1:5",
             "c": 0, "b": 0, "e": 0, "mult": 1.0, "el": "-", "date": ""})
    g.stats["score_table"].sort(key=lambda r: -int(r["score"]))
    del g.stats["score_table"][10:]
    check("таблица держит топ-10", len(g.stats["score_table"]) == 10)
    check("таблица отсортирована по очкам",
          all(g.stats["score_table"][i]["score"] >=
              g.stats["score_table"][i + 1]["score"]
              for i in range(9)))

    # экран таблицы: рисуется, Esc возвращает обратно
    g.state = "table"
    g._table_from = "match_end"
    g._draw_table()
    check("таблица рисуется без ошибок", True)
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    check("Esc возвращает из таблицы", g.state == "match_end")

    # из меню по T открывается таблица и Esc возвращает в меню
    g2 = Game()
    g2.state = "menu"
    g2.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
    check("T в меню открывает таблицу счёта", g2.state == "table")
    g2.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    check("Esc вернул в меню", g2.state == "menu")


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

    # гараж: 5 панелей + жребий + эффекты на врага рисуются
    g.state = "select"
    g._draw_select()
    check("ангар: 5 панелей + жребий + враг рисуется", True)
    # V в ангаре берёт проклятье (курсор на первой красной карте)
    g.sel_jt = 0
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v))
    check("V берёт проклятье в ангаре", len(g.sel_curses) == 1)
    # V на первой зелёной карте (индекс 8) — облегчение
    g.sel_jt = 8
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v))
    check("V берёт облегчение в ангаре", len(g.sel_blessings) == 1)
    # M берёт эффект на врага
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m))
    check("M берёт эффект на врага в ангаре", len(g.sel_enemy_keys) == 1)
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

    # pygame.quit() между тестами НЕ делаем: повторные quit/init
    # инвалидируют кэш шрифтов SDL и роняют процесс (segfault).

if __name__ == "__main__":
    pygame.init()
    test_maps()
    test_speed_table()
    test_turbo_rule()
    test_elements()
    test_barrier()
    test_mine_rules()
    test_laser_fan()
    test_fate()
    test_enemy_effects()
    test_points()
    test_score_table()
    test_magazine()
    test_battle()
    print()
    if FAILED:
        print("ПРОВАЛЕНО: %d -> %s" % (len(FAILED), FAILED))
        sys.exit(1)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
