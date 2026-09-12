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
          (set(PU_INFO) & {"fire", "water", "earth", "electric", "air",
                           "ice", "poison", "vamp"}))

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

    # ВОДА ТУШИТ ОГОНЬ (v2.2): горящий после огня гаснет от воды
    fw = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    fw.apply_element("fire", 1, 0, arena, fx, snd)
    check("огонь поджигает (горит)", fw.burn_t > 0)
    fw.apply_powerup("shield")
    fw.apply_element("water", 1, 0, arena, fx, snd)
    check("ВОДА ТУШИТ горящего (пожар снят) и смывает щит",
          fw.burn_t == 0 and fw.shield_t == 0 and fw.mud_t > 0)

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
    # (y=450 — чистая полоса «Классики» при масштабе 1.75: блоки выше/ниже)
    a = Tank(200, 450, 0, "medium", "medium", COL, "standard", "none")
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
    g.arena = Arena(0)             # фиксированная «Классика» — тест геометрии
    p = g.player
    p.x, p.y, p.angle = 400, 540, 0        # смотрит вправо (мир 2240x1260 с v2.4)
    p.barrier_charges = 1
    ok = g._place_barrier(p)
    check("стена ставится по Q", ok and len(g.barriers) == 1 and
          p.barrier_charges == 0)
    br = g.barriers[0]
    # стена поперёк курса: вертикальная, перед танком
    check("стена встаёт перед танком", abs(br.x - (400 + 88)) < 2 and
          abs(br.y - 540) < 2)
    # танк не может проехать сквозь неё
    p.x, p.y = 430, 540
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
    g.arena = Arena(0)             # фиксированная карта — тест геометрии
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
    # чистая полоса карты «Классика» (мир 2752x1548: блоки выше/ниже)
    g.arena = Arena(0)
    p.x, p.y, p.angle = 350, 540, 0
    bot.x, bot.y = 750, 540
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
    from game import Game, CR_KEYS, BL_KEYS
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

    # потолок v2.0: можно взять ВСЕ 8 проклятий и ВСЕ 8 облегчений
    g2 = Game()
    for i in range(len(CR_KEYS)):
        g2._toggle_curse(i)
    check("все %d проклятий берутся разом" % len(CR_KEYS),
          len(g2.sel_curses) == MAX_CURSES == len(CR_KEYS))
    for i in range(len(BL_KEYS)):
        g2._toggle_bless(i)
    check("с 8 проклятьями потолок облегчений 9 — берутся все 8",
          len(g2.sel_blessings) == len(BL_KEYS))

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
          len(p.blessings_keys) == len(BL_KEYS))
    # хрупкость 0.75 + укрепление 1.25 = 0.9375 от 110 HP
    check("HP пересчитано жребием",
          p.max_hp == max(20, int(round(110 * 0.75 * 1.25))),
          "(hp %d)" % p.max_hp)
    check("скорость: ржавые 0.85 x форсаж 1.15",
          abs(p.speed - base.speed * 0.85 * 1.15) < 0.01,
          "(%.1f vs %.1f)" % (p.speed, base.speed * 0.85 * 1.15))
    check("перезарядка: долгая x1.25 гасится отточенной x0.8",
          abs(p.reload_time - base.reload_time) < 1e-6)
    check("снаряды: сырой порох 0.85 гасится дальним боем 1.15",
          abs(p.mods["bullet_speed_mult"] - 0.85 * 1.15) < 1e-9)

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
    g.arena = Arena(0)
    p.x, p.y, p.angle = 350, 540, 0
    bot.x, bot.y = 650, 540
    bot.frozen_t = 3.0
    g.bullets.append(Bullet(380, 540, 0, p))
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


# ---------- 3h. ЭФФЕКТЫ НА ВРАГА: дебаффы режут счёт, баффы ДОБАВЛЯЮТ ----------
def test_enemy_effects():
    from game import Game
    from settings import ENEMY_EFFECTS, SCORE_CURSE_BONUS

    g = Game()
    g._toggle_enemy(0)
    check("дебафф врага берётся", g.sel_enemy_keys == ["e_weaken"])
    g2 = Game()
    for i in range(len(ENEMY_EFFECTS)):
        g2._toggle_enemy(i)
    check("ЛИМИТА НЕТ: все %d эффектов на врага берутся разом (v2.2)"
          % len(ENEMY_EFFECTS),
          len(g2.sel_enemy_keys) == len(ENEMY_EFFECTS))

    # множитель: дебафф -10%, бафф врага +10%, проклятье +15% (всё в одном котле)
    g.build = ("medium", "medium", "standard", "none", "none",
               ("fragile",), (), ("e_weaken", "e_harden"))
    expected = (1 + SCORE_CURSE_BONUS
                - ENEMY_EFFECTS["e_weaken"]["score_cut"]
                + ENEMY_EFFECTS["e_harden"]["score_bonus"])
    check("проклятье +15%%, дебафф врага -10%%, бафф врага +10%% (x%.2f)" % expected,
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

    # свежие эффекты (v1.9) тоже доезжают до бота
    g.build = ("medium", "medium", "standard", "none", "none",
               (), (), ("e_rust", "e_blind", "e_powder", "e_heavy"))
    g._reset_round()
    b = g.bot_tank
    check("ржавые гусеницы: бот ворочается еле-еле",
          abs(b.mods["turn_mult"] - 0.85) < 1e-9)
    check("мутный прицел: у бота разброс +6°",
          abs(b.mods["spread_deg"] - 6.0) < 1e-9)
    check("сырой порох: снаряды бота ползут",
          abs(b.mods["bullet_speed_mult"] - 0.85) < 1e-9)
    check("толстые снаряды: бот бьёт больнее",
          abs(b.mods["damage_mult"] - 1.15) < 1e-9)
    # берсерк: сразу два мода и самая жирная цена
    g.build = ("medium", "medium", "standard", "none", "none",
               (), (), ("e_frenzy",))
    g._reset_round()
    b = g.bot_tank
    check("берсерк: бот крепкий и злой",
          abs(b.mods["hp_mult"] - 1.15) < 1e-9
          and abs(b.mods["damage_mult"] - 1.10) < 1e-9)
    check("берсерк даёт +15%% очков",
          abs(g._fate_mult((), (), ("e_frenzy",)) - 1.15) < 1e-9)
    check("в колоде врага 6 дебаффов и 6 баффов",
          sum(1 for e in ENEMY_EFFECTS.values() if "score_cut" in e) == 6
          and sum(1 for e in ENEMY_EFFECTS.values()
                  if "score_bonus" in e) == 6)


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

# ---------- 6. мышь: клик по карточкам, жребию и кнопкам ----------
def test_mouse():
    from game import Game, CH_KEYS, PK_KEYS, EL_KEYS, CR_KEYS
    g = Game()

    def click(ga, kind, data=None):
        ga.draw()   # кликабельные зоны пересобираются на каждом кадре
        for rect, kd, dta in ga._click_zones:
            if kd == kind and (data is None or dta == data):
                ga.on_click(rect.center)
                return
        raise AssertionError("нет кликабельной зоны %s(%s)" % (kind, data))

    # меню: сложность и большие кнопки
    g.state = "menu"
    click(g, "menu_diff", 3)
    check("клик по «3 Сложно» выбирает сложность", g.difficulty == 3)
    click(g, "menu_start")
    check("клик «В АНГАР» открывает ангар", g.state == "select")

    # ангар: клик по карточке = выбрать её
    click(g, "ch", 0)
    check("клик по карточке шасси выбирает его", g.sel_ch == 0)
    click(g, "pk", 2)
    check("клик по карточке перка выбирает его", g.sel_pk == 2)
    click(g, "el", 4)
    check("клик по карточке стихии выбирает её", g.sel_el == 4)

    # жребий: клик взять/снять + лимиты облегчений
    click(g, "fate", 0)
    check("клик берёт проклятье", len(g.sel_curses) == 1)
    click(g, "fate", 8)
    click(g, "fate", 9)
    check("с одним проклятьем кликами взяты 2 облегчения",
          len(g.sel_blessings) == 2)
    click(g, "fate", 0)   # снять проклятье — лишние облегчения снимутся сами
    check("проклятье снято кликом, облегчений осталось 1",
          len(g.sel_curses) == 0 and len(g.sel_blessings) == 1)
    click(g, "enemy", 1)
    check("клик берёт эффект НА ВРАГА", len(g.sel_enemy_keys) == 1)

    # кнопка «В БОЙ»: сборка собирается, матч стартует
    click(g, "go_fight")
    check("клик «В БОЙ» стартует матч", g.state == "intro")
    check("в build попали кликнутые шасси/перк/стихия",
          g.build[0] == CH_KEYS[0] and g.build[3] == PK_KEYS[2]
          and g.build[4] == EL_KEYS[4])

    # пауза: кнопки ПРОДОЛЖИТЬ / АНГАР
    g.state = "pause"
    click(g, "p_resume")
    check("клик «ПРОДОЛЖИТЬ» снимает с паузы", g.state == "fight")
    g.state = "pause"
    click(g, "to_garage")
    check("клик «АНГАР» в паузе: счёт сброшен",
          g.state == "select" and g.score == [0, 0])

    # конец матча: кнопки ТАБЛИЦА / МЕНЮ
    g2 = Game()
    g2.state = "fight"
    g2._reset_round()
    g2.state = "match_end"
    click(g2, "open_table", "match_end")
    check("клик «ТАБЛИЦА» с конца матча открывает таблицу",
          g2.state == "table" and g2._table_from == "match_end")
    click(g2, "table_back")
    check("клик «НАЗАД» возвращает с таблицы", g2.state == "match_end")
    click(g2, "me_menu")
    check("клик «МЕНЮ» с конца матча", g2.state == "menu")

    # таблица из меню и обратно
    g.state = "menu"
    click(g, "open_table", "menu")
    check("клик «ТАБЛИЦА СЧЕТА» в меню", g.state == "table")
    click(g, "table_back")
    check("клик «НАЗАД» вернул в меню", g.state == "menu")
    check("карт проклятий в жребии по-прежнему 8", len(CR_KEYS) == 8)


# ---------- 3j. НОВЫЕ ДУЛА: дробовик, пулемёт, гаубица ----------
def test_new_weapons():
    import math
    from settings import WEAPONS, BULLET_DAMAGE
    from tank import Tank

    class _Fx:
        def burst(self, *a, **k): pass
        def float_text(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    check("в арсенале 6 дул", len(WEAPONS) == 6)

    sh = Tank(0, 0, 0, "medium", "medium", COL, "shotgun", "none")
    bs = []
    sh.cooldown = 0
    sh.try_shoot(bs, fx, snd)
    check("дробовик: залп из 5 дробин",
          len(bs) == 5 and WEAPONS["shotgun"]["pellets"] == 5)
    check("дробовик: каждая дробина слабая (x0.5)",
          abs(bs[0].damage - BULLET_DAMAGE * 0.5 * 1.10) < 0.1,
          "(dmg=%.1f)" % bs[0].damage)
    angles = [math.degrees(math.atan2(b.vy, b.vx)) for b in bs]
    check("дробовик: дробины летят веером", max(angles) - min(angles) > 4,
          "(разлет %.0f°)" % (max(angles) - min(angles)))

    mg = Tank(0, 0, 0, "medium", "medium", COL, "rapidgun", "none")
    check("пулемёт: обойма на 6", mg.mag_size == 6)
    bm = []
    mg.cooldown = 0
    mg.try_shoot(bm, fx, snd)
    check("пулемёт: очередями по одному, снаряд лёгкий, пауза mag_cd",
          len(bm) == 1
          and abs(bm[0].damage - BULLET_DAMAGE * 0.5 * 1.10) < 0.1
          and abs(mg.cooldown - WEAPONS["rapidgun"]["mag_cd"]) < 1e-6)

    hw = Tank(0, 0, 0, "medium", "medium", COL, "howitzer", "none")
    bh = []
    hw.cooldown = 0
    hw.try_shoot(bh, fx, snd)
    check("гаубица: снаряд x2 урона и крупный",
          abs(bh[0].damage - BULLET_DAMAGE * 2.0 * 1.10) < 0.1 and bh[0].big,
          "(dmg=%.0f)" % bh[0].damage)
    check("гаубица: танк еле ползёт (орудие x0.8)",
          abs(hw.speed - 175 * (1 - 0.15) * 0.8) < 0.6,
          "(%.1f)" % hw.speed)


# ---------- 3k. ПЕРК РИКОШЕТ: +2 отскока каждому снаряду ----------
def test_ricochet():
    from settings import BULLET_BOUNCES, PERKS
    from tank import Tank

    class _Fx:
        def burst(self, *a, **k): pass
        def float_text(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    check("перк «Рикошет» в списке перков", "ricochet" in PERKS)
    base = Tank(0, 0, 0, "medium", "medium", COL, "standard", "none")
    rk = Tank(0, 0, 0, "medium", "medium", COL, "standard", "ricochet")
    check("без перка у снаряда %d рикошет" % BULLET_BOUNCES,
          base.bullet_bounces == BULLET_BOUNCES)
    check("«Рикошет»: +2 отскока каждому снаряду",
          rk.bullet_bounces == BULLET_BOUNCES + PERKS["ricochet"]["bounces"])
    bullets = []
    rk.cooldown = 0
    rk.try_shoot(bullets, fx, snd)
    check("снаряд «Рикошета» несёт %d отскока" % (BULLET_BOUNCES + 2),
          bullets[0].bounces == BULLET_BOUNCES + 2,
          "(bounces=%d)" % bullets[0].bounces)
    check("цена рикошета: прочность -15%%",
          rk.max_hp == int(round(110 * 0.85)), "(hp %d)" % rk.max_hp)


# ---------- 3l. НОВЫЕ СТИХИИ: лёд, яд, вампиризм + правило своей стихии ----------
def test_new_elements():
    from settings import (ELEMENTS, ICE_TIME, POISON_TIME, POISON_DPS,
                          VAMP_HEAL_RATIO)
    from tank import Tank
    from bullet import Bullet
    from arena import Arena

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    a = Arena(0)
    check("в колоде 9 стихий", len(ELEMENTS) == 9)

    # лёд: вмораживает (скорость 0)
    t = Tank(0, 0, 0, "medium", "medium", COL)
    t.apply_element("ice", 1, 0, a, fx, snd)
    check("лёд вмораживает врага на %.1f с (скорость 0)" % ICE_TIME,
          t.frozen_t == ICE_TIME and t.speed == 0.0)

    # яд: травит со временем, броня не спасает
    t2 = Tank(0, 0, 0, "medium", "medium", COL)
    t2.apply_element("poison", 1, 0, a, fx, snd)
    hp0 = t2.hp
    for _ in range(30):
        t2._poison_step(1 / 60.0, fx, snd)
    check("яд тикает уроном %.1f/с" % POISON_DPS,
          abs((hp0 - t2.hp) - POISON_DPS * 0.5) < 0.01 and t2.poison_t > 0,
          "(потеря %.1f)" % (hp0 - t2.hp))

    # вампиризм: стрелявшему возвращается 40% урона снаряда
    shooter = Tank(300, 540, 0, "medium", "medium", COL)
    victim = Tank(360, 540, 0, "medium", "medium", (255, 46, 122))
    shooter.hp = 40
    bv = Bullet(victim.x, victim.y, 0, shooter, damage=30, element="vamp")
    bv.age = 1.0
    bv.update(1 / 60.0, a.walls_only(), (shooter, victim), fx, snd)
    check("вампиризм: стрелявшему +%d HP" % int(round(30 * VAMP_HEAL_RATIO)),
          shooter.hp == 40 + int(round(30 * VAMP_HEAL_RATIO)),
          "(hp %d)" % shooter.hp)

    # ПРАВИЛО СВОЕЙ СТИХИИ: свой рикошет бьёт по HP, но НЕ замедляет
    me = Tank(300, 540, 0, "medium", "medium", COL)
    foe = Tank(200, 200, 0, "medium", "medium", (255, 46, 122))
    b = Bullet(me.x, me.y, 0, me, damage=30, element="earth")
    b.age = 1.0
    hp0 = me.hp
    b.update(1 / 60.0, a.walls_only(), (me, foe), fx, snd)
    check("свой снаряд в себя: урон есть, земля НЕ вяжет",
          me.hp < hp0 and me.mud_t == 0,
          "(dmg %.0f, mud %.1f)" % (hp0 - me.hp, me.mud_t))
    b2 = Bullet(me.x, me.y, 0, foe, damage=30, element="earth")
    b2.age = 1.0
    b2.update(1 / 60.0, a.walls_only(), (me, foe), fx, snd)
    check("чужая земля вяжет как раньше", me.mud_t > 0)


# ---------- 3m. ЛИМИТЫ v2.2 (СНЯТЫ) И ТУЛТИПЫ ПОД КУРСОРОМ ----------
def test_limits_tooltip():
    from game import Game, CR_KEYS
    from settings import CHASSIS, MAX_CURSES

    g = Game()
    check("проклятий в колоде 8, лимита нет (MAX_CURSES = числу карт)",
          len(CR_KEYS) == 8 and MAX_CURSES == len(CR_KEYS))

    # тултип: наводим мышь на карточку «Лёгкое» шасси (пример игрока)
    g.state = "select"
    g.draw()
    zones = [r for r, kd, d in g._click_zones if kd == "ch" and d == 0]
    check("карточка шасси кликабельна", bool(zones))
    g._mouse = zones[0].center
    g.draw()   # перерисовываем кадр с курсором на карточке
    check("наведение на «Лёгкое» выдает тултип",
          g._tooltip is not None
          and g._tooltip[0] == CHASSIS["light"]["name"],
          "(%s)" % (g._tooltip[0] if g._tooltip else "-"))
    lines = g._tooltip[2]
    check("в тултипе характеристики и описание (крупно, не 11px)",
          len(lines) >= 3 and any("Скорость" in l for l in lines))

    # тултип проклятья: объясняет награду +15%
    g._mouse = next(r.center for r, kd, d in g._click_zones
                    if kd == "fate" and d == 0)
    g.draw()
    check("тултип проклятья объясняет награду +15%",
          g._tooltip is not None and any("+15%" in l for l in g._tooltip[2]))
    # тултип баффа врага (e_harden, индекс 6): награда +10%
    g._mouse = next(r.center for r, kd, d in g._click_zones
                    if kd == "enemy" and d == 6)
    g.draw()
    check("тултип баффа врага объясняет награду +10%",
          g._tooltip is not None and any("+10%" in l for l in g._tooltip[2]))
    # тултип нового дула: дробовик
    g._mouse = next(r.center for r, kd, d in g._click_zones
                    if kd == "wpn" and d == 3)
    g.draw()
    check("тултип дробовика показывает залп из 5",
          g._tooltip is not None and any("5" in l and "дробин" in l
                                         for l in g._tooltip[2]))


# ---------- 3n. ТАБЛИЦА ПЕРЕЖИВЁТ ЗАКРЫТИЕ ИГРЫ ----------
def test_stats_persist():
    import os
    from game import Game, STATS_FILE

    g = Game()
    g.stats["score_table"] = [{"score": 777, "res": "win", "rounds": "5:0",
                               "c": 1, "b": 0, "e": 0, "mult": 1.15,
                               "el": "Огонь", "date": "01.01 00:00"}]
    g._save_stats()
    check("duel_stats.json записан на диск", os.path.exists(STATS_FILE))
    g2 = Game()   # «новый запуск игры» — читает тот же файл
    check("таблица переживёт закрытие игры: запись читается из файла",
          any(r.get("score") == 777 for r in g2.stats["score_table"]))
    # прибираем за собой
    g2.stats["score_table"] = [r for r in g2.stats["score_table"]
                               if r.get("score") != 777]
    g2._save_stats()

    # v2.5: забег НЕ попал в топ-10 — раньше был краш next()/StopIteration
    from settings import ROUNDS_TO_WIN
    g3 = Game()
    g3.stats["score_table"] = [{"score": 100000 + i, "res": "win",
                                "rounds": "5:0", "c": 0, "b": 0, "e": 0,
                                "mult": 1.0, "el": "Огонь",
                                "date": "01.01 00:00"} for i in range(10)]
    g3.state = "round_end"
    g3.timer = 0.01
    g3.score = [0, ROUNDS_TO_WIN]   # поражение с мизерными очками
    g3.points = 0
    g3.score_mult = 1.0
    g3.update(1 / 60.0)
    check("забег мимо топ-10 НЕ роняет игру (место 0)",
          g3.state == "match_end" and g3.table_place == 0
          and len(g3.stats["score_table"]) == 10)
    g3._draw_match_end()   # баннер «в топ-10 не попал» рисуется без краша
    # прибираем: вернуть таблицу без подставных рекордов
    g3.stats["score_table"] = [r for r in g3.stats["score_table"]
                               if r.get("score", 0) < 100000]
    g3._save_stats()


# ---------- 3o. РЕЖИМЫ v2.1: 1вс1 / 1вс1вс1 / 1вс1вс1вс1 / 1вс1вс1вс1вс1 ----------
def test_ffa():
    import math
    from game import Game
    from arena import Arena
    from bullet import Bullet
    from settings import ROUNDS_TO_WIN

    g = Game()
    check("режим по умолчанию — 1 на 1", g.mode == 2)

    # клик по кнопке режима в меню
    g.state = "menu"
    g.draw()
    zone = next(r for r, kd, d in g._click_zones if kd == "menu_mode" and d == 4)
    g.on_click(zone.center)
    check("клик по «1×1×1×1» включает 4 танка", g.mode == 4)
    g.mode = 5
    g._reset_round()
    check("5 танков на арене: игрок + 4 бота с ИИ",
          len(g.tanks) == 5 and len(g.bots) == 4 and len(g.ais) == 4)
    check("у всех ботов разные цвета",
          len({tuple(t.color) for t in g.bots}) == len(g.bots))
    check("спавны не в стенах/препятствиях",
          all(not g.arena.circle_collides(t.x, t.y, t.radius)
              for t in g.tanks))
    check("спавны далеко друг от друга (более 200 px)",
          all(math.hypot(a.x - b.x, a.y - b.y) > 200
              for i, a in enumerate(g.tanks) for b in g.tanks[i + 1:]))
    g.draw()   # HUD на 5 танков рисуется без ошибок

    # раунд НЕ кончается, пока живых >= 2
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    g.player.alive = False
    g.update(1 / 60.0)
    check("в FFA смерть игрока не кончает раунд (живых ещё 4)",
          g.state == "fight" and len([t for t in g.tanks if t.alive]) == 4)
    # добиваем ботов: остался один — раунд за ним
    for b in g.bots[1:]:
        b.alive = False
    g.update(1 / 60.0)
    check("остался один танк — раунд завершён", g.state == "round_end")
    check("победа засчитана выжившему боту (БОТ)",
          g.winner == 1 and g.score[1] == 1)

    # FFA: снаряд бота бьёт ДРУГОГО бота (каждый сам за себя)
    g2 = Game()
    g2.mode = 3
    g2._reset_round()
    g2.arena = Arena(6)          # «Мосты»: чистая полоса на y=540
    b1, b2 = g2.bots[0], g2.bots[1]
    b1.x, b1.y, b1.angle = 600, 540, 0
    b2.x, b2.y = 720, 540
    hp0 = b2.hp
    bul = Bullet(b2.x - 10, 540, 0, b1, damage=30)
    bul.age = 1.0
    bul.update(1 / 60.0, g2.arena.walls_only(), tuple(g2.tanks),
               g2.effects, g2.sounds)
    check("снаряд бота ранит другого бота (FFA)",
          b2.hp < hp0, "(hp %d -> %d)" % (hp0, b2.hp))

    # ИИ в FFA воюет с ближайшим чужим (может — с другим ботом)
    ai = g2.ais[0]
    ai.target = None
    ai.target = ai._pick_target(g2)
    check("бот-1 взял цель: чужой танк, не сам себя",
          ai.target is not None and ai.target is not ai.t)
    ai2 = g2.ais[1]
    ai2.target = None
    ai2.update(1 / 60.0, g2)
    check("бот-2 воюет с кем-то живым",
          ai2.target is not None and ai2.target.alive)

    # бот добирает 5 побед — матч проигран
    g3 = Game()
    g3.state = "round_end"
    g3.timer = 0.01
    g3.score = [2, ROUNDS_TO_WIN]
    g3.update(1 / 60.0)
    check("бот добрал 5 побед — матч завершён поражением",
          g3.state == "match_end" and g3.stats["losses"] >= 1)

    # ОГНЕННОЙ ЗОНЫ БОЛЬШЕ НЕТ (v2.5 — убрана по просьбе игрока)
    import settings as _st
    check("огненная зона удалена (нет FFA_ZONE_T и _zone_step)",
          not hasattr(_st, "FFA_ZONE_T") and not hasattr(Game, "_zone_step")
          and not hasattr(g, "round_t"))

    # спавны выживают на случайных картах во всех режимах
    ok = True
    for n in (2, 3, 4, 5):
        for _ in range(4):
            g4 = Game()
            g4.mode = n
            g4._reset_round()
            if any(g4.arena.circle_collides(t.x, t.y, t.radius)
                   for t in g4.tanks):
                ok = False
    check("спавны не в стенах на 16 случайных картах всех режимов", ok)


# ---------- 3p. КАРТЫ v2.1: 16 штук, зеркало и случайные баррикады ----------
def test_map_shuffle():
    from arena import Arena, MAP_NAMES, LAYOUTS
    from settings import PROP_MAX

    check("карт стало 16", len(LAYOUTS) == 16 and len(MAP_NAMES) == 16)
    a = Arena(2, shuffle=True)
    check("перемешанная карта: внешние стены на месте",
          a.point_blocked(10, 360) and a.point_blocked(640, 10))
    check("баррикад не больше %d" % PROP_MAX,
          all(len(Arena(i, shuffle=True).obstacles)
              <= len(LAYOUTS[i]) + PROP_MAX for i in range(16)))
    names = set()
    for _ in range(40):
        c = Arena(0, shuffle=True)
        names.add(c.name)
        sx, sy = c.free_spot()
        if c.circle_collides(sx, sy, 30):
            check("free_spot свободен на перемешанной карте", False)
            return
    check("free_spot свободен на 40 перемешанных картах", True)
    check("рандомизация отмечается звёздочкой в названии",
          any("★" in n for n in names),
          "(вариантов имени %d)" % len(names))
    # классические точки появления не перекрыты баррикадами
    # (мир 2240x1260, масштаб 1.75: классические спавны в (420,630) и (1820,630))
    from arena import _S as _sc
    _sp = [(int(x * _sc), int(y * _sc)) for x, y in ((240, 360), (1040, 360))]
    blocked = 0
    for _ in range(40):
        c = Arena(0, shuffle=True)
        if any(c.circle_collides(sx, sy, 30) for sx, sy in _sp):
            blocked += 1
    check("классические спавны не перекрыты (40 карт)", blocked == 0)


# ---------- 3q. ПОСЛЕ СМЕРТИ ИГРОКА v2.6: окно 180 с + жребий кнопки ----------
def test_spectate():
    """v2.6 (окно было 70 с — стало 180): НЕУЯЗВИМОСТИ НЕТ. После смерти
    игрока живые боты (2+) в FFA выясняют победителя SPECTATE_T секунд,
    потом умирают — ничья. Один бот берёт раунд сразу. Кнопка
    «УБИТЬ СРАЗУ» — ЖРЕБИЙ: случайный живой бот забирает раунд."""
    from game import Game
    from settings import SPECTATE_T

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    g = Game()
    g.state = "fight"
    g._reset_round()
    check("неуязвимости в начале раунда НЕТ",
          g.spectate_t == 0.0 and not any(b.immune for b in g.bots)
          and not g.player.immune)
    bot = g.bot_tank
    hp0 = bot.hp
    bot.take_damage(30, fx, snd)
    check("бота можно бить с первой секунды", bot.hp < hp0,
          "(hp %d -> %d)" % (hp0, bot.hp))
    bot.apply_element("fire", 1, 0, g.arena, fx, snd)
    for _ in range(30):
        bot._burn_step(1 / 60.0, fx, snd)
    check("поджог тикает сразу (некого щадить)", bot.hp < hp0)

    # --- 1вс1: игрок умер — бот берёт раунд СРАЗУ, без всяких ожиданий
    g1 = Game()
    g1.mode = 2
    g1._reset_round()
    g1.state = "fight"
    g1._fake_keys = FakeKeys(())
    g1.player.alive = False
    g1.player._die(fx, snd)
    g1.update(1 / 60.0)
    check("1вс1: бот-одиночка берёт раунд сразу после смерти игрока",
          g1.state == "round_end" and g1.winner == 1 and g1.score[1] == 1)

    # --- FFA на 3: игрок умер при двух живых ботах — стартует окно 180 с
    g2 = Game()
    g2.mode = 3
    g2._reset_round()
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    g2.player.alive = False
    g2.player._die(fx, snd)
    g2.update(1 / 60.0)
    check("после смерти игрока боты выясняют победителя %g с" % SPECTATE_T,
          g2.state == "fight" and g2.spectate_t == SPECTATE_T)
    # делаем ботов неубиваемыми, чтобы проверить именно ТАЙМАУТ окна,
    # а не их случайную дуэль (флаг immune больше нигде не трогается)
    for b in g2.bots:
        b.immune = True
    # окно рисует текст и кнопку «УБИТЬ СРАЗУ»
    g2.draw()
    check("кнопка «УБИТЬ СРАЗУ» видна во время выяснения",
          bool([r for r, kd, d in g2._click_zones if kd == "kill_all"]))
    # 180 секунд никто не победил — ВСЕ боты умирают, раунд ничья
    for _ in range(int(SPECTATE_T * 60) + 2):
        g2.update(1 / 60.0)
        if g2.state == "round_end":
            break
    check("время вышло — боты мертвы, раунд ничья",
          g2.state == "round_end" and g2.winner == -1
          and not any(b.alive for b in g2.bots))

    # --- FFA: один бот победил другого ДО конца окна — победа уйдёт ему
    g3 = Game()
    g3.mode = 3
    g3._reset_round()
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3.player.alive = False
    g3.player._die(fx, snd)
    g3.update(1 / 60.0)               # окно запустилось
    g3.bots[1].alive = False          # первый бот «победил» второго
    g3.update(1 / 60.0)
    check("победа в выяснении уходит победившему боту",
          g3.state == "round_end" and g3.winner == 1 and g3.score[1] == 1)

    # --- кнопка «УБИТЬ СРАЗУ» во время окна (v2.6): ЖРЕБИЙ — случайный
    # живой бот сразу забирает раунд, остальные враги взрываются
    g4 = Game()
    g4.mode = 4
    g4._reset_round()
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4.player.alive = False
    g4.player._die(fx, snd)
    g4.update(1 / 60.0)
    check("в 1x1x1x1 окно тоже запустилось", g4.spectate_t == SPECTATE_T)
    g4._kill_all_foes()
    g4.update(1 / 60.0)
    alive4 = [b for b in g4.bots if b.alive]
    check("«УБИТЬ СРАЗУ» — жребий: один живой бот забрал раунд",
          g4.state == "round_end" and len(alive4) == 1
          and g4.winner == g4.tanks.index(alive4[0])
          and g4.score[g4.winner] == 1 and g4.spectate_t == 0.0)

    # --- жребий действительно СЛУЧАЙНЫЙ: за серию прогонов победителем
    # бывают разные боты (30 бросков кубка на 3 стороны)
    winners = set()
    for _ in range(30):
        gx = Game()
        gx.mode = 4
        gx._reset_round()
        gx.state = "fight"
        gx._fake_keys = FakeKeys(())
        gx.player.alive = False
        gx.player._die(fx, snd)
        gx.update(1 / 60.0)
        gx._kill_all_foes()
        winners.add(gx.winner)
    check("жребий кнопки выбирает разных ботов", len(winners) >= 2,
          "(вариантов за 30 прогонов: %d)" % len(winners))

    # --- команда: окно НЕ запускается (союзники доигрывают за нас)
    g5 = Game()
    g5.mode = 6
    g5._reset_round()
    g5.state = "fight"
    g5._fake_keys = FakeKeys(())
    g5.player.alive = False
    g5.player._die(fx, snd)
    g5.update(1 / 60.0)
    check("в командах после смерти игрока окно не стартует",
          g5.state == "fight" and g5.spectate_t == 0.0)

    # --- игрок жив: окно не стартует
    g6 = Game()
    g6.mode = 3
    g6._reset_round()
    g6.state = "fight"
    g6._fake_keys = FakeKeys(())
    g6.update(1 / 60.0)
    check("пока игрок жив — никакого окна", g6.spectate_t == 0.0)


# ---------- 3r. КОНСОЛЬ РАЗРАБОТЧИКА (Ё): выдача всего, подсказки ----------
def test_console():
    import math
    from game import Game

    g = Game()
    g.state = "fight"
    g._reset_round()
    g._fake_keys = FakeKeys(())
    p, bot = g.player, g.bot_tank

    # подсказки: пишешь «Ту» — консоль подсказывает «Турбо»
    g.con_input = "Ту"
    check("подсказка «Ту» -> «Турбо»", "турбо" in g._con_hints())

    # v2.5: Ё на РУССКОЙ раскладке Windows не даёт K_BACKQUOTE —
    # консоль должна открываться по сканкоду клавиши и по символу
    ev_ru = pygame.event.Event(pygame.KEYDOWN, key=1073741824 + 0x0451,
                               scancode=pygame.KSCAN_GRAVE, unicode="ё")
    g.con_open = False
    g.on_keydown(ev_ru)
    check("Ё с русской раскладки (санкод) открывает консоль", g.con_open)
    g.on_keydown(ev_ru)
    check("повторное Ё закрывает консоль", not g.con_open)
    ev_lat = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKQUOTE,
                                scancode=pygame.KSCAN_GRAVE, unicode="`")
    g.on_keydown(ev_lat)
    check("Ё с латинской раскладки по-прежнему работает", g.con_open)
    g.con_open = False

    g.con_input = "Во"
    check("подсказка «Во» показывает воду и воздух",
          "вода" in g._con_hints() and "воздух" in g._con_hints())
    g.con_input = "Ту"
    g._con_complete()
    check("Tab дополняет до первого совпадения", g.con_input == "турбо ")

    # выдача стихий: «Вода 1 Игрок» — вода танку №1 (игроку)
    g._con_execute("Вода 1 Игрок")
    check("«Вода 1 Игрок» выдаёт воду игроку", "water" in p.element_keys)
    # стихии СКЛАДЫВАЮТСЯ: теперь у игрока и огонь, и вода
    g._con_execute("Огонь Игрок")
    check("«Огонь Игрок» добавляет вторую стихию",
          p.element_keys == ["water", "fire"])
    seen = set()
    for _ in range(40):
        p.cooldown = 0
        p.mag_ammo = p.mag_size
        bs = []
        p.try_shoot(bs, g.effects, g.sounds)
        seen.update(b.element for b in bs)
    check("с двумя стихиями снаряды летят и огненные, и водяные",
          {"fire", "water"} <= seen, "(стихии %s)" % seen)

    # дула, перки, эффекты — тоже выдаются
    g._con_execute("Гаубица Бот")
    check("«Гаубица Бот» меняет дуло бота", bot.wpn_key == "howitzer")
    g._con_execute("Рикошет Бот")
    check("«Рикошет Бот» выдаёт перк (+2 отскока)", bot.bullet_bounces == 3)
    g._con_execute("Закалить врага Бот")
    check("«Закалить врага Бот» баффает прочность",
          abs(bot.mods["hp_mult"] - 1.25) < 1e-9)

    # бонусы и утилиты
    g._con_execute("Веер Игрок")
    check("«Веер Игрок» даёт 3 выстрела веером", p.triple == 3)
    g._con_execute("хп 50 Игрок")
    check("«хп 50 Игрок» выставляет прочность", p.hp == 50)
    g._con_execute("счёт 500")
    check("«счёт 500» накидывает очков", g.points == 500)
    g._con_execute("ждать 180")
    check("«ждать 180» ставит окно выяснения", g.spectate_t == 180)
    g._con_execute("ждать 0")
    check("«ждать 0» снимает окно", g.spectate_t == 0)

    # бонус БЕЗ цели — режим установки кликом (веер на карту)
    g._con_open = True
    g._con_execute("Веер")
    check("«Веер» без цели включает установку кликом",
          g.con_place == "triple" and not g.con_open)
    # клик по карте в мировых координатах камеры — бонус появляется.
    # точка ищем СВОБОДНУЮ: карта случайная, часть позиции занята баррикадами
    wx = wy = None
    for dx in range(200, 560, 20):
        cand = (p.x + dx, p.y)
        if not g.arena.circle_collides(cand[0], cand[1], 26):
            wx, wy = cand
            break
    check("рядом с игроком нашлась свободная точка под бонус", wx is not None)
    g._con_do_place((wx - g.cam[0], wy - g.cam[1]))
    check("клик ставит бонус на карту (потом можно подъехать и забрать)",
          len(g.powerups) == 1 and g.powerups[0].kind == "triple"
          and abs(g.powerups[0].x - wx) < 1 and abs(g.powerups[0].y - wy) < 1)

    # «убить всех» — все боты мертвы
    g2 = Game()
    g2.state = "fight"
    g2._reset_round()
    g2._con_execute("убить всех")
    check("«убить всех» убивает всех ботов",
          not any(b.alive for b in g2.bots))
    # регулятор консоли: неизвестное слово не роняет игру
    g2._con_execute("абракадабра 123")
    check("неизвестная команда не роняет игру", True)


# ---------- 3s2. ПОДСВЕТКА КОМАНД v2.6: враги красным, союзники салатовым ----------
def test_team_highlight():
    """v2.6: в командных боях у каждого танка есть цвет стороны — враги
    КРАСНЫЕ, союзники (включая игрока) САЛАТОВЫЕ: свечение под танком,
    точки на миникарте и строки в HUD. В FFA подсветки нет."""
    from game import Game
    from settings import TEAM_FOE_COLOR, TEAM_ALLY_COLOR, SPECTATE_T

    check("v2.6: окно выяснения = 180 с", SPECTATE_T == 180.0)

    g = Game()
    g.mode = 3                 # FFA — подсветки быть не должно
    g._reset_round()
    check("в FFA подсветки нет",
          all(g._team_ring_color(t) is None for t in g.tanks)
          and all(g._team_pad(t) is None for t in g.tanks))

    g2 = Game()
    g2.mode = 6                # 2 на 2: игрок + СОЮЗНИК против БОТ и БОТ-2
    g2._reset_round()
    allies = [t for t in g2.tanks if g2.tank_team[t] == 0]
    foes = [t for t in g2.tanks if g2.tank_team[t] == 1]
    check("2на2: составы по два танка", len(allies) == 2 and len(foes) == 2)
    check("союзники (и игрок) подсвечены САЛАТОВЫМ",
          all(g2._team_ring_color(t) == TEAM_ALLY_COLOR for t in allies))
    check("враги подсвечены КРАСНЫМ",
          all(g2._team_ring_color(t) == TEAM_FOE_COLOR for t in foes))
    pads = [g2._team_pad(t) for t in g2.tanks]
    check("свечение под танком — квадратный спрайт с кругом",
          all(p is not None and p.get_width() == p.get_height() > 0
              for p in pads))
    # кадр с подсветкой (мир + миникарта + HUD) рисуется без падений
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    g2.draw()
    check("кадр командного боя с подсветкой рисуется", True)

    # 5 на 5: пятеро салатовых против пятерых красных
    g3 = Game()
    g3.mode = 10
    g3._reset_round()
    a3 = [t for t in g3.tanks if g3.tank_team[t] == 0]
    f3 = [t for t in g3.tanks if g3.tank_team[t] == 1]
    check("5на5: 5 салатовых союзников и 5 красных врагов",
          len(a3) == 5 and len(f3) == 5
          and all(g3._team_ring_color(t) == TEAM_ALLY_COLOR for t in a3)
          and all(g3._team_ring_color(t) == TEAM_FOE_COLOR for t in f3))


# ---------- 3s. КОМАНДНЫЕ РЕЖИМЫ v2.2: 2 на 2 и 2 против БОССА ----------
def test_team_modes():
    import math
    from game import Game
    from bullet import Bullet
    from settings import BOSS_SCALE

    # ----- 2 НА 2 -----
    g = Game()
    g.mode = 6
    g._reset_round()
    check("режим «2 на 2»: 4 танка", len(g.tanks) == 4)
    check("команды: игрок+союзник (0) против двух ботов (1)",
          [g.tank_team[t] for t in g.tanks] == [0, 0, 1, 1])
    check("союзник — «СОЮЗНИК» с бирюзовым цветом",
          g.bots[0].display_name == "СОЮЗНИК")
    check("неуязвимости нет ни у кого (v2.5)",
          not g.bots[0].immune and not any(b.immune for b in g.foes))
    check("врагов двое, счёт командный [0, 0]",
          len(g.foes) == 2 and g.score == [0, 0])
    g.draw()   # HUD командного режима рисуется без ошибок

    # союзная пуля пролетает сквозь союзника, не раня его
    p, ally = g.player, g.bots[0]
    p.x, p.y = 400, 540
    ally.x, ally.y = 700, 540
    ally.hp = ally.max_hp
    g.arena = __import__("arena").Arena(0)
    hp0 = ally.hp
    bl = Bullet(430, 540, 0, p, damage=30)
    bl.age = 1.0
    for _ in range(30):
        bl.update(1 / 60.0, g.arena.walls_only(), tuple(g.tanks),
                  g.effects, g.sounds)
        if bl.dead:
            break
    check("снаряд союзника НЕ ранит союзника (пролетает)",
          ally.hp == hp0, "(hp %d -> %d)" % (hp0, ally.hp))

    # ИИ союзника воюет только с вражеской командой
    ai = g.ais[0]
    ai.target = None
    ai.target = ai._pick_target(g)
    check("ИИ союзника берёт целью только чужую команду",
          ai.target is not None and g.tank_team[ai.target] == 1)

    # вырезали вражескую команду — раунд за НАШЕЙ командой
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    for b in g.foes:
        b.alive = False
    g.update(1 / 60.0)
    check("враги мертвы -> раунд за вашей командой",
          g.state == "round_end" and g.winner == 0 and g.score[0] == 1)

    # ----- 2 ПРОТИВ БОССА -----
    g3 = Game()
    g3.mode = 7
    g3._reset_round()
    boss = [b for b in g3.bots if b.display_name == "БОСС"][0]
    check("режим «2 против БОССА»: игрок + союзник + босс", len(g3.tanks) == 3)
    check("БОСС вдвое крупнее обычного танка",
          abs(boss.radius - 24 * BOSS_SCALE) < 0.01 and boss.scale == BOSS_SCALE)
    check("БОСС вчетверо крепче (~800 HP)", boss.max_hp >= 780,
          "(hp %d)" % boss.max_hp)
    check("БОСС и союзник без неуязвимости (v2.5)",
          not boss.immune and not g3.bots[0].immune)
    g3.draw()
    # убили босса — раунд за командой игрока
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3.foes[0].alive = False
    g3.update(1 / 60.0)
    check("босс мёртв -> раунд за командой игрока",
          g3.state == "round_end" and g3.winner == 0 and g3.score[0] == 1)
    # команда игрока мертва — раунд за боссом
    g4 = Game()
    g4.mode = 7
    g4._reset_round()
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4.player.alive = False
    g4.bots[0].alive = False
    g4.update(1 / 60.0)
    check("игрок и союзник мертвы -> раунд за боссом",
          g4.state == "round_end" and g4.winner == 1 and g4.score[1] == 1)
    # матч: босс добрал 5 побед — поражение
    g5 = Game()
    g5.mode = 7
    g5.state = "round_end"
    g5.timer = 0.01
    g5.score = [2, 5]
    g5.update(1 / 60.0)
    check("босс добрал 5 побед — матч завершён поражением",
          g5.state == "match_end" and g5.stats["losses"] >= 1)


# ---------- 3t. КАРТЫ v2.5: обычные 2752x1548, командные 3888x2187 ----------
def test_bigmap():
    import math
    from game import Game
    from settings import (ARENA_W, ARENA_H, SCREEN_W, SCREEN_H,
                          TEAM_ARENA_W, TEAM_ARENA_H)

    check("обычная карта x1.5 площади к v2.4: 2752x1548",
          ARENA_W == 2752 and ARENA_H == 1548
          and abs(ARENA_W * ARENA_H / (2240.0 * 1260) - 1.5) < 0.01)
    check("командная карта x3 площади к v2.4: 3888x2187",
          TEAM_ARENA_W == 3888 and TEAM_ARENA_H == 2187
          and abs(TEAM_ARENA_W * TEAM_ARENA_H / (2240.0 * 1260) - 3.0) < 0.02)
    a = __import__("arena").Arena(0)
    at = __import__("arena").Arena(0, team=True)
    check("арена несёт свой размер: обычная и командная",
          (a.w, a.h) == (ARENA_W, ARENA_H)
          and (at.w, at.h) == (TEAM_ARENA_W, TEAM_ARENA_H)
          and at.wall_t > a.wall_t)
    check("внешние стены большого мира блокируют",
          a.point_blocked(10, 540) and a.point_blocked(960, 10))
    check("свободная точка на большом мире ищется",
          not a.circle_collides(*a.free_spot(), 26)
          and not at.circle_collides(*at.free_spot(), 26))

    g = Game()
    g.state = "fight"
    g._reset_round()
    g._fake_keys = FakeKeys(())
    # камера следит за игроком и не выходит за края мира
    g.player.x, g.player.y = 100, 100
    g._update_cam(1 / 60.0)
    g._cam_snap()
    check("камера прижата к левому верхнему углу",
          g.cam[0] == 0 and g.cam[1] == 0)
    g.player.x, g.player.y = ARENA_W - 10, ARENA_H - 10
    g._cam_snap()
    check("камера прижата к правому нижнему углу",
          g.cam[0] == ARENA_W - SCREEN_W and g.cam[1] == ARENA_H - SCREEN_H)
    # командный режим — командная карта и кламп камеры по ней
    gt = Game()
    gt.mode = 8
    gt._reset_round()
    gt.state = "fight"
    gt._fake_keys = FakeKeys(())
    check("3на3 выезжает на командной карте 3888x2187",
          (gt.arena.w, gt.arena.h) == (TEAM_ARENA_W, TEAM_ARENA_H))
    gt.player.x, gt.player.y = TEAM_ARENA_W - 10, TEAM_ARENA_H - 10
    gt._cam_snap()
    check("камера на командной карте прижата к её правому нижнему углу",
          gt.cam[0] == TEAM_ARENA_W - SCREEN_W
          and gt.cam[1] == TEAM_ARENA_H - SCREEN_H)
    g._reset_round()
    g.draw()
    check("бой на большой карте рисуется (камера + миникарта)", True)
    # спавны всех режимов свободны и далеко друг от друга
    ok = True
    for m in (2, 3, 4, 5, 6, 7, 8, 9, 10):
        for _ in range(3):
            gm = Game()
            gm.mode = m
            gm._reset_round()
            if any(gm.arena.circle_collides(t.x, t.y, t.radius)
                   for t in gm.tanks):
                ok = False
            dist = min(math.hypot(a2.x - b2.x, a2.y - b2.y)
                       for i, a2 in enumerate(gm.tanks)
                       for b2 in gm.tanks[i + 1:])
            if dist < 240:
                ok = False
    check("спавны всех 9 режимов свободны и не ближе 240 px", ok)


# ---------- 3u. ФИКС «ПУЛЕМЁТ + ЛЁД» v2.3: лёд больше не перезаливается ----------
def test_ice_immunity():
    from settings import ICE_TIME, ICE_IMMUNE_T
    from tank import Tank
    from arena import Arena

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()
    a = Arena(0)

    t = Tank(600, 540, 0, "medium", "medium", COL)
    t.apply_element("ice", 1, 0, a, fx, snd)
    check("лёд вмораживает на %.1f с" % ICE_TIME, t.frozen_t == ICE_TIME)
    # очередь по уже замороженному: заморозка НЕ продлевается
    for _ in range(5):
        t.apply_element("ice", 1, 0, a, fx, snd)
    check("повторные ледяные попадания НЕ продлевают лёд",
          t.frozen_t == ICE_TIME, "(frozen %.2f)" % t.frozen_t)
    # оттаивание -> иммунитет на ICE_IMMUNE_T
    for _ in range(int(ICE_TIME * 60) + 2):
        t.update(1 / 60.0)
    check("после оттаивания включается иммунитет к льду (%.1f с)" % ICE_IMMUNE_T,
          t.frozen_t == 0.0 and abs(t.ice_immune_t - ICE_IMMUNE_T) < 0.1,
          "(immune %.2f)" % t.ice_immune_t)
    t.apply_element("ice", 1, 0, a, fx, snd)
    check("в окне иммунитета лёд НЕ сковывает", t.frozen_t == 0.0)
    # иммунитет кончился — лёд снова работает
    for _ in range(int(ICE_IMMUNE_T * 60) + 3):
        t.update(1 / 60.0)
    t.apply_element("ice", 1, 0, a, fx, snd)
    check("после окна иммунитета лёд снова вмораживает", t.frozen_t == ICE_TIME)

    # ПУЛЕМЁТ + ЛЁД как в бою: полная обойма не держит врага в вечном льду
    victim = Tank(660, 540, 0, "light", "light", (255, 46, 122))
    victim.apply_element("ice", 1, 0, a, fx, snd)   # первая дробина скует
    for _ in range(5):                              # остальные 5 дробин обоймы
        victim.apply_element("ice", 1, 0, a, fx, snd)
        victim.update(0.12)                         # темп очереди пулемёта
    check("обойма пулемёта держит врага не дольше %.1f с льда" % ICE_TIME,
          victim.frozen_t <= ICE_TIME,
          "(frozen %.2f)" % victim.frozen_t)
    while victim.frozen_t > 0:
        victim.update(1 / 60.0)
    check("оттаял — иммунитет включился, танк может ехать",
          victim.ice_immune_t > 0 and victim.speed > 0)


# ---------- 3v. РЕЖИМЫ 3 НА 3 И 4 НА 4 (v2.3) ----------
def test_big_teams():
    import math
    from game import Game
    from bullet import Bullet
    from arena import Arena
    from settings import ARENA_H

    # ----- 3 НА 3 -----
    g = Game()
    g.mode = 8
    g._reset_round()
    check("режим «3 на 3»: 6 танков", len(g.tanks) == 6)
    check("команды: игрок+2 союзника против трёх ботов",
          [g.tank_team[t] for t in g.tanks] == [0, 0, 0, 1, 1, 1])
    check("союзники зовутся СОЮЗНИК и СОЮЗНИК-2",
          g.bots[0].display_name == "СОЮЗНИК"
          and g.bots[1].display_name == "СОЮЗНИК-2")
    check("вражеские боты получили имена БОТ..БОТ-3",
          [b.display_name for b in g.bots[2:]] == ["БОТ", "БОТ-2", "БОТ-3"])
    check("врагов трое, счёт командный", len(g.foes) == 3 and g.score == [0, 0])
    check("неуязвимости нет — бить можно всех с первой секунды",
          not any(b.immune for b in g.tanks))
    g.draw()   # HUD на 6 танков рисуется без ошибок

    # шеренги на старте: наша снизу, чужая сверху (арена без баррикад)
    g.arena = Arena(0)
    pts = g._spawn_points(6)
    check("шеренги 3на3: наша снизу, чужая сверху",
          all(p[1] > g.arena.h / 2 for p in pts[:3])
          and all(p[1] < g.arena.h / 2 for p in pts[3:]))
    dist = min(math.hypot(p1[0] - p2[0], p1[1] - p2[1])
               for i, p1 in enumerate(pts) for p2 in pts[i + 1:])
    check("точки шеренг разнесены не меньше 240 px", dist > 240,
          "(min %.0f)" % dist)

    # ИИ второго союзника целится только в чужую команду
    ai = g.ais[1]
    ai.target = ai._pick_target(g)
    check("ИИ СОЮЗНИКА-2 воюет только с врагами",
          ai.target is not None and g.tank_team[ai.target] == 1)

    # вырезали врагов — раунд за нашей командой
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    for b in g.foes:
        b.alive = False
    g.update(1 / 60.0)
    check("враги 3на3 мертвы -> раунд за вашей командой",
          g.state == "round_end" and g.winner == 0 and g.score[0] == 1)

    # ----- 4 НА 4 -----
    g2 = Game()
    g2.mode = 9
    g2._reset_round()
    check("режим «4 на 4»: 8 танков", len(g2.tanks) == 8)
    check("команды: игрок+3 союзника против четырёх ботов",
          [g2.tank_team[t] for t in g2.tanks] == [0, 0, 0, 0, 1, 1, 1, 1])
    check("третий союзник зовётся СОЮЗНИК-3",
          g2.bots[2].display_name == "СОЮЗНИК-3")
    check("врагов четверо с именами БОТ..БОТ-4",
          [b.display_name for b in g2.bots[3:]]
          == ["БОТ", "БОТ-2", "БОТ-3", "БОТ-4"])
    g2.draw()
    g2.arena = Arena(0)
    pts = g2._spawn_points(8)
    check("шеренги 4на4: 4 снизу и 4 сверху",
          all(p[1] > g2.arena.h / 2 for p in pts[:4])
          and all(p[1] < g2.arena.h / 2 for p in pts[4:]))

    # снаряд ПРОЛЕТАЕТ сквозь союзника в толпе из 8 танков
    p, a1 = g2.player, g2.bots[0]
    p.x, p.y = 500, 540
    a1.x, a1.y = 760, 540
    a1.hp = a1.max_hp
    g2.arena = Arena(0)
    hp0 = a1.hp
    bl = Bullet(530, 540, 0, p, damage=30)
    bl.age = 1.0
    for _ in range(40):
        bl.update(1 / 60.0, g2.arena.walls_only(), tuple(g2.tanks),
                  g2.effects, g2.sounds)
        if bl.dead:
            break
    check("в 4на4 снаряд союзника НЕ ранит союзника", a1.hp == hp0,
          "(hp %d -> %d)" % (hp0, a1.hp))

    # вся наша команда мертва -> раунд за ботами
    g3 = Game()
    g3.mode = 9
    g3._reset_round()
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    for tk in g3.tanks:
        if g3.tank_team[tk] == 0:
            tk.alive = False
    g3.update(1 / 60.0)
    check("команда игрока вырезана -> раунд за командой ботов",
          g3.state == "round_end" and g3.winner == 1 and g3.score[1] == 1)

    # ----- 5 НА 5 (v2.5): вся рота — 10 танков -----
    g5 = Game()
    g5.mode = 10
    g5._reset_round()
    check("режим «5 на 5»: 10 танков", len(g5.tanks) == 10)
    check("команды: игрок+4 союзника против пяти ботов",
          [g5.tank_team[t] for t in g5.tanks]
          == [0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    check("четвёртый союзник зовётся СОЮЗНИК-4",
          g5.bots[3].display_name == "СОЮЗНИК-4")
    check("врагов пятеро с именами БОТ..БОТ-5",
          [b.display_name for b in g5.bots[4:]]
          == ["БОТ", "БОТ-2", "БОТ-3", "БОТ-4", "БОТ-5"])
    check("счёт командный, врагов пять", len(g5.foes) == 5
          and g5.score == [0, 0] and g5.team_mode)
    g5.draw()   # HUD на 10 танков рисуется без ошибок
    g5.arena = Arena(0)
    pts5 = g5._spawn_points(10)
    check("шеренги 5на5: 5 снизу и 5 сверху",
          all(p[1] > g5.arena.h / 2 for p in pts5[:5])
          and all(p[1] < g5.arena.h / 2 for p in pts5[5:]))
    dist5 = min(math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                for i, p1 in enumerate(pts5) for p2 in pts5[i + 1:])
    check("точки 5на5 разнесены не меньше 240 px", dist5 > 240,
          "(min %.0f)" % dist5)
    # вырезали чужих — раунд за нашей ротой
    g5.state = "fight"
    g5._fake_keys = FakeKeys(())
    for b in g5.foes:
        b.alive = False
    g5.update(1 / 60.0)
    check("враги 5на5 мертвы -> раунд за вашей командой",
          g5.state == "round_end" and g5.winner == 0 and g5.score[0] == 1)

    # консоль в большом бою: «Бот» — чужак, «Союзник2» — второй союзник
    g4 = Game()
    g4.mode = 8
    g4._reset_round()
    g4._con_execute("гаубица союзник2")
    check("консоль: «Гаубица Союзник2» сменила дуло второму союзнику",
          g4.bots[1].wpn_key == "howitzer")
    g4._con_execute("закалить врага бот")
    check("консоль: «Закалить врага Бот» бьёт по ЧУЖАКУ, не по союзнику",
          g4.foes[0].mods.get("hp_mult", 1.0) != 1.0
          and g4.bots[0].mods.get("hp_mult", 1.0) == 1.0)
    g4._con_execute("вода 1 бот2")
    check("консоль: «Вода 1 Бот2» добавила стихию чужаку №2",
          "water" in g4.foes[1].element_keys)


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
    test_new_weapons()
    test_ricochet()
    test_new_elements()
    test_limits_tooltip()
    test_stats_persist()
    test_ffa()
    test_map_shuffle()
    test_spectate()
    test_console()
    test_team_modes()
    test_team_highlight()
    test_ice_immunity()
    test_big_teams()
    test_bigmap()
    test_points()
    test_score_table()
    test_magazine()
    test_battle()
    test_mouse()
    print()
    if FAILED:
        print("ПРОВАЛЕНО: %d -> %s" % (len(FAILED), FAILED))
        sys.exit(1)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
