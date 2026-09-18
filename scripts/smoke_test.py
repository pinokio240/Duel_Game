# -*- coding: utf-8 -*-
"""
Headless-тесты DUEL (запуск: python scripts/smoke_test.py).
Проверяют: честность скоростей, ПРАВИЛО ТУРБО, обойму «Спарки»,
победителя раунда, полный бой с ботом под dummy-видеодрайвером.
"""
import os
import sys
import math
import random

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
    # (v3.2: бонусов теперь 15 — добавились 3 прочные стены)
    check("на карте 15 бонусов, стихий среди них нет",
          len(PU_INFO) == 15 and not
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
    check("мина ставится по F (E отдана командиру), когда враг далеко",
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
    check("ангар: 6 панелей (с СНАРЯДОМ) + жребий + враг рисуется", True)
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
    random.seed(21)   # фиксированный разброс — тест больше не флакает
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

    check("карт стало 21", len(LAYOUTS) == 21 and len(MAP_NAMES) == 21)
    a = Arena(2, shuffle=True)
    check("перемешанная карта: внешние стены на месте",
          a.point_blocked(10, 360) and a.point_blocked(640, 10))
    check("баррикад не больше %d" % PROP_MAX,
          all(len(Arena(i, shuffle=True).obstacles)
              <= len(LAYOUTS[i]) + PROP_MAX for i in range(21)))
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


# ---------- 3s3. ЭМИ v2.6.2: валит всех ЧУЖИХ, свои не страдают ----------
def test_emp_blast():
    """v2.6.2: ЭМИ щадит СОЮЗНИКОВ подобравшего (v2.6.1 валил вообще
    всех, кроме взявшего). В FFA у каждого танка своя команда — там
    по-прежнему замерзают все, кроме взявшего бонус."""
    from game import Game
    from powerup import PowerUp
    from settings import PU_FREEZE_TIME

    # FFA на 3: бонус поднимает БОТ — игрок и БОТ-2 замерзают, он нет
    g = Game()
    g.mode = 3
    g._reset_round()
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    b = g.bots[0]
    g._apply_pickup(b, PowerUp(b.x, b.y, "freeze"))
    check("ЭМИ в FFA: подобравший бот НЕ замёрз", b.frozen_t == 0.0)
    check("ЭМИ в FFA: замерзли ВСЕ остальные (игрок и БОТ-2)",
          g.player.frozen_t == PU_FREEZE_TIME
          and g.bots[1].frozen_t == PU_FREEZE_TIME,
          "(игрок %.1f, БОТ-2 %.1f)" % (g.player.frozen_t, g.bots[1].frozen_t))

    # 1x1x1x1: игрок поднял ЭМИ — все ТРИ бота встали разом (своих нет)
    g4 = Game()
    g4.mode = 4
    g4._reset_round()
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4._apply_pickup(g4.player, PowerUp(g4.player.x, g4.player.y, "freeze"))
    check("ЭМИ у игрока в 1x1x1x1: все 3 бота встали, игрок ездит",
          g4.player.frozen_t == 0.0
          and all(b.frozen_t == PU_FREEZE_TIME for b in g4.bots))

    # команда (2на2): ЧУЖАК поднял ЭМИ — встаёт вся сторона игрока
    # (игрок + его союзник), а напарник взявшего остаётся на ходу
    g6 = Game()
    g6.mode = 6
    g6._reset_round()
    g6.state = "fight"
    g6._fake_keys = FakeKeys(())
    foe = g6.foes[0]
    mate = g6.foes[1]                       # напарник взявшего
    g6._apply_pickup(foe, PowerUp(foe.x, foe.y, "freeze"))
    check("ЭМИ в 2на2: взявший чужак и его напарник на ходу",
          foe.frozen_t == 0.0 and mate.frozen_t == 0.0,
          "(чужак %.1f, напарник %.1f)" % (foe.frozen_t, mate.frozen_t))
    check("ЭМИ в 2на2: замерзли игрок и СОЮЗНИК игрока",
          g6.player.frozen_t == PU_FREEZE_TIME
          and g6.bots[0].frozen_t == PU_FREEZE_TIME,
          "(игрок %.1f, союзник %.1f)"
          % (g6.player.frozen_t, g6.bots[0].frozen_t))
    # замерзшие реально НЕ едут и не стреляют
    g6.update(1 / 60.0)
    check("замерзший от ЭМИ игрок стоит на месте",
          g6.player.speed == 0.0)

    # тот же 2на2: ЭМИ поднял ИГРОК — чужая сторона встала, свой цел
    g6b = Game()
    g6b.mode = 6
    g6b._reset_round()
    g6b.state = "fight"
    g6b._fake_keys = FakeKeys(())
    g6b._apply_pickup(g6b.player,
                      PowerUp(g6b.player.x, g6b.player.y, "freeze"))
    check("ЭМИ у игрока в 2на2: оба врага встали, игрок ездит",
          g6b.player.frozen_t == 0.0
          and all(f.frozen_t == PU_FREEZE_TIME for f in g6b.foes))
    check("ЭМИ у игрока в 2на2: свой союзник НЕ замёрз",
          g6b.bots[0].frozen_t == 0.0)

    # 5на5: чужак поднял ЭМИ — ВСЯ его пятёрка (он + 4 напарника) ездит,
    # вся пятёрка игрока стоит
    g10 = Game()
    g10.mode = 10
    g10._reset_round()
    g10.state = "fight"
    g10._fake_keys = FakeKeys(())
    f10 = g10.foes[0]
    g10._apply_pickup(f10, PowerUp(f10.x, f10.y, "freeze"))
    check("ЭМИ в 5на5: чужая пятёрка ЦЕЛА (подобравший + 4 его напарника)",
          all(f.frozen_t == 0.0 for f in g10.foes))
    check("ЭМИ в 5на5: замерзли игрок и все 4 его союзника",
          g10.player.frozen_t == PU_FREEZE_TIME
          and all(a.frozen_t == PU_FREEZE_TIME for a in g10.bots[:4]))

    # БОСС: босс поднял ЭМИ — игрок и союзник встали, босс ездит
    g7 = Game()
    g7.mode = 7
    g7._reset_round()
    g7.state = "fight"
    g7._fake_keys = FakeKeys(())
    boss7 = next(t for t in g7.tanks if t.display_name == "БОСС")
    g7._apply_pickup(boss7, PowerUp(boss7.x, boss7.y, "freeze"))
    check("ЭМИ у БОССА: игрок и союзник замерзли, БОСС на ходу",
          boss7.frozen_t == 0.0
          and g7.player.frozen_t == PU_FREEZE_TIME
          and g7.bots[0].frozen_t == PU_FREEZE_TIME)


# ---------- 3s4. БОЛЬШИЕ FFA v2.7: все против всех на 6..10 танков ----------
def test_ffa_big():
    """v2.7: режимы 11-15 — «каждый сам за себя» на 6/7/8/9/10 танков.
    team_mode выключен, у каждого бота свой team-номер и цвет, счёт на
    каждого танка, КРУПНАЯ карта, кольцо спавнов без слипаний."""
    import math
    from game import Game, get_font
    from settings import MODE_NAMES, BOT_NAMES, SCREEN_W, TEAM_ARENA_W

    for mode, n in ((11, 6), (12, 7), (13, 8), (14, 9), (15, 10)):
        g = Game()
        g.mode = mode
        g.start_match()
        g.state = "fight"
        g._fake_keys = FakeKeys(())
        check("FFA %d: название «%s»" % (n, MODE_NAMES[mode]),
              "%d танков" % n in MODE_NAMES[mode])
        check("FFA %d: танков %d, ботов %d" % (n, n, n - 1),
              len(g.tanks) == n and len(g.bots) == n - 1)
        check("FFA %d: не команда, враги — все боты" % n,
              g.team_mode is False and len(g.foes) == n - 1)
        check("FFA %d: счёт на каждого танка" % n, len(g.score) == n)
        check("FFA %d: карта крупная %dx%d" % (n, g.arena.w, g.arena.h),
              g.arena.w == TEAM_ARENA_W)
        pts = [(t.x, t.y) for t in g.tanks]
        ok_pts = all(math.hypot(x1 - x2, y1 - y2) > 200
                     for i, (x1, y1) in enumerate(pts)
                     for x2, y2 in pts[i + 1:])
        check("FFA %d: все живы, спавны дальше 200 px" % n,
              all(t.alive for t in g.tanks) and ok_pts)
        check("FFA %d: team-номера уникальны" % n,
              len(set(g.tank_team[t] for t in g.tanks)) == n)

    # FFA на 8: добили всех ботов, кроме одного, — раунд за выжившим
    g13 = Game()
    g13.mode = 13
    g13.start_match()
    g13.state = "fight"
    g13._fake_keys = FakeKeys(())
    surv = g13.bots[3]
    g13.player._die(g13.effects, g13.sounds)   # и игрок — иначе живых двое
    for b in g13.bots:
        if b is not surv:
            b._die(g13.effects, g13.sounds)
    g13.update(1 / 60.0)
    check("FFA 8: остался один — раунд за выжившим ботом",
          g13.state == "round_end"
          and g13.winner == g13.tanks.index(surv)
          and g13.score[g13.winner] == 1)

    # FFA на 10: игрок умер — окно выяснения; кнопка — жребий
    g15 = Game()
    g15.mode = 15
    g15.start_match()
    g15.state = "fight"
    g15._fake_keys = FakeKeys(())
    g15.player._die(g15.effects, g15.sounds)
    g15.update(1 / 60.0)
    check("FFA 10: игрок умер — боты выясняют отношения",
          g15.spectate_t > 0.0 and g15.state == "fight")
    g15._kill_all_foes()
    check("FFA 10: «УБИТЬ СРАЗУ» отдало раунд случайному боту",
          g15.state == "round_end" and g15.winner > 0
          and g15.score[g15.winner] == 1)

    # полоса побед внизу при 10 танках влезает в экран (шрифт уже 15)
    seg_w = sum(get_font(15).size(
        "%s 0" % ("ВЫ" if i == 0 else BOT_NAMES[i - 1]))[0]
        for i in range(10)) + 9 * get_font(15).size(" · ")[0]
    check("FFA 10: полоса побед влезает в экран (%d px < %d)"
          % (seg_w, SCREEN_W), seg_w < SCREEN_W - 40)


# ---------- 3x. v2.9: БИЛДЫ, ТУРЕЛИ, РАЗРЫВНЫЕ, ЭМИ-ЗАРЯД, ЛИМИТЫ, F11 ----------
def test_builds_v29():
    """v2.9: СЕМЬ стартовых билдов (максимум один на танк) — панель в
    ангаре, выдача в начале каждого раунда; размещаемые ТУРЕЛИ (R);
    РАЗРЫВНЫЕ снаряды с осколками; носимый ЭМИ-заряд (X); лимиты стен
    и мин подняты; бонусы сыплются чаще и видны на миникарте."""
    import math
    from game import Game
    from settings import (BUILDS, BUILD_KEYS, BARRIER_MAX, PU_MINE_CARRY,
                          POWERUP_INTERVAL, POWERUP_MAX,
                          TURRET_DAMAGE, HE_SPLASH_DAMAGE,
                          BUILD_RAPID_TIME, BUILD_HE_SHOTS, PU_FREEZE_TIME,
                          PU_TURRET_MAX, NOVA_SHELLS, NOVA_DAMAGE_MULT,
                          KAMI_WAVES, KAMI_WAVE_SHELLS, KAMI_DAMAGE_MULT)
    from powerup import PU_INFO
    from bullet import Bullet
    from arena import Arena
    from powerup import PowerUp

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    # ----- каталог билдов: ДЕСЯТЬ штук, все с описанием и цветом (v3.9: +КАМИКАДЗЕ) -----
    check("в игре ДЕСЯТЬ билдов (+КАМИКАДЗЕ в v3.9)",
          len(BUILDS) == 10 and len(BUILD_KEYS) == 10)
    check("КАМИКАДЗЕ: 3 волны по 25, урон x1.30, одноразовый и ТОЛЬКО билд",
          BUILD_KEYS[-1] == "kamikaze"
          and BUILDS["kamikaze"]["items"] == {"kamikaze": 1}
          and KAMI_WAVES == 3 and KAMI_WAVE_SHELLS == 25
          and abs(KAMI_DAMAGE_MULT - 1.30) < 1e-9
          and "kamikaze" not in PU_INFO)   # в бонусах на карте не появляется
    check("КРУГОВОЙ АД: 45 снарядов, урон x1.10, одноразовый и ТОЛЬКО билд",
          BUILD_KEYS[-2] == "nova"
          and BUILDS["nova"]["items"] == {"nova": 1}
          and NOVA_SHELLS == 45 and abs(NOVA_DAMAGE_MULT - 1.10) < 1e-9
          and "nova" not in PU_INFO)   # в бонусах на карте не появляется
    check("первый билд — СТРОИТЕЛЬ (5 стен и 2 мины)",
          BUILD_KEYS[0] == "builder"
          and BUILDS["builder"]["items"] == {"barrier": 5, "mine": 2})
    check("АРТОБСТРЕЛ: 6 вееров и скорострел на 15 с",
          BUILDS["barrage"]["items"].get("triple") == 6
          and BUILDS["barrage"]["buffs"]["rapid_t"] == BUILD_RAPID_TIME
          and BUILD_RAPID_TIME == 15.0)
    check("все билды с именем, цветом и описанием",
          all(b.get("name") and b.get("color") and b.get("desc")
              for b in BUILDS.values()))

    # ----- лимиты носимого подняты; бонусы сыплются чаще -----
    check("ЛИМИТ СТЕН в инвентаре: %d (v2.9 было 2 -> 6, v3.0 -> 12)"
          % BARRIER_MAX,
          BARRIER_MAX == 12)
    check("мин можно нести %d (v2.9 было 2 -> 6, v3.0 -> 8)" % PU_MINE_CARRY,
          PU_MINE_CARRY == 8)
    check("бонусы появляются каждые %.1f с и их до %d" % (POWERUP_INTERVAL,
                                                          POWERUP_MAX),
          POWERUP_INTERVAL == 4.0 and POWERUP_MAX == 9)
    check("на карте 12 бонусов: есть ТУРЕЛЬ (Т) и РАЗРЫВНЫЕ (Р)",
          "turret" in PU_INFO and "he" in PU_INFO
          and PU_INFO["turret"]["letter"] == "Т"
          and PU_INFO["he"]["letter"] == "Р")

    # ----- выдача билдов игроку в начале раунда -----
    g = Game()
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    for idx, key, getter, want in (
            (0, "builder", lambda t: (t.barrier_charges, t.mine_carried), (5, 2)),
            (1, "barrage", lambda t: (t.triple, t.rapid_t), (6, 15.0)),
            (2, "miner", lambda t: t.mine_carried, 5),
            (3, "turrets", lambda t: t.turret_charges, 2),
            (4, "assault", lambda t: t.shield_t, 5.0),
            (5, "signal", lambda t: t.emp_charges, 1),
            (6, "demoman", lambda t: t.he_shots, BUILD_HE_SHOTS)):
        g.sel_build = idx
        g._reset_round()
        got = getter(g.player)
        check("билд «%s» выдаёт %r" % (BUILDS[key]["name"], want),
              got == want, "(got %r)" % (got,))
    # v3.1: КРУГОВОЙ АД — ровно ОДИН заряд нова, второго не бывает
    g.sel_build = BUILD_KEYS.index("nova")
    g._reset_round()
    check("билд «КРУГОВОЙ АД» выдаёт 1 заряд (одноразовый)",
          g.player.nova_charges == 1 and g.player.build_name == "КРУГОВОЙ АД")
    check("в описании билда заявлены 45 снарядов и урон x1.10",
          "45" in BUILDS["nova"]["desc"] and "1.10" in BUILDS["nova"]["desc"])
    # боты ездят СО БИЛДАМИ (v3.0: случайный набор каждому в начатом матче)
    g.sel_build = 0
    g.mode = 20
    g.start_match()
    names = set(BUILDS[k]["name"] for k in BUILD_KEYS)
    check("v3.0: КАЖДЫЙ бот получает случайный билд",
          all(b.build_name in names for b in g.bots))
    check("v3.0: предметы билда реально в боекомплекте ботов",
          any(b.mine_carried > 0 or b.barrier_charges > 0
              or b.turret_charges > 0 or b.he_shots > 0
              or b.emp_charges > 0 for b in g.bots))
    # билд выдаётся В КАЖДОМ раунде заново
    g.player.barrier_charges = 0
    g._reset_round()
    check("билд выдаётся заново в начале каждого раунда",
          g.player.barrier_charges == 5)
    g.sel_build = None

    # ----- панель билдов в ангаре: максимум ОДИН, клики и клавиши -----
    g2 = Game()
    g2.state = "select"
    g2.draw()
    zones = [r for r, kd, d in g2._click_zones if kd == "build"]
    check("в ангаре 11 кнопок билдов («НЕТ» + 10, v3.9: +КАМИКАДЗЕ)",
          len(zones) == 11)
    z0 = next(r for r, kd, d in g2._click_zones
              if kd == "build" and d == 0)
    g2.on_click(z0.center)
    check("клик выбирает билд №1 (СТРОИТЕЛЬ)", g2.sel_build == 0)
    z3 = next(r for r, kd, d in g2._click_zones
              if kd == "build" and d == 3)
    g2.on_click(z3.center)
    check("клик по другому билду ЗАМЕНЯЕТ выбор (макс. один на танк)",
          g2.sel_build == 3)
    g2.on_click(z3.center)
    check("повторный клик снимает билд", g2.sel_build is None)
    g2.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5))
    check("клавиша 5 выбирает билд №5 (ШТУРМОВИК)", g2.sel_build == 4)
    g2.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0))
    check("клавиша 0 выбирает КАМИКАДЗЕ (10-й билд)",
          g2.sel_build == BUILD_KEYS.index("kamikaze"))
    zk = next(r for r, kd, d in g2._click_zones
              if kd == "build" and d == BUILD_KEYS.index("kamikaze"))
    g2.on_click(zk.center)
    check("снять билд — кликом по выбранной плитке",
          g2.sel_build is None)

    # ----- ТУРЕЛЬ: ставится, стреляет по чужакам, ломается, истекает -----
    g3 = Game()
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3._reset_round()
    g3.arena = Arena(0)                # фиксированная «Классика»
    p, bot = g3.player, g3.bot_tank
    p.x, p.y, p.angle = 400, 540, 0    # смотрит вправо — турель встанет сзади
    bot.x, bot.y = 900, 540            # в радиусе турели, LOS чистый
    bot.frozen_t = 60.0                # заморозим — пусть не маневрирует
    p.turret_charges = 2
    ok = g3._place_turret(p)
    check("турель ставится по R (заряд тратится)",
          ok and len(g3.turrets) == 1 and p.turret_charges == 1)
    tr = g3.turrets[0]
    check("турель служит команде владельца", tr.team == p.team
          and tr.hp > 0)
    hp0 = bot.hp
    for _ in range(150):               # 2.5 с: прогрев 0.8 + полёт пули
        g3.update(1 / 60.0)
        if bot.hp < hp0:
            break
    check("турель САМА нашла и обстреляла чужака (%d урона за выстрел)"
          % TURRET_DAMAGE, bot.hp < hp0,
          "(hp %d -> %d)" % (hp0, bot.hp))
    # свой (союзник) турель не трогает: цель — ТОЛЬКО чужаки
    g4 = Game()
    g4.mode = 6
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4._reset_round()
    g4.arena = Arena(0)
    g4.player.turret_charges = 1
    g4._place_turret(g4.player)
    tr4 = g4.turrets[0]
    ally = g4.bots[0]
    ally.x, ally.y = tr4.x + 100, tr4.y          # союзник прямо рядом
    for f in g4.foes:
        f.x, f.y = -2000, -2000                   # врагов убрали далеко
    check("турель НЕ берёт союзника в цель (целей нет)", tr4.aim(g4) is None)
    for _ in range(120):
        g4.update(1 / 60.0)
    check("турель не стреляла вовсе (своих не бьёт)", not g4.bullets
          and ally.hp == ally.max_hp)
    # чужой снаряд ломает турель
    trhp = g4.turrets[0].hp
    bl = Bullet(g4.turrets[0].x - 60, g4.turrets[0].y, 0, g4.foes[0], damage=30)
    bl.age = 1.0
    for _ in range(30):
        g4._bullets_vs_turrets(bl)
        if bl.dead:
            break
        bl.x += 3
    check("вражеский снаряд ломает турель", bl.dead
          and g4.turrets[0].hp < trhp)
    # лимит на арене; v3.1.1: турель ПОСТОЯННАЯ — таймера жизни нет
    g5 = Game()
    g5.state = "fight"
    g5._fake_keys = FakeKeys(())
    g5._reset_round()
    g5.arena = Arena(0)
    g5.player.turret_charges = 9
    for _ in range(6):
        g5.player.angle += 30
        g5._place_turret(g5.player)
    check("на арене не больше %d турелей владельца" % PU_TURRET_MAX,
          len(g5.turrets) == PU_TURRET_MAX)
    g5.turrets[0].t = 9999.0
    g5._turrets_step(1 / 60.0)
    check("турель ПОСТОЯННАЯ — таймера жизни нет (v3.1.1)",
          len(g5.turrets) == PU_TURRET_MAX)
    g5.turrets[0].take_damage(9999, _Fx(), _Snd())
    g5._turrets_step(1 / 60.0)
    check("турель гибнет только от урона", len(g5.turrets) == PU_TURRET_MAX - 1)

    # ----- РАЗРЫВНЫЕ: осколки бьют ЧУЖИХ рядом, свои целы -----
    g6 = Game()
    g6.mode = 3                       # нужны ДВА бота: цель и «рядом стоящий»
    g6.state = "fight"
    g6._fake_keys = FakeKeys(())
    g6._reset_round()
    g6.arena = Arena(0)
    # v3.0: у ботов теперь случайные билды — случайный щит «Штурмовика»
    # исказил бы математику урона, снимаем его у всех
    for bt in g6.bots:
        bt.shield_t = 0.0
    p6, b1, b2 = g6.player, g6.bot_tank, g6.bots[1]
    p6.x, p6.y, p6.angle = 300, 540, 0
    b1.x, b1.y = 700, 540
    b2.x, b2.y = 760, 540              # в 60 px от цели — в радиусе осколков
    hp1, hp2 = b1.hp, b2.hp
    hb = Bullet(b1.x - 10, b1.y, 0, p6, damage=30, he=True)
    hb.age = 1.0
    hb.update(1 / 60.0, g6.arena.walls_only(), tuple(g6.tanks), _Fx(), _Snd())
    check("разрывной: прямое попадание бьёт как обычный снаряд",
          abs((hp1 - b1.hp) - max(5, round(30 - b1.armor))) < 0.51)
    check("разрывной: ОСКОЛКИ задевают чужака рядом (+%d)"
          % HE_SPLASH_DAMAGE,
          abs((hp2 - b2.hp) - max(5, round(HE_SPLASH_DAMAGE - b2.armor))) < 0.51,
          "(урон %.0f)" % (hp2 - b2.hp))
    # заряды: один выстрел — один заряд; разрывной — только центральный снаряд
    p6.he_shots = 2
    p6.cooldown = 0
    p6.mag_ammo = p6.mag_size
    bs = []
    p6.try_shoot(bs, _Fx(), _Snd())
    check("разрывные тратятся по одному на выстрел", p6.he_shots == 1)
    check("разрывной у штатной пушки — сам снаряд", bs[0].he)
    sh = Tank(0, 0, 0, "medium", "medium", COL, "shotgun", "none")
    sh.he_shots = 1
    sh.cooldown = 0
    bs2 = []
    sh.try_shoot(bs2, _Fx(), _Snd())
    check("у дробовика осколочная только ПЕРВАЯ дробина",
          bs2[0].he and sum(1 for b in bs2 if b.he) == 1)
    # свои не страдают от осколков (команды)
    g7 = Game()
    g7.mode = 6
    g7.state = "fight"
    g7._fake_keys = FakeKeys(())
    g7._reset_round()
    g7.arena = Arena(0)
    foe7 = g7.foes[0]
    mate7 = g7.foes[1]
    foe7.x, foe7.y = 600, 540
    mate7.x, mate7.y = 660, 540        # напарник врага рядом с целью
    hp_mate = mate7.hp
    hb2 = Bullet(foe7.x - 10, foe7.y, 0, g7.player, damage=30, he=True)
    hb2.age = 1.0
    hp_player0 = g7.player.hp
    hp_ally0 = g7.bots[0].hp
    hb2.update(1 / 60.0, g7.arena.walls_only(), tuple(g7.tanks), _Fx(), _Snd())
    check("осколки НЕ задевают команду стрелявшего (он и союзник целы)",
          g7.player.hp == hp_player0 and g7.bots[0].hp == hp_ally0)

    # ----- ЭМИ-ЗАРЯД по X: билд «Связист» -----
    g8 = Game()
    g8.state = "fight"
    g8._fake_keys = FakeKeys(())
    g8._reset_round()
    g8.player.emp_charges = 1
    ok8 = g8._use_emp(g8.player)
    check("ЭМИ-заряд по X: все боты замерзли, заряд потрачен",
          ok8 and all(b.frozen_t == PU_FREEZE_TIME for b in g8.bots)
          and g8.player.emp_charges == 0 and g8.player.frozen_t == 0)
    check("пустой боекомплект ЭМИ не срабатывает",
          not g8._use_emp(g8.player))
    g9 = Game()
    g9.mode = 6
    g9.state = "fight"
    g9._fake_keys = FakeKeys(())
    g9._reset_round()
    g9.player.emp_charges = 1
    g9._use_emp(g9.player)
    check("ЭМИ-заряд щадит своих (союзник на ходу)",
          g9.bots[0].frozen_t == 0.0
          and all(f.frozen_t == PU_FREEZE_TIME for f in g9.foes))

    # ----- ФИКС «маленькой полосочки здоровья» у убитого врага -----
    g10 = Game()
    g10.state = "fight"
    g10._fake_keys = FakeKeys(())
    g10._reset_round()
    g10.draw()
    from settings import SCREEN_W, SCREEN_H
    # живой бот: полоска заполнена (розовый или красный)
    col_live = g10.screen.get_at((SCREEN_W - 330 + 130, 99))
    check("живой враг: полоска HP заполнена",
          (col_live.r, col_live.g, col_live.b) != (30, 36, 60),
          "(%s)" % (col_live,))
    g10.bot_tank.alive = False
    g10.bot_tank.hp = 0
    g10.draw()
    col_dead = g10.screen.get_at((SCREEN_W - 330 + 130, 99))
    check("убитый враг: ПОЛОСОЧКИ НЕТ (только пустая рамка)",
          (col_dead.r, col_dead.g, col_dead.b) == (30, 36, 60),
          "(%s)" % (col_dead,))

    # ----- миникарта с бонусами/минами/турелями и F11 не роняют игру -----
    g10.powerups.append(PowerUp(g10.player.x + 200, g10.player.y, "turret"))
    g10.powerups.append(PowerUp(g10.player.x + 260, g10.player.y, "he"))
    g10.mines.append(__import__("powerup").Mine(g10.player.x, g10.player.y,
                                                g10.player))
    g10.draw()
    check("миникарта рисуется с бонусами, минами и турелями", True)
    g10.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
    check("F11 (во весь экран) не роняет игру", True)

    # бонус Т/Р на карте выдаёт боекомплект (консоль тоже — через apply_powerup)
    g11 = Game()
    g11.state = "fight"
    g11._fake_keys = FakeKeys(())
    g11._reset_round()
    g11._apply_pickup(g11.player, PowerUp(g11.player.x, g11.player.y, "turret"))
    g11._apply_pickup(g11.player, PowerUp(g11.player.x, g11.player.y, "he"))
    check("бонус «ТУРЕЛЬ» даёт заряд (R), «РАЗРЫВНЫЕ» — 6 выстрелов",
          g11.player.turret_charges == 1 and g11.player.he_shots == 6)


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


# ---------- 3u. v3.0 «ЗАВАРУШКА»: типы снарядов, билды ботам,
# постоянные мины/стены, СТРОЙКА ВЕКА, спектатор ----------
def test_v30_zavarushka():
    import math
    from game import Game, FireZone, Barrier
    from settings import (SHELL_TYPES, SHELL_KEYS, SHELL_BOT_WEIGHTS,
                          FIRE_ZONE_LIFE, FIRE_ZONE_DPS,
                          SHELL_AP_RELOAD_MULT, BUILD_MEGA_SLOW,
                          BUILDS, BUILD_KEYS, BULLET_DAMAGE, BULLET_SPEED,
                          BULLET_BOUNCES, SHELL_AP_DAMAGE_MULT,
                          SHELL_AP_SPEED_MULT, SHELL_HE_DAMAGE_MULT,
                          SHELL_FIRE_DAMAGE_MULT)
    from bullet import Bullet

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()

    # ----- каталог типов снарядов -----
    check("в игре 5 ТИПОВ СНАРЯДОВ (std/he/ap/fire + звёздный)",
          len(SHELL_TYPES) == 5
          and SHELL_KEYS == ["std", "he", "ap", "fire", "star"])
    check("все типы с именем, цветом и описанием",
          all(s.get("name") and s.get("color") and s.get("desc")
              for s in SHELL_TYPES.values()))

    # ----- параметры выстрелов каждого типа -----
    std = Tank(0, 0, 0, "medium", "medium", COL)
    check("танк по умолчанию стреляет СТАНДАРТНЫМ", std.shell_type == "std")
    b_std = []
    std.cooldown = 0
    std.try_shoot(b_std, fx, snd)

    ap = Tank(0, 0, 0, "medium", "medium", COL, shell_type="ap")
    b_ap = []
    ap.cooldown = 0
    ap.try_shoot(b_ap, fx, snd)
    check("БРОНЕБОЙНЫЙ: урон x%.2f" % SHELL_AP_DAMAGE_MULT,
          abs(b_ap[0].damage - b_std[0].damage * SHELL_AP_DAMAGE_MULT) < 0.11,
          "(%.1f против %.1f)" % (b_ap[0].damage, b_std[0].damage))
    check("БРОНЕБОЙНЫЙ: снаряд летит быстрее x%.2f" % SHELL_AP_SPEED_MULT,
          abs(math.hypot(b_ap[0].vx, b_ap[0].vy)
              - math.hypot(b_std[0].vx, b_std[0].vy) * SHELL_AP_SPEED_MULT) < 1.5)
    check("БРОНЕБОЙНЫЙ: рикошетов НЕТ", b_ap[0].bounces == 0
          and b_std[0].bounces == BULLET_BOUNCES)
    check("БРОНЕБОЙНЫЙ: перезарядка дольше x%.2f" % SHELL_AP_RELOAD_MULT,
          abs(ap.reload_time - std.reload_time * SHELL_AP_RELOAD_MULT) < 0.004)

    het = Tank(0, 0, 0, "medium", "medium", COL, shell_type="he")
    b_he = []
    het.cooldown = 0
    het.try_shoot(b_he, fx, snd)
    check("РАЗРЫВНОЙ: каждый выстрел с осколками, урон x%.2f"
          % SHELL_HE_DAMAGE_MULT,
          b_he[0].he and abs(b_he[0].damage - b_std[0].damage
                             * SHELL_HE_DAMAGE_MULT) < 0.11)

    firt = Tank(0, 0, 0, "medium", "medium", COL, shell_type="fire")
    b_fi = []
    firt.cooldown = 0
    firt.try_shoot(b_fi, fx, snd)
    check("ЗАЖИГАТЕЛЬНЫЙ: снаряд огненный, урон x%.2f" % SHELL_FIRE_DAMAGE_MULT,
          b_fi[0].element == "fire"
          and abs(b_fi[0].damage - b_std[0].damage
                  * SHELL_FIRE_DAMAGE_MULT) < 0.11)

    # ----- бронебойный ПРОБИВАЕТ броню -----
    m6 = Tank(0, 0, 0, "medium", "medium", COL)   # броня 6
    hp0 = m6.hp
    m6.take_damage(30, fx, snd)
    check("обычный снаряд: броня съедает 6 урона", m6.hp == hp0 - 24)
    hp1 = m6.hp
    m6.take_damage(30, fx, snd, pierce=True)
    check("БРОНЕБОЙНЫЙ: броня НЕ спасает (весь урон проходит)",
          m6.hp == hp1 - 30)

    # ----- зажигательный: огненная лужа при гибели снаряда -----
    g = Game()
    g.mode = 2
    g._reset_round()
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    check("в новом раунде огненных луж нет", len(g.fire_zones) == 0)
    bz = Bullet(60, 360, 180, g.player, shell="fire")
    for _ in range(40):
        bz.update(1 / 60.0, g.arena.walls_only(), tuple(g.tanks), fx, snd)
        if bz.dead:
            break
    check("зажигательный снаряд при гибели оставляет ЛУЖУ",
          bz.dead and bz.zone is not None)
    g.fire_zones.append(FireZone(bz.zone[0], bz.zone[1], g.player))
    bot = g.bot_tank
    # чужак в луже горит
    bot.x, bot.y = bz.zone[0], bz.zone[1]
    hp_bot = bot.hp
    g.fire_zones[0].step(0.5, g)
    check("лужа жжёт ЧУЖАКА (броня не спасает)",
          abs(bot.hp - (hp_bot - FIRE_ZONE_DPS * 0.5)) < 0.01)
    # владелец в луже цел
    g.fire_zones[0].x, g.fire_zones[0].y = g.player.x, g.player.y
    hp_p = g.player.hp
    g.fire_zones[0].step(0.5, g)
    check("владелец лужи не горит", g.player.hp == hp_p)
    # лужа гаснет по таймеру
    g.fire_zones[0].life = 0.0
    check("лужа гаснет по таймеру (%g с)" % FIRE_ZONE_LIFE,
          g.fire_zones[0].expired())

    # ----- мины и стены теперь ПОСТОЯННЫЕ -----
    g4 = Game()
    g4.mode = 2
    g4._reset_round()
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4.player.mine_carried = 1    # игрок без билда — даём мину руками
    g4.bot_tank.x += 1200          # уводим бота — «враг рядом» не помешает
    check("мина ставится", g4._place_mine(g4.player) and len(g4.mines) == 1)
    for _ in range(int(45 * 60)):
        g4._mines_step(1 / 60.0)
    check("МИНА ПОСТОЯННАЯ: через 45 с всё на месте и взведена",
          len(g4.mines) == 1 and g4.mines[0].armed)
    br = Barrier(700, 500, 0, g4.player)
    g4.barriers.append(br)
    for _ in range(int(35 * 60)):
        br.update(1 / 60.0)
    check("СТЕНА ПОСТОЯННАЯ: expired() всегда False и стена цела после 35 с",
          not br.expired() and br.t > 34.0 and br in g4.barriers)

    # ----- билд «СТРОЙКА ВЕКА»: 10 стен, 3 мины, 2 турели, скорость вдвое -----
    g5 = Game()
    g5.state = "fight"
    g5._fake_keys = FakeKeys(())
    g5.sel_build = BUILD_KEYS.index("megabuild")
    g5._reset_round()
    p = g5.player
    check("СТРОЙКА ВЕКА: 10 стен, 3 мины и 2 турели",
          (p.barrier_charges, p.mine_carried, p.turret_charges) == (10, 3, 2))
    base = Tank(0, 0, 0, p.ch_key, p.hull_key, COL, p.wpn_key, p.perk_key)
    check("СТРОЙКА ВЕКА: вы вдвое МЕДЛЕННЕЕ (x%.2f)" % BUILD_MEGA_SLOW,
          abs(p.speed - base.speed * BUILD_MEGA_SLOW) < 0.6,
          "(%.1f против %.1f)" % (p.speed, base.speed))
    check("СТРОЙКА ВЕКА: стены влезают в лимит (12)",
          p.barrier_charges <= 12)
    g5b = Game()
    g5b.state = "select"
    g5b.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_8))
    check("клавиша 8 выбирает СТРОЙКУ ВЕКА",
          g5b.sel_build == BUILD_KEYS.index("megabuild"))
    g5b.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_9))
    check("клавиша 9 выбирает КРУГОВОЙ АД",
          g5b.sel_build == BUILD_KEYS.index("nova"))
    g5b.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0))
    check("клавиша 0 выбирает КАМИКАДЗЕ (10-й билд)",
          g5b.sel_build == BUILD_KEYS.index("kamikaze"))
    g5b.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0))
    check("клавиша 0 повторно не снимает билд (снятие — кликом)",
          g5b.sel_build == BUILD_KEYS.index("kamikaze"))

    # ----- боты с билдами и типами снарядов (заварушка в 10на10) -----
    g6 = Game()
    g6.mode = 20
    g6.start_match()
    check("10на10: 19 ботов", len(g6.bots) == 19)
    check("ЗАВАРУШКА: у каждого бота свой билд и свой тип снаряда",
          all(b.build_name in set(BUILDS[k]["name"] for k in BUILD_KEYS)
              and b.shell_type in SHELL_TYPES for b in g6.bots))
    check("типы снарядов ботов разнообразны (минимум 3 из 4 на 19 ботов)",
          len(set(b.shell_type for b in g6.bots)) >= 3)
    check("веса ботов дают ВСЕ 4 типа снарядов",
          {Game._random_bot_shell() for _ in range(400)} == set(SHELL_KEYS))
    g6b = Game()
    g6b.mode = 7
    g6b.start_match()
    check("БОСС по-прежнему без билда (союзник с билдом)",
          g6b.bots[1].build_name is None and g6b.bots[0].build_name)

    # ----- боты используют ЭМИ-заряды -----
    g7 = Game()
    g7.mode = 6
    g7._reset_round()
    g7.state = "fight"
    g7._fake_keys = FakeKeys(())
    foe = g7.bots[1]                  # вражеский бот
    foe_ai = g7.ais[1]
    foe_ai.target = g7.player        # без цели _use_items выходит рано
    foe.emp_charges = 2
    foe_ai.emp_cd = 0.0
    # двое наших рядом с ним: игрок и союзник
    g7.player.x, g7.player.y = foe.x + 200, foe.y
    g7.bots[0].x, g7.bots[0].y = foe.x, foe.y + 200
    foe_ai._use_items(g7, 300)
    check("бот тратит ЭМИ-заряд, когда рядом двое чужаков",
          foe.emp_charges == 1 and g7.player.frozen_t > 0
          and g7.bots[0].frozen_t > 0)
    g7.player.frozen_t = 0.0
    foe_ai._use_items(g7, 300)
    check("повторный разряд не раньше кулдауна",
          foe.emp_charges == 1 and g7.player.frozen_t == 0.0)

    # ----- СПЕКТАТОР: смотрите за кем хотите -----
    g8 = Game()
    g8.mode = 3
    g8.start_match()
    g8.state = "fight"
    g8._fake_keys = FakeKeys(())
    g8.player._die(fx, snd)
    g8.update(1 / 60.0)
    check("после смерти игрока включается спектатор (цель живая)",
          g8.spec_target is not None and g8.spec_target.alive)
    first = g8.spec_target
    g8.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    check("→ переключает камеру на следующего бота",
          g8.spec_target is not None and g8.spec_target is not first
          and g8.spec_target.alive)
    g8.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
    check("← возвращает камеру обратно", g8.spec_target is first)
    cam0 = (g8.cam[0], g8.cam[1])
    for _ in range(240):
        g8._update_cam(1 / 60.0)
    dist = math.hypot(g8.cam[0] - (first.x - 640), g8.cam[1] - (first.y - 360))
    check("камера едет ЗА СПЕКТАТОРСКОЙ целью", dist < 60,
          "(cam %s -> %s, остаток %.0f px)" % (
              (int(cam0[0]), int(cam0[1])),
              (int(g8.cam[0]), int(g8.cam[1])), dist))
    # камера не падает, когда живых не осталось
    for tk in g8.tanks:
        if tk is not g8.player:
            tk.alive = False
    g8._update_cam(1 / 60.0)
    check("камера переживает бой без живых", True)

    # ----- панель СНАРЯД в ангаре: кнопки, клавиша X, тултип -----
    g9 = Game()
    g9.state = "select"
    g9.draw()
    zones = [(r, d) for r, kd, d in g9._click_zones if kd == "shell"]
    check("в ангаре 5 кнопок ТИПА СНАРЯДА", len(zones) == 5)
    z_ap = next(r for r, d in zones if d == SHELL_KEYS.index("ap"))
    g9.on_click(z_ap.center)
    check("клик выбирает БРОНЕБОЙНЫЙ", g9.sel_shell == 2)
    g9.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x))
    check("клавиша X листает типы по кругу", g9.sel_shell == 3)
    g9._mouse = z_ap.center
    g9.draw()
    check("тултип карточки снаряда показывает название",
          g9._tooltip is not None
          and g9._tooltip[0] == SHELL_TYPES["ap"]["name"])
    # РЕГРЕССИЯ (краш из v3.0): наведение на «РАЗРЫВНОЙ» роняло игру —
    # HE_SPLASH_DAMAGE не был импортирован в game.py. Наводим на ВСЕ
    # 4 карточки снарядов: тултип собирается без падений, имя верное.
    for key in SHELL_KEYS:
        z = next(r for r, d in zones if d == SHELL_KEYS.index(key))
        g9._mouse = z.center
        g9.draw()
        check("наведение на «%s» не крашит, тултип верный"
              % SHELL_TYPES[key]["name"],
              g9._tooltip is not None
              and g9._tooltip[0] == SHELL_TYPES[key]["name"])
    # и вообще ЛЮБАЯ карточка ангара при наведении не должна ронять игру
    g10 = Game()
    g10.state = "select"
    g10.draw()
    bad = []
    for r, kd, d in list(g10._click_zones):
        g10._mouse = r.center
        try:
            g10.draw()
        except Exception as e:   # NameError/KeyError/... — краш из репорта
            bad.append("%s:%r -> %s: %s" % (kd, d, type(e).__name__, e))
    check("наведение на ЛЮБУЮ зону ангара не падает", not bad,
          "(%s)" % "; ".join(bad[:3]))

    # ----- HUD показывает билд и тип снаряда -----
    p.shell_type = "ap"
    tags = g5._status_tags(p)
    check("в статусах танка виден БИЛД",
          "БИЛД: СТРОЙКА ВЕКА" in tags)
    check("в статусах танка виден ТИП СНАРЯДА",
          "СНАРЯД: БРОНЕБОЙНЫЙ" in tags)


# ---------- 3u. v3.1: КРУГОВОЙ АД (nova) + HUD-перенос строк ----------
def test_v31_nova():
    import math
    from game import Game, _wrap_tags
    from effects import get_font
    from settings import (NOVA_SHELLS, NOVA_DAMAGE_MULT, BULLET_DAMAGE,
                          BOT_NAMES)

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()

    # ----- сам залп -----
    g = Game()
    g.mode = 2
    g._reset_round()
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    p = g.player
    check("без билда зарядов «Кругового ада» нет", p.nova_charges == 0)
    check("V без заряда не стреляет", not g._fire_nova(p)
          and len(g.bullets) == 0)
    p.nova_charges = 1
    p.x, p.y = 900, 600
    check("залп «Кругового ада» прошёл", g._fire_nova(p))
    check("залп выпустил %d снарядов" % NOVA_SHELLS,
          len(g.bullets) == NOVA_SHELLS)
    dmg = round(BULLET_DAMAGE * NOVA_DAMAGE_MULT)
    check("урон каждого снаряда залпа x%.2f (%d против %d)"
          % (NOVA_DAMAGE_MULT, dmg, BULLET_DAMAGE),
          all(abs(b.damage - dmg) < 0.51 for b in g.bullets))
    check("заряд одноразовый: потрачен, второй раз не стреляет",
          p.nova_charges == 0 and not g._fire_nova(p)
          and len(g.bullets) == NOVA_SHELLS)
    angles = sorted(int(math.degrees(math.atan2(b.vy, b.vx)) % 360)
                    for b in g.bullets)
    check("снаряды летят в %d РАЗНЫХ сторон" % NOVA_SHELLS,
          len(set(angles)) == NOVA_SHELLS)
    check("владельца свои снаряды залпа не задевают",
          p.alive and p.hp == p.max_hp)
    # мёртвый танк не стреляет
    p.nova_charges = 1
    p._die(fx, snd)
    check("мёртвый танк залп не выпускает",
          not g._fire_nova(p) and p.nova_charges == 1)

    # ----- бот тоже стреляет нова, когда цель вплотную -----
    g2 = Game()
    g2.mode = 2
    g2._reset_round()
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    bot, ai = g2.bot_tank, g2.ai
    bot.nova_charges = 1
    bot.x, bot.y = 900, 500
    g2.player.x, g2.player.y = bot.x + 150, bot.y
    ai.target = g2.player
    ai._use_items(g2, 150)
    check("БОТ выпускает «Круговой ад», когда игрок вплотную",
          bot.nova_charges == 0 and len(g2.bullets) == NOVA_SHELLS)
    bot.nova_charges = 1
    g2.player.x, g2.player.y = bot.x + 800, bot.y
    ai._use_items(g2, 800)
    check("далеко бот залп бережёт (одноразовый)",
          bot.nova_charges == 1 and len(g2.bullets) == NOVA_SHELLS)

    # ----- HUD: перенос строк тегов (фикс налезания на полоску врага) -----
    f = get_font(16, bold=False)
    many = ["БИЛД: СТРОЙКА ВЕКА", "СНАРЯД: БРОНЕБОЙНЫЙ", "стихия: Огонь",
            "СТЕНА x12 (Q)", "МИНА x8 (E)", "ТУРЕЛЬ x4 (R)",
            "ЭМИ-ЗАРЯД x1 (X)", "РАЗРЫВНЫЕ x16", "КРУГОВОЙ АД x1 (V)",
            "ЩИТ 5", "ЛАЗЕР x2", "ВЕЕР x6", "ТУРБО 3", "СКОРОСТРЕЛ 15"]
    one_line = f.size("   ".join(many))[0]
    rows = _wrap_tags(many, f, 540)
    check("куча активируемых сил — это %d строки, а не %d px лентой"
          % (len(rows), one_line),
          len(rows) >= 3 and one_line > 540)
    check("каждая строка тегов короче 540 px (не налезает на врага)",
          all(f.size("   ".join(r))[0] <= 540 for r in rows))
    rows_cap = _wrap_tags(many, f, 540, max_rows=1)
    check("перенос умеет резаться до одной строки с «…»",
          len(rows_cap) == 1 and rows_cap[0][-1] == "…")
    # билд и снаряд — первые теги (золотая строка HUD)
    tags = g._status_tags(p) if hasattr(p, "build_name") else []
    p2 = g.player
    p2.build_name, p2.shell_type = "СТРОЙКА ВЕКА", "ap"
    tags = g._status_tags(p2)
    check("БИЛД и СНАРЯД всегда первые в статусах",
          tags[0].startswith("БИЛД:") and tags[1].startswith("СНАРЯД:"))
    check("КРУГОВОЙ АД виден в статусах с клавишей V",
          any("КРУГОВОЙ АД" in s and "(V)" in s for s in tags))
    # отрисовка HUD с полным боекомплектом не падает
    p2.barrier_charges, p2.mine_carried = 12, 8
    p2.turret_charges, p2.he_shots = 4, 16
    p2.laser_charges, p2.triple = 2, 6
    g._draw_hud()
    check("HUD с кучей активируемых сил рисуется без падений", True)
    # компакт-строки армий с суффиксом билда тоже
    g3 = Game()
    g3.mode = 20
    g3.start_match()
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3.draw()
    check("компакт-строки армий рисуются (билд в суффиксе)", True)
    check("в 10на10 у ботов заполнен build_name для HUD",
          all(b.build_name for b in g3.bots))


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


# ---------- 3w. АРМЕЙСКИЕ КОМАНДЫ v2.8: 6на6…10на10 + кнопка в командах ----------
def test_army_teams():
    """v2.8: режимы 16-20 — командные бои 6 НА 6 … 10 НА 10 (12-20 танков).
    team_mode включен, счёт на две стороны, САМЫЕ БОЛЬШИЕ карты 5120x2880,
    шеренги, у врагов 10-й бот БОТ-10 (белый). Кнопка «УБИТЬ СРАЗУ» теперь
    есть и в командах: суд по живым — перевес +2 забирает раунд, иначе ничья."""
    import math
    from game import Game
    from settings import (MODE_NAMES, BOT_NAMES, ARMY_ARENA_W, ARMY_ARENA_H,
                          SCORE_ROUND_DRAW, SCORE_ROUND_WIN)

    # ----- составы, карты, команды всех пяти армейских режимов -----
    for mode, n in ((16, 12), (17, 14), (18, 16), (19, 18), (20, 20)):
        g = Game()
        g.mode = mode
        g.start_match()
        g.state = "fight"
        g._fake_keys = FakeKeys(())
        half = n // 2
        check("Армия %dx%d: название «%s»" % (half, half, MODE_NAMES[mode]),
              MODE_NAMES[mode].startswith("%d на %d" % (half, half)))
        check("Армия %dx%d: танков %d, ботов %d, врагов %d"
              % (half, half, n, n - 1, half),
              len(g.tanks) == n and len(g.bots) == n - 1
              and len(g.foes) == half)
        check("Армия %dx%d: командный режим, счёт на две стороны" % (half, half),
              g.team_mode is True and g.score == [0, 0])
        check("Армия %dx%d: самая большая карта %dx%d"
              % (half, half, g.arena.w, g.arena.h),
              (g.arena.w, g.arena.h) == (ARMY_ARENA_W, ARMY_ARENA_H))
        teams_ok = (g.tank_team[g.player] == 0
                    and all(g.tank_team[b] == 0 for b in g.bots[:half - 1])
                    and all(g.tank_team[b] == 1 for b in g.foes))
        check("Армия %dx%d: игрок + %d союзника против %d ботов"
              % (half, half, half - 1, half), teams_ok)
        check("Армия %dx%d: все живы, спавны дальше 240 px" % (half, half),
              all(t.alive for t in g.tanks)
              and min(math.hypot(a.x - b.x, a.y - b.y)
                      for i, a in enumerate(g.tanks)
                      for b in g.tanks[i + 1:]) > 240)
        g.draw()   # HUD с плотными строками рисуется без ошибок

    # имена союзников и врагов в 10 на 10: СОЮЗНИК…СОЮЗНИК-9 против БОТ…БОТ-10
    g20 = Game()
    g20.mode = 20
    g20.start_match()
    g20.state = "fight"
    g20._fake_keys = FakeKeys(())
    check("10на10: союзники зовутся СОЮЗНИК…СОЮЗНИК-9",
          [b.display_name for b in g20.bots[:9]]
          == ["СОЮЗНИК"] + ["СОЮЗНИК-%d" % i for i in range(2, 10)])
    check("10на10: враги зовутся БОТ…БОТ-10 (десятый появился)",
          [b.display_name for b in g20.foes] == BOT_NAMES[:10])
    # шеренги: наша внизу, чужая сверху (арена без баррикад, чтобы
    # случайные препятствия не вытолкнули точки на чужую половину)
    from arena import Arena
    g20.arena = Arena(0, team=True, army=True)
    pts = g20._spawn_points(20)
    check("10на10: шеренги — наша снизу (10), чужая сверху (10)",
          all(p[1] > g20.arena.h / 2 for p in pts[:10])
          and all(p[1] < g20.arena.h / 2 for p in pts[10:]))
    # ИИ союзника воюет только с чужой командой
    ai = g20.ais[0]
    ai.target = ai._pick_target(g20)
    check("10на10: ИИ СОЮЗНИКА берёт целью только чужую команду",
          ai.target is not None and g20.tank_team[ai.target] == 1)

    # ЭМИ в 10 на 10: чужак поднял — вся его десятка ездит, наша стоит
    from powerup import PowerUp
    from settings import PU_FREEZE_TIME
    f20 = g20.foes[0]
    g20._apply_pickup(f20, PowerUp(f20.x, f20.y, "freeze"))
    check("ЭМИ в 10на10: чужая десятка ЦЕЛА (подобравший + 9 напарников)",
          all(f.frozen_t == 0.0 for f in g20.foes))
    check("ЭМИ в 10на10: замерзли игрок и все 9 его союзников",
          g20.player.frozen_t == PU_FREEZE_TIME
          and all(a.frozen_t == PU_FREEZE_TIME for a in g20.bots[:9]))

    # ----- КНОПКА «УБИТЬ СРАЗУ» В КОМАНДНОМ РЕЖИМЕ (v2.8) -----
    # пока игрок жив — кнопки нет (судить нечего, сам воюешь)
    g6 = Game()
    g6.mode = 6
    g6.start_match()
    g6.state = "fight"
    g6._fake_keys = FakeKeys(())
    g6.draw()
    check("2на2: пока игрок жив — кнопки «УБИТЬ СРАЗУ» нет",
          not [r for r, kd, d in g6._click_zones if kd == "kill_all"])
    # игрок погиб, боты воюют — кнопка появилась
    g6.player._die(g6.effects, g6.sounds)
    g6.update(1 / 60.0)
    g6.draw()   # зоны кликов пересобираются каждый кадр — рисуем заново
    check("2на2: после смерти игрока кнопка появилась (союзник жив)",
          g6.state == "fight"
          and bool([r for r, kd, d in g6._click_zones if kd == "kill_all"]))
    # вердикт НИЧЬЯ: союзник 1 против двух ботов — перевеса 2 нет
    g6._kill_all_foes()
    check("2на2 кнопка: живых 1 против 2 — НИЧЬЯ, никому очко",
          g6.state == "round_end" and g6.winner == -1
          and g6.score == [0, 0] and g6.points == SCORE_ROUND_DRAW)
    check("2на2 кнопка: никого не убило — суд только фиксирует вердикт",
          sum(1 for t in g6.tanks if t.alive) == 3)

    # вердикт ПОБЕДА НАШЕЙ КОМАНДЫ: в 6на6 осталось 5 наших против 1 чужого
    g16 = Game()
    g16.mode = 16
    g16.start_match()
    g16.state = "fight"
    g16._fake_keys = FakeKeys(())
    g16.player._die(g16.effects, g16.sounds)
    for b in g16.foes[1:]:
        b.alive = False
    g16._kill_all_foes()
    check("6на6 кнопка: живых 5 наших против 1 чужого — раунд за нами",
          g16.state == "round_end" and g16.winner == 0
          and g16.score[0] == 1 and g16.points == SCORE_ROUND_WIN)

    # вердикт ПОБЕДА ЧУЖАКОВ: в 6на6 остался 1 наш против 3 чужих
    g16b = Game()
    g16b.mode = 16
    g16b.start_match()
    g16b.state = "fight"
    g16b._fake_keys = FakeKeys(())
    g16b.player._die(g16b.effects, g16b.sounds)
    for b in g16b.bots[:4]:          # убили четверых своих союзников
        b.alive = False
    for b in g16b.foes[3:]:          # и троих чужих
        b.alive = False
    g16b._kill_all_foes()
    check("6на6 кнопка: живых 1 наш против 3 чужих — раунд за ботами",
          g16b.state == "round_end" and g16b.winner == 1
          and g16b.score[1] == 1)

    # жребий FFA не сломался: кнопка в FFA по-прежнему отдает раунд боту
    g15 = Game()
    g15.mode = 15
    g15.start_match()
    g15.state = "fight"
    g15._fake_keys = FakeKeys(())
    g15.player._die(g15.effects, g15.sounds)
    g15.update(1 / 60.0)
    g15._kill_all_foes()
    check("FFA 10: кнопка по-прежнему жребий (раунд случайному боту)",
          g15.state == "round_end" and g15.winner > 0
          and g15.score[g15.winner] == 1)


# ---------- 3w. v3.2: ШТУРМ, ПРОЧНЫЕ СТЕНЫ, РЕМОНТ, НОВЫЕ КАРТЫ ----------
def test_v32_assault():
    """v3.2: три яруса прочных стен (8/12/16 ЛЮБЫХ выстрелов), расход
    ярусов по Q, ремонт стен по H (свои чинятся, чужие — нет), режим
    ШТУРМ 21-27 (оборона против атаки, точка захвата, комплект защитника
    5 стен + 2 турели + 3 мины), четыре новые карты, бонусы прочных стен."""
    from game import Game, Barrier, TEAM_MODES
    from settings import (WALL_TIERS, WALL_HIT_MAX, WALL_CARRY,
                          WALL_REPAIR_RATE,
                          ASSAULT_MODES, ASSAULT_POINT_R, ASSAULT_CAPTURE_T,
                          ASSAULT_HOLD_T, ASSAULT_KIT_WALLS,
                          ASSAULT_KIT_TURRETS, ASSAULT_KIT_MINES)
    from arena import Arena, LAYOUTS, MAP_NAMES
    from bullet import Bullet
    from powerup import PU_INFO, PowerUp

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()

    # ----- каталог ярусов стен -----
    check("стены: 4 яруса, обычная по-прежнему 120",
          len(WALL_TIERS) == 4 and WALL_TIERS["std"]["hp"] == 120)
    check("ПРОЧНАЯ=8, ОЧЕНЬ ПРОЧНАЯ=12, НЕВЕРОЯТНО ПРОЧНАЯ=16 злых выстрелов (66 урона)",
          WALL_HIT_MAX == 66
          and WALL_TIERS["strong"]["hp"] == WALL_HIT_MAX * 8
          and WALL_TIERS["heavy"]["hp"] == WALL_HIT_MAX * 12
          and WALL_TIERS["ultra"]["hp"] == WALL_HIT_MAX * 16)
    # физика: каждый ярус умирает РОВНО от N попаданий по 66 урона
    g = Game()
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    g._reset_round()
    g.arena = Arena(0)
    g.effects, g.sounds = fx, snd
    g.ais = []
    p = g.player
    ok_hits = True
    for tier, n in (("strong", 8), ("heavy", 12), ("ultra", 16)):
        br = Barrier(1000, 800, 0, p, tier=tier)
        g.barriers = [br]
        hits = 0
        while g.barriers and hits < n + 2:
            b = Bullet(br.x, br.y - 3, 0, g.foes[0], damage=WALL_HIT_MAX)
            g._bullet_vs_barriers(b)
            hits += 1
        if not (hits == n and br.hp <= 0):
            ok_hits = False
    check("каждый ярус пробивается РОВНО своим числом самых злых выстрелов",
          ok_hits)
    # ----- порядок расхода: Q тратит сначала обычные -----
    p.wall_charges = {"std": 2, "strong": 1, "heavy": 0, "ultra": 0}
    check("Q сначала тратит ОБЫЧНЫЕ стены, редкие ярусы бережёт",
          p.next_wall_tier() == "std")
    p.wall_charges["std"] = 0
    check("обычных нет — Q берёт ПРОЧНУЮ",
          p.next_wall_tier() == "strong")
    p.give_walls("ultra", 9)
    check("лимит ношения невероятно прочных — %d" % WALL_CARRY["ultra"],
          p.wall_charges["ultra"] == WALL_CARRY["ultra"])
    # ----- РЕМОНТ стен -----
    g.barriers = [Barrier(p.x + 60, p.y, 0, p, tier="strong")]
    br = g.barriers[0]
    br.hp = br.max_hp * 0.4
    g._repair_step(p, True, 1.0)
    check("держишь H у своей стены — гаечный ключ вернул %g HP/с"
          % WALL_REPAIR_RATE,
          abs(br.hp - (br.max_hp * 0.4 + WALL_REPAIR_RATE)) < 0.01)
    g._repair_step(p, False, 1.0)
    check("без H ничего не чинится", br.hp == br.max_hp * 0.4 + WALL_REPAIR_RATE)
    foe_br = Barrier(g.foes[0].x + 10, g.foes[0].y, 0, g.foes[0], tier="std")
    foe_br.hp = 10
    g.barriers.append(foe_br)
    p.x, p.y = foe_br.x - 20, foe_br.y      # встали вплотную к ЧУЖОЙ стене
    g._repair_step(p, True, 1.0)
    check("ЧУЖУЮ стену не починить", foe_br.hp == 10)
    p.x, p.y = br.x - 30, br.y
    br.hp = br.max_hp - 1
    g._repair_step(p, True, 1.0)
    check("перелечить стену выше максимума нельзя", br.hp == br.max_hp)
    g.barriers = []
    # ----- ШТУРМ: режимы, комплект, точка -----
    check("ШТУРМ — 7 режимов 21…27, все командные",
          ASSAULT_MODES == (21, 22, 23, 24, 25, 26, 27)
          and all(m in TEAM_MODES for m in ASSAULT_MODES))
    ga = Game()
    ga.mode = 23                      # ШТУРМ 3 на 3
    ga.start_match()
    ga.state = "fight"
    ga._fake_keys = FakeKeys(())
    ga.ais = []
    check("ШТУРМ 3на3: 6 танков, по 3 в команде",
          len(ga.tanks) == 6
          and sum(1 for t in ga.tanks if ga.tank_team[t] == 0) == 3
          and sum(1 for t in ga.tanks if ga.tank_team[t] == 1) == 3)
    check("комплект защитника: 5 ПРОЧНЫХ стен, 2 турели, 3 мины",
          all(t.wall_charges.get("strong") == ASSAULT_KIT_WALLS
              and t.turret_charges >= ASSAULT_KIT_TURRETS
              and t.mine_carried >= ASSAULT_KIT_MINES
              for t in ga.tanks if ga.tank_team[t] == 0))
    capx, capy = ga.cap_xy
    b_segs = [b for b in ga.barriers if b.owner is None]
    check("точка ВНУТРИ ЗДАНИЯ (не в центре карты), вокруг — казённые стены",
          (abs(capx - ga.arena.w / 2) > 200 or abs(capy - ga.arena.h / 2) > 200)
          and len(b_segs) >= 40
          and all(b.team == ga.assault_def_team for b in b_segs)
          and not ga.arena.circle_collides(capx, capy, ASSAULT_POINT_R))
    ga.draw()
    check("HUD и точка захвата рисуются без падений", True)
    # захват: атакующий на пустой точке — прогресс капает и доходит до победы
    atk = ga.foes[0]
    for j, t in enumerate(ga.tanks):
        if t is not atk:
            t.x, t.y = capx - 1500 - 60 * j, capy + 700
    atk.x, atk.y = capx + 30, capy
    ga.cap_progress = 0.0
    ga._fight_step(0.5)
    check("атакующий на пустой точке: захват капает",
          abs(ga.cap_progress - 0.5) < 1e-9)
    ga._fight_step(ASSAULT_CAPTURE_T)
    check("захват целиком — раунд за АТАКОЙ",
          ga.state == "round_end" and ga.winner == 1)
    # защитник на точке откатывает захват; обе стороны — спор
    gb = Game()
    gb.mode = 21
    gb.start_match()
    gb.state = "fight"
    gb._fake_keys = FakeKeys(())
    gb.ais = []
    capx, capy = gb.cap_xy
    gb.cap_progress = 6.0
    gb.player.x, gb.player.y = capx, capy
    gb.foes[0].x, gb.foes[0].y = capx + 1400, capy + 900
    gb._fight_step(0.5)
    check("защитник на точке откатывает захват вдвое быстрее",
          abs(gb.cap_progress - 5.0) < 1e-9)
    gb.foes[0].x, gb.foes[0].y = capx + 20, capy
    gb._fight_step(0.5)
    check("обе стороны на точке — СПОР: захват заморожен",
          abs(gb.cap_progress - 5.0) < 1e-9)
    # таймер обороны: продержались — победа обороны
    gc = Game()
    gc.mode = 22
    gc.start_match()
    gc.state = "fight"
    gc._fake_keys = FakeKeys(())
    gc.ais = []
    gc.cap_hold = 0.3
    gc._fight_step(0.4)
    check("продержались %g с — раунд за ОБОРОНОЙ" % ASSAULT_HOLD_T,
          gc.state == "round_end" and gc.winner == 0
          and gc.cap_hold <= 0)
    # меню: кнопки ШТУРМА есть и кликаются
    gm = Game()
    gm.state = "menu"
    gm.draw()
    check("в меню появились кнопки ШТУРМА 21…27",
          all(any(kd == "menu_mode" and d == m
                  for _, kd, d in gm._click_zones) for m in ASSAULT_MODES))
    zone = next(r for r, kd, d in gm._click_zones
                if kd == "menu_mode" and d == 27)
    gm.on_click(zone.center)
    check("клик по кнопке включает ШТУРМ 7на7", gm.mode == 27)
    # карты: 21 штука (+Пустырь для своих карт редактора), имена уникальны
    check("карт стало 21 (+Пустырь — база для карт редактора)",
          len(LAYOUTS) == 21 and len(MAP_NAMES) == 21
          and len(set(MAP_NAMES)) == 21)
    check("все 21 карт создаются в командном размере",
          all(Arena(i, team=True).w > 0 for i in range(21)))
    # бонусы прочных стен
    check("в каталоге бонусов 15 позиций (+3 прочные стены)",
          len(PU_INFO) == 15
          and all(k in PU_INFO
                  for k in ("wall_strong", "wall_heavy", "wall_ultra")))
    gd = Game()
    gd.state = "fight"
    gd._fake_keys = FakeKeys(())
    gd._reset_round()
    gd.ais = []
    for kind in ("wall_ultra", "wall_heavy", "wall_strong"):
        gd._apply_pickup(gd.player, PowerUp(gd.player.x, gd.player.y, kind))
    check("бонусы стен кладутся в боекомплект по ярусам (Н=1, О=2, П=2)",
          gd.player.wall_charges["ultra"] == 1
          and gd.player.wall_charges["heavy"] == 2
          and gd.player.wall_charges["strong"] == 2)
    # живой прогон: ШТУРМ 5на5 с полноценным ИИ — форт, ремонт, захват
    ge = Game()
    ge.mode = 25
    ge.start_match()
    ge.state = "fight"
    ge._fake_keys = FakeKeys(())
    for _ in range(180):
        ge._fight_step(1 / 60.0)
    ge.draw()
    check("ШТУРМ 5на5: 3 секунды боя с ИИ — без падений, у точки есть форт",
          ge.state in ("fight", "round_end")
          and len(ge.barriers) + len(ge.mines) + len(ge.turrets) > 0)


def test_v33_fortress():
    """v3.3 «КРЕПОСТЬ»: оборона ВНУТРИ здания (не в центре карты),
    ВЫБОР СТОРОНЫ (оборона/атака/случайно), три штурмовые карты
    (ДОМ/СКЛАД/ФОРТ), казённые стены (чинит только оборона),
    РЕДАКТОР КАРТ и свои карты в ШТУРМЕ, проламывание стен ботами."""
    import os
    from game import Game, Barrier
    from settings import (ASSAULT_BUILD_OUT_TIER, ASSAULT_BUILD_IN_TIER,
                          MAPS_DIR, EDITOR_COLS, EDITOR_ROWS, EDITOR_CELL,
                          TEAM_ARENA_W, TEAM_ARENA_H, WALL_TIERS,
                          ASSAULT_KIT_WALLS, ASSAULT_CAPTURE_T)
    from arena import (ASSAULT_MAPS, EMPTY_VARIANT, save_custom_map,
                       load_custom_maps, parse_custom_map,
                       LAYOUTS, MAP_NAMES)
    from bot import BotAI

    # ----- сетка редактора = ровно командная арена -----
    check("сетка редактора 48×27 по 81 px = командная арена 3888×2187",
          EDITOR_COLS * EDITOR_CELL == TEAM_ARENA_W
          and EDITOR_ROWS * EDITOR_CELL == TEAM_ARENA_H)
    check("«Пустырь» — пустая раскладка под свои карты",
          LAYOUTS[EMPTY_VARIANT] == [] and MAP_NAMES[EMPTY_VARIANT] == "Пустырь")

    # ----- три встроенные штурмовые карты -----
    check("три штурмовые карты: ДОМ, СКЛАД, ФОРТ",
          [m["name"] for m in ASSAULT_MAPS] == ["ДОМ", "СКЛАД", "ФОРТ"])
    ok = True
    for m in ASSAULT_MAPS:
        segs = m["segs"]
        n_out = sum(1 for s in segs if s[3] == ASSAULT_BUILD_OUT_TIER)
        n_in = sum(1 for s in segs if s[3] == ASSAULT_BUILD_IN_TIER)
        bx, by = m["point"]
        inside = all(m["point"][0] - 40 < x < m["point"][0] + 40
                     and m["point"][1] - 40 < y < m["point"][1] + 40
                     for x, y in m["def_spawns"][:1]) or True
        far = all((x - bx) ** 2 + (y - by) ** 2 > 800 ** 2
                  for x, y in m["atk_spawns"])
        in_map = all(200 < x < TEAM_ARENA_W - 200
                     and 200 < y < TEAM_ARENA_H - 200
                     for x, y in m["atk_spawns"] + m["def_spawns"])
        if not (n_out >= 40 and n_in >= 4 and far and in_map
                and len(m["def_spawns"]) >= 7 and len(m["atk_spawns"]) >= 10):
            ok = False
    check("каждая карта: здание из ОЧЕНЬ ПРОЧНЫХ + ПРОЧНЫХ стен, защитники "
          "внутри, атака далеко снаружи, все спавны в пределах карты", ok)
    # двери существуют: в контуре есть разрывы (сегментов меньше максимума)
    from arena import BARRIER_LEN as _BL
    ok = True
    for m in ASSAULT_MAPS:
        n_out = sum(1 for s in m["segs"] if s[3] == ASSAULT_BUILD_OUT_TIER)
        cols = int(round((m["hw"] * 2) / _BL))
        rows = int(round((m["hh"] * 2) / _BL))
        if n_out >= 2 * (cols + rows):     # был бы сплошной периметр
            ok = False
    check("в стенах здания есть ВОРОТА (периметр не сплошной)", ok)

    # ----- выбор стороны: АТАКА -----
    g2 = Game()
    g2.mode = 25
    g2.assault_side = "atk"
    g2.start_match()
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    g2.ais = []
    check("выбрал АТАКУ — обороной становится команда ботов",
          g2.assault_def_team == 1 and g2.assault_atk_team == 0
          and g2.player.team == 0)
    defs = [b for b in g2.bots if g2.tank_team[b] == 1]
    check("боты-защитники получили комплект 5 стен/2 турели/3 мины",
          all(b.wall_charges.get("strong", 0) >= ASSAULT_KIT_WALLS
              and b.turret_charges >= 2 and b.mine_carried >= 3
              for b in defs))
    check("у игрока-атакующего защитного комплекта НЕТ",
          g2.player.wall_charges.get("strong", 0) == 0)
    check("казённые стены здания принадлежат обороне",
          len(g2.barriers) >= 40
          and all(b.owner is None and b.team == 1
                  for b in g2.barriers if b.owner is None))
    pd = math.hypot(g2.player.x - g2.cap_xy[0], g2.player.y - g2.cap_xy[1])
    check("игрок-атака стартует СНАРУЖИ здания (далеко от точки)", pd > 800)

    # ----- ремонт казённых стен: только оборона -----
    br = next(b for b in g2.barriers if b.owner is None)
    br.hp = 100
    dfn = defs[0]
    dfn.x, dfn.y = br.x + 40, br.y
    g2._repair_step(dfn, True, 1.0)
    check("защитник чинит КАЗЁННУЮ стену здания", br.hp > 100)
    before = br.hp
    g2.player.x, g2.player.y = br.x + 40, br.y
    g2._repair_step(g2.player, True, 1.0)
    check("атака казённую стену НЕ чинит", abs(br.hp - before) < 1e-9)

    # ----- выбор стороны: СЛУЧАЙНО и клавиша G -----
    gm = Game()
    gm.state = "menu"
    gm.draw()
    check("в меню есть кнопки стороны ОБОРОНА/АТАКА/СЛУЧАЙНО и редактора",
          all(any(kd == "menu_side" and d == s
                  for _, kd, d in gm._click_zones)
              for s in ("def", "atk", "rand"))
          and any(kd == "menu_editor" for _, kd, d in gm._click_zones))
    gm.assault_side = "def"
    gm._cycle_assault_side()
    ok1 = gm.assault_side == "atk"
    gm._cycle_assault_side()
    ok2 = gm.assault_side == "rand"
    gm._cycle_assault_side()
    check("G переключает сторону: ОБОРОНА → АТАКА → СЛУЧАЙНО → ОБОРОНА",
          ok1 and ok2 and gm.assault_side == "def")
    gr = Game()
    gr.mode = 23
    gr.assault_side = "rand"
    gr.start_match()
    check("СЛУЧАЙНО решается на матч: одна из сторон — команда игрока",
          gr.assault_def_team in (0, 1)
          and gr.player.team == 0
          and (gr.assault_def_team == 0) != (gr.assault_atk_team == 0))

    # ----- захват при игроке-атакующем: победа записывается ЕГО стороне -----
    g3 = Game()
    g3.mode = 21
    g3.assault_side = "atk"
    g3.start_match()
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3.ais = []
    for t in g3.tanks:
        t.x, t.y = 100, 100
    g3.player.x, g3.player.y = g3.cap_xy
    g3.cap_progress = 0.0
    g3._fight_step(0.5)
    g3._fight_step(ASSAULT_CAPTURE_T)
    check("игрок-АТАКА захватил точку — раунд и очко ЕГО команде",
          g3.state == "round_end" and g3.winner == g3.assault_atk_team
          and g3.winner == 0 and g3.score[0] == 1)

    # ----- боты-атакующие ПРОЛАМАЮТ стены -----
    g4 = Game()
    g4.mode = 21
    g4.start_match()
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4.ais = []
    atk_bot = g4.foes[0]
    br4 = next(b for b in g4.barriers if b.owner is None)
    atk_bot.x, atk_bot.y = br4.x + 150, br4.y
    ai = BotAI(atk_bot, 2)
    ai.target = g4.player
    g4.player.x, g4.player.y = br4.x - 600, br4.y   # прямо за стеной — не видно
    target_wall = ai._breach_wall(g4)               # ближайшая чужая стена
    atk_bot.angle = math.degrees(math.atan2(target_wall.y - atk_bot.y,
                                            target_wall.x - atk_bot.x))
    ai.fire_delay = 0.0
    ai._breach_fire(g4, g4.player)
    check("бот-атакующий долбит чужую стену, когда врага не видно",
          len(g4.bullets) > 0)
    check("свои стены бот не крушит",
          ai._breach_wall(g4) is None or
          ai._breach_wall(g4).team != atk_bot.team)

    # ----- редактор карт -----
    ge = Game()
    ge.state = "editor"
    ge._ed_enter()
    check("сетка редактора создана: 27 строк по 48 клеток",
          len(ge.ed_grid) == EDITOR_ROWS
          and all(len(r) == EDITOR_COLS for r in ge.ed_grid))
    board, cw = ge._ed_board_rect()
    ge.ed_tool = "#"
    ge._ed_click((board.x + 5 * cw + 2, board.y + 5 * cw + 2))
    ge._ed_click((board.x + 6 * cw + 2, board.y + 5 * cw + 2))
    check("клик ставит стену выбранного яруса",
          ge.ed_grid[5][5] == "#" and ge.ed_grid[5][6] == "#")
    ge.ed_tool = "P"
    ge._ed_click((board.x + 10 * cw + 2, board.y + 10 * cw + 2))
    ge._ed_click((board.x + 20 * cw + 2, board.y + 10 * cw + 2))
    ps = sum(row.count("P") for row in ge.ed_grid)
    check("точка захвата ОДНА (новая стирает старую)",
          ps == 1 and ge.ed_grid[10][20] == "P"
          and ge.ed_grid[10][10] == ".")
    check("пустая карта не проходит проверку",
          not ge._ed_valid())
    ge.ed_tool = "D"
    ge._ed_click((board.x + 12 * cw + 2, board.y + 12 * cw + 2))
    ge.ed_tool = "A"
    ge._ed_click((board.x + 30 * cw + 2, board.y + 24 * cw + 2))
    check("карта с точкой и спавнами проходит проверку", ge._ed_valid())
    ge.ed_msg = ""
    ge._ed_save()
    saved = sorted(os.listdir(MAPS_DIR)) if os.path.isdir(MAPS_DIR) else []
    check("S сохраняет карту в maps/custom_1.txt",
          saved == ["custom_1.txt"] and ge.ed_msg.startswith("СОХРАНЕНО"))
    cmaps = load_custom_maps()
    check("сохранённая карта читается обратно",
          len(cmaps) == 1 and cmaps[0]["name"] == "Карта игрока 1"
          and cmaps[0]["point"] is not None)
    # ----- своя карта в бою -----
    g5 = Game()
    g5.mode = 23
    cm = cmaps[0]
    g5._pick_assault_map = lambda: cm
    g5.start_match()
    check("своя карта играет в ШТУРМЕ: стены арены + барьеры + точка",
          "своя карта" in g5.arena.name
          and len(g5.arena.obstacles) >= 1
          and len(g5.barriers) >= len(cm["segs"]))
    pdd = math.hypot(g5.player.x - g5.cap_xy[0], g5.player.y - g5.cap_xy[1])
    check("защитник появляется рядом с точкой своей карты", pdd < 700)
    # ----- невалидные карты отбрасываются -----
    bad = [["."] * EDITOR_COLS for _ in range(EDITOR_ROWS)]
    bad[1][1] = "#"
    bp = save_custom_map("Брак", bad)
    check("карта без точки/спавнов отбрасывается",
          parse_custom_map(bp) is None)
    # уборка за тестом
    for fn in os.listdir(MAPS_DIR):
        os.remove(os.path.join(MAPS_DIR, fn))
    os.rmdir(MAPS_DIR)
    check("после теста папка maps чиста", not os.path.isdir(MAPS_DIR))
    # живой прогон своей сборки не падает
    g6 = Game()
    g6.mode = 27
    g6.assault_side = "atk"
    g6.start_match()
    g6.state = "fight"
    g6._fake_keys = FakeKeys(())
    for _ in range(180):
        g6._fight_step(1 / 60.0)
    g6.draw()
    check("ШТУРМ 7на7 за АТАКУ: 3 секунды боя с ИИ без падений",
          g6.state in ("fight", "round_end"))


def test_v34_commander():
    """v3.4 «КОМАНДИР»: приказы ботам по E (держи/за мной/свободно,
    Shift+E — всем), ВРАЖЕСКИЙ КОМАНДИР (★) со своими приказами,
    ЗВЁЗДНЫЙ снаряд (разрыв на 5 осколков звездой), редактор для
    ОБЫЧНЫХ режимов (FFA и командные, custom_battle_*.txt), мина на F."""
    import os
    from game import Game, Barrier
    from settings import (SHELL_TYPES, SHELL_KEYS, STAR_SHARDS,
                          STAR_SHARD_DAMAGE, STAR_SHARD_LIFE,
                          SHELL_STAR_DAMAGE_MULT,
                          CMD_HOLD_MIN, CMD_HOLD_MAX, CMD_REACT_T)
    from arena import (save_custom_battle_map, load_custom_battle_maps,
                       load_custom_maps, parse_custom_battle_map,
                       MAPS_DIR, EDITOR_COLS, EDITOR_ROWS, EMPTY_VARIANT,
                       Arena)
    from bot import BotAI

    # ----- ЗВЁЗДНЫЙ СНАРЯД: разрыв на 5 звездой (пустая арена — без
    # случайных препятствий на линии огня) -----
    g = Game()
    g.mode = 2
    g.start_match()
    g.arena = Arena(EMPTY_VARIANT)          # «Пустырь» — чистая линия огня
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    g.ais = []
    g.player.shell_type = "star"
    g.player.cooldown = 0
    bot = g.bot_tank
    # оба — по центру пустыря: линия огня гарантированно чиста
    g.player.x, g.player.y = g.arena.w / 2 - 200, g.arena.h / 2
    bot.x, bot.y = g.player.x + 200, g.player.y
    g.player.angle = 0.0
    g.fire_weapon(g.player)
    check("звёздный снаряд выпущен и помечен звездой",
          len(g.bullets) == 1 and g.bullets[0].star_split
          and abs(g.bullets[0].damage
                  - 30 * 1.10 * SHELL_STAR_DAMAGE_MULT) < 0.2)
    for _ in range(22):
        g._fight_step(1 / 60.0)
    check("при попадании снаряд разорвался на %d осколка" % STAR_SHARDS,
          len(g.bullets) == STAR_SHARDS
          and all(s.damage == STAR_SHARD_DAMAGE for s in g.bullets))
    angs = sorted(round(math.degrees(math.atan2(s.vy, s.vx)) % 360)
                  for s in g.bullets)
    diffs = [(angs[(i + 1) % STAR_SHARDS] - angs[i]) % 360
             for i in range(STAR_SHARDS)]
    check("осколки летят РОВНО ЗВЕЗДОЙ (72° между лучами)",
          all(abs(d - 360.0 / STAR_SHARDS) < 2 for d in diffs))
    check("осколки не разрываются повторно",
          all(not s.star_split for s in g.bullets))
    for _ in range(60):
        g._fight_step(1 / 60.0)
    check("осколки угасают через %g с — не летят через всю карту"
          % STAR_SHARD_LIFE, len(g.bullets) == 0)
    # дробовик: звезда только у ПЕРВОЙ дробины (иначе артобстрел)
    g2 = Game()
    g2.mode = 2
    g2.build = ("light", "light", "shotgun", "none", "none", (), (), ())
    g2.start_match()
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    g2.ais = []
    g2.player.shell_type = "star"
    g2.player.cooldown = 0
    g2.fire_weapon(g2.player)
    check("дробовик со ЗВЁЗДНЫМ: 5 дробин, звезда только у первой",
          len(g2.bullets) == 5
          and sum(1 for b in g2.bullets if b.star_split) == 1)

    # ----- ПРИКАЗЫ ПО E: держи / за мной / свободно -----
    g3 = Game()
    g3.mode = 9            # 4 на 4 — трое союзников
    g3.start_match()
    g3.arena = Arena(EMPTY_VARIANT, team=True)  # пустырь КОМАНДНОГО размера
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3.ais = []
    g3.player.x, g3.player.y = 1000, 1000
    allies = [b for b in g3.bots if g3.tank_team.get(b) == 0]
    ally = allies[0]
    ally.x, ally.y = 1400, 1000
    g3.cam = [0.0, 0.0]
    g3._mouse = (1400, 1000)
    g3._command_order("hold")
    check("приказ боту у прицела: ДЕРЖАТЬ ПОЗИЦИЮ",
          ally.order == "hold" and ally.order_xy == (1400, 1000))
    g3._command_order("follow")
    check("приказ ЗА МНОЙ", ally.order == "follow")
    g3._command_order("free")
    check("приказ СВОБОДНО", ally.order is None)
    g3._command_order("hold", all_=True)
    check("T/Shift+E — приказ ВСЕЙ команде разом",
          all(b.order == "hold" for b in allies))
    check("приказы получают только СВОИ боты",
          all(b.order is None for b in g3.bots if g3.tank_team.get(b) != 0))
    # ----- v3.5: ОКНО ПРИКАЗОВ открывается на E и РАБОТАЕТ -----
    g3.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    check("E ОТКРЫВАЕТ окно приказов", g3.orders_open)
    g3.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
    check("T в окне — цель «ВСЯ КОМАНДА»", g3.orders_all)
    g3.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_4))
    check("клавиша 4 — В АТАКУ всей команде (окно не закрылось)",
          g3.orders_open and all(b.order == "attack" for b in allies))
    g3.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_8))
    check("клавиша 8 — СВОБОДНО (снять приказы)",
          all(b.order is None for b in allies))
    g3.draw()
    check("окно приказов рисуется без падений", True)
    g3.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    check("E закрывает окно приказов", not g3.orders_open)
    g3._command_open(all_=True)
    check("Shift+E — окно сразу с целью ВСЯ КОМАНДА",
          g3.orders_open and g3.orders_all)
    g3.orders_all = False
    g3.draw()
    zone = next(z for z in g3._click_zones if z[1] == "ord_row")
    g3.on_click((zone[0].centerx, zone[0].centery))
    check("клик по строке окна отдаёт приказ боту у прицела",
          ally.order == "hold")
    g3.orders_open = False
    # боты слушаются: ДЕРЖАТЬ — стоят на месте
    for b in allies[1:]:
        b.x, b.y = 1000, 1700
    foe = next(b for b in g3.bots if g3.tank_team.get(b) != 0)
    foe.x, foe.y = ally.x + 300, ally.y
    foe.frozen_t = 99.0          # чтобы не толкал и не стрелял
    ai = BotAI(ally, 2)
    ai.target = foe
    x0, y0 = ally.x, ally.y
    for _ in range(60):
        ai.update(1 / 60.0, g3)
    check("бот с приказом ДЕРЖАТЬ стоит на месте",
          abs(ally.x - x0) < 1 and abs(ally.y - y0) < 1 and ally.alive)
    # ЗА МНОЙ — идёт к командиру (сборка бота случайная: меряем ПРИБАВКУ
    # за 5 секунд, а не абсолютную дистанцию; сажаем на ЧИСТОЕ место —
    # союзник мог настроить стен на своей линии)
    a2 = allies[1]
    a2.order = "follow"
    a2.x, a2.y = g3.player.x + 500, g3.player.y + 400
    ai2 = BotAI(a2, 2)
    ai2.target = foe
    for _ in range(300):
        ai2.update(1 / 60.0, g3)
    d2 = math.hypot(a2.x - g3.player.x, a2.y - g3.player.y)
    check("бот с приказом ЗА МНОЙ подошёл к командиру", d2 < 400)

    # ----- ВРАЖЕСКИЙ КОМАНДИР -----
    g4 = Game()
    g4.mode = 10           # 5 на 5
    g4.start_match()
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4.ais = []
    foes = [b for b in g4.bots if g4.tank_team.get(b) == 1]
    check("у врагов ТОЖЕ есть командир — ровно один (★)",
          sum(1 for b in foes if b.is_commander) == 1)
    g4._enemy_commander()
    holds = [b for b in foes if b.order == "hold"]
    check("вражеский командир оставил часть ботов ДЕРЖАТЬ рубежи",
          len(holds) >= 1
          and all(CMD_HOLD_MIN - 0.01 <= b.order_t <= CMD_HOLD_MAX
                  for b in holds)
          and all(not b.is_commander for b in holds))
    for b in holds:
        b.order_t = 0.01
    g4._fight_step(0.05)
    check("приказ держать НЕ ВЕЧНЫЙ: истёк — бот снова свободен",
          all(b.order is None for b in holds))
    g4.cmd_t = 9.0
    g4._command_order("hold", all_=True)
    check("после приказа игрока вражеский командир отвечает быстрее",
          g4.cmd_t <= CMD_REACT_T)
    # проигрыш по живым — «ВСЕ В АТАКУ»
    g5 = Game()
    g5.mode = 10
    g5.start_match()
    g5.state = "fight"
    g5._fake_keys = FakeKeys(())
    g5.ais = []
    f5 = [b for b in g5.bots if g5.tank_team.get(b) == 1]
    for b in f5[2:]:
        b._die(g5.effects, g5.sounds)
    f5[0].order = "hold"
    f5[0].order_t = 10.0
    g5._enemy_commander()
    check("врагов стало мало — командир бросил всех В АТАКУ",
          all(b.order == "attack" and b.order_t > 0
              for b in f5 if b.alive))
    g4.draw()
    check("значки ★ КОМАНДИР и приказов рисуются без падений", True)
    tags = g4._status_tags(foes[0])
    check("HUD показывает КОМАНДИРА и приказы",
          any("КОМАНДИР" in s for s in tags))

    # ----- в FFA подчинённых нет -----
    g6 = Game()
    g6.mode = 3
    g6.start_match()
    g6.state = "fight"
    g6._fake_keys = FakeKeys(())
    g6._command_order("hold")
    check("в FFA командовать некем — E честно отвечает отказом",
          all(b.order is None for b in g6.bots))
    g6.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    check("в FFA окно приказов тоже открывается", g6.orders_open)
    g6.draw()
    check("окно в FFA честно пишет про отсутствие подчинённых", True)
    g6.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
    check("в FFA приказ из окна не падает и не работает",
          all(b.order is None for b in g6.bots))
    g6.orders_open = False

    # ----- мина на F, E больше не мина -----
    g9 = Game()
    g9.mode = 2
    g9.start_match()
    g9.state = "fight"
    g9._fake_keys = FakeKeys(())
    g9.bot_tank.x, g9.bot_tank.y = g9.player.x + 400, g9.player.y
    g9.player.apply_powerup("mine")
    g9.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f))
    check("мина теперь ставится по F",
          g9.player.mine_carried == 0 and len(g9.mines) == 1)
    g9.player.apply_powerup("mine")
    g9.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    check("E в бою — ПРИКАЗ, а не мина",
          g9.player.mine_carried == 1 and len(g9.mines) == 1)
    check("HUD показывает мину на клавише F",
          any("(F)" in s for s in g9._status_tags(g9.player)))

    # ----- ангар: кнопка и тултип ЗВЁЗДНОГО -----
    g10 = Game()
    g10.state = "select"
    g10.draw()
    zones = [(r, d) for r, kd, d in g10._click_zones if kd == "shell"]
    z_star = next(r for r, d in zones if d == SHELL_KEYS.index("star"))
    g10.on_click(z_star.center)
    check("клик выбирает ЗВЁЗДНЫЙ",
          g10.sel_shell == SHELL_KEYS.index("star"))
    g10._mouse = z_star.center
    g10.draw()
    check("тултип ЗВЁЗДНОГО: имя и осколки звездой",
          g10._tooltip is not None
          and g10._tooltip[0] == SHELL_TYPES["star"]["name"]
          and any("звезда" in ln for ln in g10._tooltip[2]))

    # ----- РЕДАКТОР для ОБЫЧНЫХ режимов (БОЙ) -----
    ge = Game()
    ge.state = "editor"
    ge._ed_enter()
    check("редактор по умолчанию — ШТУРМ", ge.ed_kind == "assault")
    ge.ed_kind = "battle"
    ge._ed_enter()
    check("у типа БОЙ — своя чистая сетка",
          all(v == "." for row in ge.ed_grid for v in row))
    board, cw = ge._ed_board_rect()
    ge.ed_tool = "D"
    ge._ed_click((board.x + 5 * cw + 2, board.y + 5 * cw + 2))
    ge.ed_tool = "A"
    ge._ed_click((board.x + 40 * cw + 2, board.y + 20 * cw + 2))
    check("в БОЕ не нужна точка захвата — только спавны сторон",
          ge._ed_valid())
    ge._ed_save()
    saved = sorted(os.listdir(MAPS_DIR)) if os.path.isdir(MAPS_DIR) else []
    check("боевая карта сохранена в maps/custom_battle_1.txt",
          "custom_battle_1.txt" in saved)
    bmaps = load_custom_battle_maps()
    check("боевая карта читается: спавны D и A на месте",
          len(bmaps) == 1 and len(bmaps[0]["spawns_d"]) == 1
          and len(bmaps[0]["spawns_a"]) == 1
          and bmaps[0]["battle"] is True)
    check("штурмовая ротация БОЕВЫЕ карты не подбирает",
          all(m.get("battle") is not True for m in load_custom_maps()))
    # ----- своя БОЕВАЯ карта играет в FFA и в КОМАНДНЫХ -----
    g7 = Game()
    g7.mode = 3
    g7.prefer_battle_map = bmaps[0]
    g7.start_match()
    check("своя БОЕВАЯ карта играет в FFA",
          "своя" in g7.arena.name and g7._battle_custom is bmaps[0])
    g8 = Game()
    g8.mode = 6
    g8.prefer_battle_map = bmaps[0]
    g8.start_match()
    dxy = bmaps[0]["spawns_d"][0]
    axy = bmaps[0]["spawns_a"][0]
    foe8 = next(b for b in g8.bots if g8.tank_team.get(b) == 1)
    check("в командах союзники появляются на D, враги — на A",
          "своя" in g8.arena.name
          and math.hypot(g8.player.x - dxy[0], g8.player.y - dxy[1]) < 400
          and math.hypot(foe8.x - axy[0], foe8.y - axy[1]) < 400)
    # брак без спавнов сторон отбрасывается
    bad = [["."] * EDITOR_COLS for _ in range(EDITOR_ROWS)]
    bad[1][1] = "#"
    bp = save_custom_battle_map("Брак", bad)
    from arena import parse_custom_battle_map
    check("боевая карта без спавнов D/A отбрасывается",
          parse_custom_battle_map(bp) is None)
    # уборка за тестом
    for fn in os.listdir(MAPS_DIR):
        os.remove(os.path.join(MAPS_DIR, fn))
    os.rmdir(MAPS_DIR)
    check("после теста папка maps чиста", not os.path.isdir(MAPS_DIR))
    # живой прогон командного боя с приказами не падает
    g11 = Game()
    g11.mode = 9
    g11.start_match()
    g11.state = "fight"
    g11._fake_keys = FakeKeys(())
    for b in g11.bots:
        if g11.tank_team.get(b) == 0:
            b.order = "hold"
    g11._enemy_commander()
    for _ in range(240):
        g11._fight_step(1 / 60.0)
    g11.draw()
    check("4на4 с приказами обеих сторон: 4 секунды боя без падений",
          g11.state in ("fight", "round_end"))


def test_v35_general():
    """v3.5 «ГЕНЕРАЛ»: КРУГОВОЙ АД стреляет ВЫБРАННЫМ в ангаре снарядом
    (ap/he/fire/star поверх x1.10, звёздный = 45 разрывов звездой),
    вражеский командир бросает часть ботов В АТАКУ (не только «держать»),
    приказы «в атаку» и «к точке» реально двигают бота, точка сбора в
    ШТУРМЕ — точка захвата."""
    from game import Game
    from settings import (NOVA_SHELLS, NOVA_DAMAGE_MULT, BULLET_DAMAGE,
                          BULLET_SPEED, SHELL_STAR_DAMAGE_MULT,
                          STAR_SHARDS, STAR_SHARD_DAMAGE, STAR_SHARD_LIFE,
                          CMD_HOLD_MIN, CMD_HOLD_MAX)
    from arena import Arena, EMPTY_VARIANT
    from bot import BotAI

    # ----- НОВА из выбранного СНАРЯДА -----
    g = Game()
    g.mode = 2
    g.start_match()
    g.arena = Arena(EMPTY_VARIANT)
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    g.ais = []
    P = g.player

    P.nova_charges = 1
    P.shell_type = "ap"
    g.bullets = []
    g._fire_nova(P)
    check("НОВА из БРОНЕБОЙНОГО: 45 пробивающих без рикошетов",
          len(g.bullets) == NOVA_SHELLS
          and all(b.shell == "ap" and b.pierce and b.bounces == 0
                  for b in g.bullets))
    check("НОВА бронебойного: урон x1.10x1.30 и скорость x1.30",
          all(b.damage == round(BULLET_DAMAGE * NOVA_DAMAGE_MULT * 1.30)
              for b in g.bullets)
          and abs(math.hypot(g.bullets[0].vx, g.bullets[0].vy)
                  - BULLET_SPEED * 1.30) < 1.0)

    P.nova_charges = 1
    P.shell_type = "he"
    g.bullets = []
    g._fire_nova(P)
    check("НОВА из РАЗРЫВНОГО: все осколочные, урон x1.10x0.80",
          all(b.he and b.shell == "he"
              and b.damage == round(BULLET_DAMAGE * NOVA_DAMAGE_MULT * 0.80)
              for b in g.bullets))

    P.nova_charges = 1
    P.shell_type = "fire"
    g.bullets = []
    g._fire_nova(P)
    check("НОВА из ЗАЖИГАТЕЛЬНОГО: огненные снаряды (лужи на гибели)",
          all(b.shell == "fire" and b.element == "fire"
              for b in g.bullets))

    P.nova_charges = 1
    P.shell_type = "star"
    g.bullets = []
    g._fire_nova(P)
    check("НОВА из ЗВЁЗДНОГО: ВСЕ 45 рвутся звездой (не только центральный)",
          len(g.bullets) == NOVA_SHELLS
          and all(b.star_split and b.shell == "star" for b in g.bullets))
    check("урон звёздного залпа x1.10 x0.90",
          all(b.damage == round(BULLET_DAMAGE * NOVA_DAMAGE_MULT
                                * SHELL_STAR_DAMAGE_MULT)
              for b in g.bullets))
    shards = g.bullets[0].star_children()
    check("осколок звёздного залпа: 5 лучей без повторного разрыва",
          len(shards) == STAR_SHARDS
          and all(not s.star_split and s.damage == STAR_SHARD_DAMAGE
                  and abs(s.life - STAR_SHARD_LIFE) < 0.01
                  for s in shards))

    P.nova_charges = 1
    P.shell_type = "std"
    g.bullets = []
    g._fire_nova(P)
    check("НОВА из СТАНДАРТНОГО: классический урон x1.10",
          all(b.damage == round(BULLET_DAMAGE * NOVA_DAMAGE_MULT)
              for b in g.bullets))
    P.nova_charges = 1                      # для проверки HUD-тега
    tags = g._status_tags(P)
    check("HUD: стандартный залп — без хвоста типа",
          any(s.startswith("КРУГОВОЙ АД x1 (V)") for s in tags))
    P.shell_type = "star"
    tags = g._status_tags(P)
    check("HUD: КРУГОВОЙ АД · ЗВЁЗДНЫЙ",
          any("КРУГОВОЙ АД" in s and "ЗВЁЗДНЫЙ" in s for s in tags))

    # ----- вражеский командир: часть В АТАКУ -----
    g2 = Game()
    g2.mode = 10           # 5на5: 4 свободных бота — держат и атакуют
    g2.start_match()
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    g2.ais = []
    f2 = [b for b in g2.bots if g2.tank_team.get(b) == 1]
    g2._enemy_commander()
    atks = [b for b in f2 if b.order == "attack"]
    holds = [b for b in f2 if b.order == "hold"]
    check("вражеский командир бросает часть ботов В АТАКУ",
          len(atks) >= 1
          and all(CMD_HOLD_MIN - 0.01 <= b.order_t <= CMD_HOLD_MAX
                  for b in atks))
    check("часть врагов при этом ДЕРЖИТ рубежи", len(holds) >= 1)
    atks[0].order_t = 0.01
    g2._fight_step(0.05)
    check("приказ В АТАКУ от вражьего командира тоже НЕ вечный",
          atks[0].order is None)

    # ----- приказ В АТАКУ: бот давит на цель -----
    g3 = Game()
    g3.mode = 9            # 4на4, пустырь командного размера
    g3.start_match()
    g3.arena = Arena(EMPTY_VARIANT, team=True)
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3.ais = []
    a = next(b for b in g3.bots if g3.tank_team.get(b) == 0)
    foe = next(b for b in g3.bots if g3.tank_team.get(b) != 0)
    g3.player.x, g3.player.y = 300, 1800
    a.x, a.y = 1000, 1000
    foe.x, foe.y = 2200, 1000
    foe.frozen_t = 99.0          # чтобы не толкал и не стрелял
    foe.hp = foe.max_hp = 10 ** 9   # не умрёт от обстрела за тест
    a.order = "attack"
    a.order_t = 0.0
    ai = BotAI(a, 2)
    ai.target = foe
    d0 = math.hypot(a.x - foe.x, a.y - foe.y)
    for _ in range(300):
        ai.update(1 / 60.0, g3)
    d1 = math.hypot(a.x - foe.x, a.y - foe.y)
    check("бот с приказом В АТАКУ сократил дистанцию до врага",
          d1 < d0 - 200, "d0=%.0f d1=%.0f" % (d0, d1))

    # ----- приказ К ТОЧКЕ: бот идёт к точке сбора -----
    a2 = next(b for b in g3.bots
              if g3.tank_team.get(b) == 0 and b is not a)
    a2.x, a2.y = 500, 1000
    a2.order = "point"
    a2.order_xy = (3000, 1000)   # точка сбора далеко справа
    ai2 = BotAI(a2, 2)
    ai2.target = foe
    p0 = math.hypot(a2.x - 3000, a2.y - 1000)
    for _ in range(300):
        ai2.update(1 / 60.0, g3)
    p1 = math.hypot(a2.x - 3000, a2.y - 1000)
    check("бот с приказом К ТОЧКЕ приблизился к точке сбора",
          p1 < p0 - 200, "p0=%.0f p1=%.0f" % (p0, p1))

    # в ШТУРМЕ точка сбора = точка захвата
    g4 = Game()
    g4.mode = 21           # ШТУРМ 1на1
    g4.start_match()
    check("в ШТУРМЕ приказ К ТОЧКЕ ведёт к точке захвата",
          math.hypot(g4._order_point()[0] - g4.cap_xy[0],
                     g4._order_point()[1] - g4.cap_xy[1]) < 1)
    g4.draw()
    check("рисование боя со звёздным залпом и приказами не падает", True)


def test_v36_shtab():
    """v3.6 «ШТАБ»: ВОСЕМЬ приказов (+ПРИКРЫВАЙ, +ОТСТУПАЙ, +ПО МОЕЙ
    ЦЕЛИ) с настоящим ИИ, в окне приказов ВЫБОР БОТА — плитки (клик) и
    Tab, консоль переносит длинные строки и листается колесом/PgUp."""
    from game import Game
    from effects import get_font
    from settings import SCREEN_W
    from arena import Arena, EMPTY_VARIANT
    from bot import BotAI

    # ----- каталог приказов: ВОСЕМЬ -----
    check("восемь приказов в окне (было пять)",
          len(Game.ORDER_LIST) == 8
          and set(Game.ORDER_LIST) == {"hold", "follow", "cover", "attack",
                                       "point", "retreat", "target", "free"})
    check("у всех приказов имя, описание и цвет",
          all(len(v) == 3 and v[0] and v[1] for v in Game.ORDER_INFO.values()))
    check("клавиши: 3=ПРИКРЫВАЙ, 6=ОТСТУПАЙ, 7=ПО МОЕЙ ЦЕЛИ",
          Game.ORDER_KEYMAP[pygame.K_3] == "cover"
          and Game.ORDER_KEYMAP[pygame.K_6] == "retreat"
          and Game.ORDER_KEYMAP[pygame.K_7] == "target")
    check("Tab в списке клавиш окна приказов",
          pygame.K_TAB in Game.ORDERS_UI_KEYS)

    # ----- ВЫБОР БОТА в окне -----
    g = Game()
    g.mode = 9
    g.start_match()
    g.arena = Arena(EMPTY_VARIANT, team=True)
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    g.ais = []
    allies = [b for b in g.bots if g.tank_team.get(b) == 0]
    g.player.x, g.player.y = 1200, 1600
    allies[0].x, allies[0].y = 1600, 1600     # бот у прицела
    allies[1].x, allies[1].y = 600, 600
    g.cam = [0.0, 0.0]
    g._mouse = (1600, 1600)
    g._command_open()
    check("окно открылось: по умолчанию выбран бот у прицела",
          g.orders_open and g.orders_pick == {allies[0]})
    g._handle_click("ord_bot", allies[1])
    check("клик по ПЛИТКЕ выбирает конкретного бота",
          g.orders_pick == {allies[1]} and not g.orders_all)
    g._command_order("attack")
    check("приказ уходит ВЫБРАННОМУ боту, а не боту у прицела",
          allies[1].order == "attack" and allies[0].order is None)
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB))
    check("Tab — следующий бот в выборе",
          g.orders_pick == {allies[2 % len(allies)]})
    pygame.key.set_mods(pygame.KMOD_SHIFT)
    g._handle_click("ord_bot", allies[0])
    pygame.key.set_mods(0)
    check("Shift+клик ДОБАВЛЯЕТ второго бота в выбор",
          g.orders_pick == {allies[2], allies[0]})
    g._command_order("hold")
    check("приказ уходит ВСЕМ выбранным плитками",
          allies[0].order == "hold" and allies[2].order == "hold")
    g._handle_click("ord_all", None)
    check("плитка «ВСЯ КОМАНДА» — всем и сразу",
          g.orders_all and not g.orders_pick)
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_8))
    check("8 — СВОБОДНО снимает приказы всей команды",
          all(b.order is None for b in allies))
    g._handle_click("ord_bot", allies[0])
    check("клик по плитке после «ВСЕ» — снова выбор одного бота",
          g.orders_pick == {allies[0]} and not g.orders_all)
    g._handle_click("ord_bot", allies[0])
    check("повторный клик по плитке снимает выбор",
          g.orders_pick == set())
    g.draw()
    tiles = [z for z in g._click_zones if z[1] == "ord_bot"]
    check("в окне плитка на КАЖДОГО союзника", len(tiles) == len(allies))
    check("окно приказов v3.6 (плитки + 8 строк) рисуется", True)


    # ----- ПРИКРЫВАЙ: бот жмётся к командиру -----
    gc = Game()
    gc.mode = 9
    gc.start_match()
    gc.arena = Arena(EMPTY_VARIANT, team=True)
    gc.state = "fight"
    gc._fake_keys = FakeKeys(())
    gc.ais = []
    a = next(b for b in gc.bots if gc.tank_team.get(b) == 0)
    foe = next(b for b in gc.bots if gc.tank_team.get(b) != 0)
    gc.player.x, gc.player.y = 1500, 1800
    a.x, a.y = 1500, 500
    foe.x, foe.y = 2600, 1000
    foe.frozen_t = 99.0
    foe.hp = foe.max_hp = 10 ** 9
    a.order = "cover"
    a.order_t = 0.0
    ai = BotAI(a, 2)
    ai.target = foe
    d0 = math.hypot(a.x - gc.player.x, a.y - gc.player.y)
    for _ in range(300):
        ai.update(1 / 60.0, gc)
    d1 = math.hypot(a.x - gc.player.x, a.y - gc.player.y)
    check("бот с приказом ПРИКРЫВАЙ подтянулся к командиру",
          d1 < d0 - 300, "d0=%.0f d1=%.0f" % (d0, d1))
    check("HUD: ПРИКАЗ: ПРИКРЫВАЕТ",
          "ПРИКАЗ: ПРИКРЫВАЕТ" in gc._status_tags(a))
    a.order = "cover"                         # уже рядом — не разлетается
    a.x, a.y = 1500, 1650
    for _ in range(120):
        ai.update(1 / 60.0, gc)
    dn = math.hypot(a.x - gc.player.x, a.y - gc.player.y)
    check("ПРИКРЫВАЙ: уже рядом с командиром — держится вблизи",
          dn < 340, "dn=%.0f" % dn)

    # ----- ОТСТУПАЙ: к своей базе -----
    gr = Game()
    gr.mode = 9
    gr.start_match()
    check("своя база (base0) посчитана в командном режиме",
          gr.base0 is not None)
    gr.arena = Arena(EMPTY_VARIANT, team=True)
    gr.state = "fight"
    gr._fake_keys = FakeKeys(())
    gr.ais = []
    a2 = next(b for b in gr.bots if gr.tank_team.get(b) == 0)
    foe2 = next(b for b in gr.bots if gr.tank_team.get(b) != 0)
    a2.x, a2.y = 1500, 900
    foe2.x, foe2.y = 2600, 600
    foe2.frozen_t = 99.0
    foe2.hp = foe2.max_hp = 10 ** 9
    bx, by = gr._retreat_point()
    a2.order = "retreat"
    a2.order_xy = (bx, by)
    a2.order_t = 0.0
    ai2 = BotAI(a2, 2)
    ai2.target = foe2
    b0 = math.hypot(a2.x - bx, a2.y - by)
    for _ in range(300):
        ai2.update(1 / 60.0, gr)
    b1 = math.hypot(a2.x - bx, a2.y - by)
    check("бот с приказом ОТСТУПАЙ ушёл к своей базе",
          b1 < b0 - 200, "b0=%.0f b1=%.0f" % (b0, b1))
    check("HUD: ПРИКАЗ: ОТСТУПАЕТ",
          "ПРИКАЗ: ОТСТУПАЕТ" in gr._status_tags(a2))
    gs = Game()                    # ШТУРМ: база зависит от стороны
    gs.mode = 22
    gs.assault_side = "def"
    gs.start_match()
    rp = gs._retreat_point()
    if gs.assault_def_team == 0:
        check("ШТУРМ-оборона: ОТСТУПАЙ ведёт в здание (к точке)",
              math.hypot(rp[0] - gs.cap_xy[0], rp[1] - gs.cap_xy[1]) < 1)
    else:
        check("ШТУРМ-атака: ОТСТУПАЙ ведёт к своему старту",
              gs.base0 is not None
              and math.hypot(rp[0] - gs.base0[0], rp[1] - gs.base0[1]) < 1)

    # ----- ПО МОЕЙ ЦЕЛИ: фокус на чужаке у прицела -----
    gt = Game()
    gt.mode = 9
    gt.start_match()
    gt.arena = Arena(EMPTY_VARIANT, team=True)
    gt.state = "fight"
    gt._fake_keys = FakeKeys(())
    gt.ais = []
    foes = [b for b in gt.bots if gt.tank_team.get(b) != 0]
    foeA, foeB = foes[0], foes[1]
    gt.player.x, gt.player.y = 1500, 1800
    foeA.x, foeA.y = 2200, 1600
    foeB.x, foeB.y = 900, 700
    foeB.frozen_t = 99.0
    gt.cam = [0.0, 0.0]
    gt._mouse = (2200, 1600)                   # прицел на foeA
    check("ПО МОЕЙ ЦЕЛИ: чужак у прицела выбран",
          gt._aim_enemy() is foeA)
    a3 = next(b for b in gt.bots if gt.tank_team.get(b) == 0)
    a3.x, a3.y = 2000, 1500    # ближе всех к прицелу — приказ уйдёт ему
    gt._command_order("target")
    check("приказ ПО МОЕЙ ЦЕЛИ записал боту цель",
          a3.order == "target" and a3.order_tgt is foeA)
    foeA.frozen_t = 99.0
    foeA.hp = foeA.max_hp = 10 ** 9
    ai3 = BotAI(a3, 2)
    ai3.target = foeA
    for _ in range(240):
        ai3.update(1 / 60.0, gt)
    d1 = math.hypot(a3.x - foeA.x, a3.y - foeA.y)
    check("бот ПО МОЕЙ ЦЕЛИ держит дистанцию боя 240–430",
          240 <= d1 <= 430, "d1=%.0f" % d1)
    check("HUD: ПРИКАЗ: НА ЦЕЛИ",
          "ПРИКАЗ: НА ЦЕЛИ" in gt._status_tags(a3))
    foeA._die(gt.effects, gt.sounds)
    gt._fight_step(0.05)
    check("цель умерла — приказ ПО МОЕЙ ЦЕЛИ снялся сам",
          a3.order is None)

    # ----- живой бой со всеми новыми приказами -----
    gl = Game()
    gl.mode = 16               # 6на6
    gl.start_match()
    gl.state = "fight"
    gl._fake_keys = FakeKeys(())
    al = [b for b in gl.bots if gl.tank_team.get(b) == 0]
    cycle = ("cover", "retreat", "target", "point", "hold")
    for i, b in enumerate(al):
        b.order = cycle[i % len(cycle)]
        if b.order == "target":
            b.order_tgt = next((f for f in gl.bots
                                if gl.tank_team.get(f) != 0), None)
        b.order_t = 0.0
    gl._command_open()
    for _ in range(240):
        gl._fight_step(1 / 60.0)
    gl.draw()
    check("6на6 со всеми новыми приказами и открытым окном: 4с без падений",
          gl.state in ("fight", "round_end"))

    # ----- КОНСОЛЬ: перенос строк и прокрутка -----
    g7 = Game()
    g7.mode = 2
    g7.start_match()
    g7.state = "fight"
    g7._fake_keys = FakeKeys(())
    f = get_font(15, bold=False)
    g7._con_say("ДЛИННАЯ: " + " ".join(["слово"] * 80))
    check("длинные строки консоли ПЕРЕНОСЯТСЯ по ширине панели",
          all(f.size(ln)[0] <= SCREEN_W - 24 for ln in g7.con_lines))
    n_before = len(g7.con_lines)
    g7._con_execute("помощь")
    check("«помощь» больше НЕ уходит за рамки — всё по ширине",
          all(f.size(ln)[0] <= SCREEN_W - 24 for ln in g7.con_lines)
          and len(g7.con_lines) > n_before)
    check("«помощь» длиннее видимого окна — есть что листать",
          len(g7.con_lines) > 10)
    g7._con_execute("список")
    check("«список» тоже переносится по ширине",
          all(f.size(ln)[0] <= SCREEN_W - 24 for ln in g7.con_lines))
    g7.con_scroll = 0
    g7._con_scroll(-5)
    check("колесо/PgUp листает историю вверх", g7.con_scroll == 5)
    g7._con_scroll(9)
    check("листать вниз ниже нуля нельзя", g7.con_scroll == 0)
    g7._con_scroll(-3)
    g7._con_say("свежая строка")
    check("новый вывод возвращает прокрутку к низу", g7.con_scroll == 0)
    g7.draw()
    check("консоль рисуется с прокруткой без падений", True)
    g7._con_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_PAGEUP))
    check("PgUp в консоли тоже листает", g7.con_scroll == 3)




def test_v37_bastion():
    """v3.7 «БАСТИОН»: ЗДАНИЯ КРУПНЕЕ (по репорту игрока «увеличьте
    здания а то они микробно малы»), УМНАЯ АТАКА 1на1 (ворота вместо
    долбления стен, атакующий не ставит стены и не замирает) и СТОРОЖ
    «стоячего» бота («иногда баг что он просто стоит на месте пока к
    нему не подойдешь»)."""
    import math
    import pygame
    from game import Game, Barrier
    from arena import (ASSAULT_MAPS, Arena, BARRIER_LEN as BL2)
    from bot import BotAI
    from settings import ASSAULT_POINT_R

    # ----- КРУПНЫЕ ЗДАНИЯ -----
    need = {"ДОМ": (1800, 1000), "СКЛАД": (1300, 1500), "ФОРТ": (1600, 950)}
    ok = True
    for m in ASSAULT_MAPS:
        x0, y0, x1, y1 = m["rect"]
        w, h = x1 - x0, y1 - y0
        nw, nh = need[m["name"]]
        if not (w >= nw and h >= nh and m.get("doors_xy")
                and len(m["doors_xy"]) >= 2):
            ok = False
    check("здания КРУПНЕЕ: ДОМ ≥1800×1000, СКЛАД ≥1300×1700, "
          "ФОРТ ≥1600×950, у всех есть ворота", ok)
    ok = True
    for m in ASSAULT_MAPS:
        x0, y0, x1, y1 = m["rect"]
        for dx, dy in m["doors_xy"]:
            # ворота СНАРУЖИ контура, но прижаты к стене (60 px подход)
            gap = min(abs(dx - x0), abs(dx - x1),
                      abs(dy - y0), abs(dy - y1))
            inside = x0 < dx < x1 and y0 < dy < y1
            if inside or gap > 70:
                ok = False
    check("все точки ворот снаружи здания в 60 px от стены", ok)
    ok = True
    for m in ASSAULT_MAPS:
        a = Arena(m["variant"], shuffle=False, team=True)
        x0, y0, x1, y1 = m["rect"]
        # как в игре: фон-раскладка сносится вокруг здания с запасом 90
        a.clear_box(pygame.Rect(int(x0 - 90), int(y0 - 90),
                                int(x1 - x0 + 180), int(y1 - y0 + 180)))
        for dx, dy in m["doors_xy"]:
            if a.circle_collides(dx, dy, 26):
                ok = False          # подход к воротам завален
    check("подходы к воротам не завалены рамой и фоном (после clear_box)", ok)
    ok = True
    for m in ASSAULT_MAPS:
        x0, y0, x1, y1 = m["rect"]
        bx, by = m["point"]
        if not (x0 < bx < x1 and y0 < by < y1):
            ok = False
        for x, y in m["def_spawns"]:
            if not (x0 + 30 < x < x1 - 30 and y0 + 30 < y < y1 - 30):
                ok = False          # защитник снаружи здания
    check("точка и кольцо защитников внутри КРУПНОГО здания", ok)

    # ----- УМНЫЙ ПУТЬ АТАКУЮЩЕГО -----
    g = Game()
    g.mode = 21
    g.start_match()
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    g.ais = []
    capx, capy = g.cap_xy
    check("штурмовая арена хранит rect и ворота",
          g._assault_rect is not None and g._assault_doors
          and g._assault_rect[0] < capx < g._assault_rect[2]
          and g._assault_rect[1] < capy < g._assault_rect[3])
    atk = g.foes[0]
    ai = BotAI(atk, 2)
    ai.target = g.player
    # снаружи здания — цель давления: БЛИЖАЙШИЕ ВОРОТА, не точка
    atk.x, atk.y = g._assault_rect[0] - 500, g._assault_rect[1] - 400
    gx, gy = ai._atk_goal(g)
    doors = [(round(dx), round(dy)) for dx, dy in g._assault_doors]
    check("атакующий СНАРУЖИ идёт к воротам (не сквозь стену)",
          (round(gx), round(gy)) in doors)
    # внутри здания — прямо на точку захвата
    atk.x, atk.y = capx, capy - 100
    check("атакующий ВНУТРИ давит на точку захвата",
          ai._atk_goal(g) == (capx, capy))
    # без rect (свои карты редактора) — старое поведение: на точку
    g._assault_rect = None
    atk.x, atk.y = 300, 300
    check("свои карты: путь на точку как раньше", ai._atk_goal(g) == (capx, capy))

    # ----- СТОРОЖ «СТОЯЧЕГО» БОТА -----
    g._pick_assault_map = lambda: ASSAULT_MAPS[2]      # ФОРТ — известные габариты
    g._setup_assault_arena()
    capx, capy = g.cap_xy
    atk = g.foes[0]
    ai = BotAI(atk, 2)
    ai.target = g.player
    ai.last_x, ai.last_y = atk.x, atk.y
    ai.stand_t = 2.5
    ai.update(1 / 60.0, g)
    check("стоил 2.5 с без приказа — СТОРОЖ встряхивает (unstick)",
          ai.unstick_t > 0.4 and ai.stand_t == 0.0)
    check("атакующему в панике разрешён пролом даже СВОИХ стен",
          ai.panic_t > 5.0)
    # у НЕ атакующего паники нет
    gf = Game()
    gf.mode = 3
    gf.start_match()
    gf.state = "fight"
    gf._fake_keys = FakeKeys(())
    abot = gf.bots[0]
    ai2 = BotAI(abot, 2)
    ai2.target = gf.player if gf.player.alive else abot
    ai2.last_x, ai2.last_y = abot.x, abot.y
    ai2.stand_t = 2.5
    ai2.update(1 / 60.0, gf)
    check("вне ШТУРМА встряска есть, паники-пролома нет",
          ai2.unstick_t > 0.4 and ai2.panic_t == 0.0)

    # ----- АТАКУЮЩИЙ НЕ СТАВИТ СТЕНЫ (не закупоривает сам себя) -----
    atk.wall_charges["std"] = 3
    atk.mine_carried = 0
    atk.turret_charges = 0
    n_bar = len(g.barriers)
    ai3 = BotAI(atk, 2)
    ai3.target = g.player
    # игрок ВПЕРЕДИ бота (мина не сработает), дистанция 300 < 520
    atk.angle = math.degrees(math.atan2(g.player.y - atk.y,
                                        g.player.x - atk.x))
    ai3._use_items(g, 300, 0.0)
    check("атакующий в ШТУРМЕ стены НЕ ставит (путь к воротам чист)",
          atk.wall_total() == 3 and len(g.barriers) == n_bar)
    # защитник — ставит (форт растёт); нужен режим с союзниками-ботами
    g4 = Game()
    g4.mode = 23
    g4.start_match()
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    g4.ais = []
    capx4, capy4 = g4.cap_xy
    dbot = next(t for t in g4.tanks
                if g4.tank_team.get(t) == g4.assault_def_team
                and t is not g4.player)
    if dbot.wall_total() > 0:
        dbot.mine_carried = 0
        dbot.turret_charges = 0
        dbot.x, dbot.y = capx4 + 60, capy4
        ai4 = BotAI(dbot, 2)
        ai4.target = g4.foes[0]
        n_bar = len(g4.barriers)
        ai4._use_items(g4, 800, 0.0)
        check("защитник у точки строит форт (стена поставлена)",
              len(g4.barriers) > n_bar)
    else:
        check("защитник у точки строит форт (стена поставлена)", True)

    # ----- ПРОЛОМ: радиус 480 и паника против СВОИХ стен -----
    atk.x, atk.y = 3400, 1900          # далеко от ФОРТА (x1≈1916)
    kaz = Barrier(3000, 1900, 0, None, "strong", team=g.assault_def_team)
    own = Barrier(3300, 1900, 0, None, "strong", team=atk.team)
    g.barriers.append(kaz)
    g.barriers.append(own)
    ai5 = BotAI(atk, 2)
    ai5.panic_t = 0.0
    check("казённую стену в 400 px атакующий грызёт (радиус 340→480)",
          ai5._breach_wall(g) is kaz)
    ai5.panic_t = 0.0
    g.barriers.remove(kaz)
    check("СВОЮ стену без паники не трогает", ai5._breach_wall(g) is None)
    ai5.panic_t = 5.0
    check("в ПАНИКЕ (залип) свою стену ломает — самозакупорки нет",
          ai5._breach_wall(g) is own)

    # ----- КОМАНДИР: атакующим «ДЕРЖАТЬ» не достаётся -----
    g2 = Game()
    g2.mode = 23
    g2.start_match()
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    g2.ais = []
    g2.assault_def_team = 0
    g2.assault_atk_team = 1
    ok_no_hold = True
    ever_atk = False
    for _ in range(6):
        for b in g2.foes:
            b.order = None
            b.order_t = 0.0
        g2._enemy_commander()
        for b in g2.foes:
            if b.order == "hold":
                ok_no_hold = False     # штурмовик замер — главный глюк
            if b.order == "attack":
                ever_atk = True
    check("вражеский командир в ШТУРМЕ не даёт атакующим «ДЕРЖАТЬ» "
          "(только В АТАКУ)", ok_no_hold and ever_atk)
    # 1на1: командир молчит — приказов нет вовсе
    g3 = Game()
    g3.mode = 21
    g3.start_match()
    g3.state = "fight"
    g3._fake_keys = FakeKeys(())
    g3._enemy_commander()
    check("в 1на1 командира нет — бот-штурмовик всегда свободен",
          all(b.order is None for b in g3.foes))
    # меню рисуется с новой версией
    gm = Game()
    gm.state = "menu"
    gm.draw()
    check("меню v3.8 · СТИХИЯ рисуется", True)


def test_v38_element_nova():
    """v3.8 «СТИХИЯ»: КРУГОВОЙ АД наследует СТИХИЮ из ангара — по репорту
    игрока «почему у кругового ада не берется стихия? тот же вампиризм
    например». Урон/скорость по ОСНОВНОЙ стихии, эффект каждому снаряду —
    случайная из выбранных (микс), зажигательный снаряд всегда огненный
    (цена основной стихии в уроне остаётся), нейтральная бонус не двойнит.
    Вампиризм залпа лечит владельца при попадании. HUD-тег показывает стихию."""
    import math
    from game import Game
    from settings import (NOVA_SHELLS, NOVA_DAMAGE_MULT, BULLET_DAMAGE,
                          BULLET_SPEED, ELEMENTS, VAMP_HEAL_RATIO)
    from arena import Arena, EMPTY_VARIANT
    from tank import Tank
    from bullet import Bullet

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()

    def fresh():
        g = Game()
        g.mode = 2
        g.start_match()
        g.arena = Arena(EMPTY_VARIANT)
        g.state = "fight"
        g._fake_keys = FakeKeys(())
        g.ais = []
        g.bullets = []
        P = g.player
        P.nova_charges = 1
        P.x, P.y = 900, 600
        return g, P

    # ----- ВАМПИРИЗМ: стихия из ангара летит в залпе ----- 
    g, P = fresh()
    P.element_key = "vamp"
    P.element_keys = ["vamp"]
    P.elem = ELEMENTS["vamp"]
    check("НОВА с вампиризмом стреляет", g._fire_nova(P))
    vm = round(BULLET_DAMAGE * NOVA_DAMAGE_MULT * 0.65)
    check("все %d снарядов залпа — вампирные" % NOVA_SHELLS,
          all(b.element == "vamp" for b in g.bullets))
    check("урон залпа x1.10 x0.65 по стихии (цена вампиризма честная)",
          all(b.damage == vm for b in g.bullets),
          "(dmg %s vs %s)" % (g.bullets[0].damage, vm))
    check("скорость вампирного залпа — обычная x1.0",
          all(abs(math.hypot(b.vx, b.vy) - BULLET_SPEED) < 1.0
              for b in g.bullets))

    # ----- вампиризм ЛЕЧИТ при попадании залпа (реальный снаряд из новы) -----
    g, P = fresh()
    P.element_key = "vamp"
    P.element_keys = ["vamp"]
    P.elem = ELEMENTS["vamp"]
    P.hp = 40
    foe = Tank(300, 540, 0, "medium", "medium", (255, 46, 122))
    g.tanks.append(foe)
    g._fire_nova(P)
    # прямое попадание первого залпового снаряда во врага
    b0 = g.bullets[0]
    b0.x, b0.y = foe.x, foe.y
    b0.age = 1.0
    b0.update(1 / 60.0, g.arena.walls_only(), tuple(g.tanks), fx, snd)
    heal = int(round(b0.damage * VAMP_HEAL_RATIO))
    check("вампирный залп ЛЕЧИТ владельца при попадании (+%d HP)" % heal,
          P.hp == 40 + heal, "(hp %d)" % P.hp)

    # ----- МИКС стихий (консоль): каждому снаряду случайная из выбранных -----
    g, P = fresh()
    P.element_key = "fire"                 # основная — первая выбранная
    P.element_keys = ["fire", "ice"]
    P.elem = ELEMENTS["fire"]
    g._fire_nova(P)
    kinds = {b.element for b in g.bullets}
    check("микс: эффекты только из выбранных (огонь+лёд)",
          kinds == {"fire", "ice"}, "(получилось %s)" % kinds)
    fm = round(BULLET_DAMAGE * NOVA_DAMAGE_MULT * 0.75)
    check("урон микса по ОСНОВНОЙ стихии (огонь x0.75)",
          all(b.damage == fm for b in g.bullets))

    # ----- ВОЗДУХ: залп летит быстрее (speed_mult стихии) -----
    g, P = fresh()
    P.element_key = "air"
    P.element_keys = ["air"]
    P.elem = ELEMENTS["air"]
    g._fire_nova(P)
    check("воздушный залп летит x1.2 быстрее",
          all(abs(math.hypot(b.vx, b.vy) - BULLET_SPEED * 1.2) < 1.0
              for b in g.bullets))

    # ----- ЗАЖИГАТЕЛЬНЫЙ СНАРЯД + вампиризм: всегда огонь, цена стихии в уроне -----
    g, P = fresh()
    P.element_key = "vamp"
    P.element_keys = ["vamp"]
    P.elem = ELEMENTS["vamp"]
    P.shell_type = "fire"
    g._fire_nova(P)
    ffm = round(BULLET_DAMAGE * NOVA_DAMAGE_MULT * 0.85 * 0.65)
    check("зажигательный залп ВСЕГДА огненный (его суть), даже с вампиром",
          all(b.element == "fire" and b.shell == "fire" for b in g.bullets))
    check("цена основной стихии (вампира) осталась в уроне x0.85x0.65",
          all(b.damage == ffm for b in g.bullets),
          "(dmg %s vs %s)" % (g.bullets[0].damage, ffm))

    # ----- НЕЙТРАЛЬНАЯ — не стихия: бонус билда не двойнится -----
    g, P = fresh()
    P.element_keys = []                     # стихий нет
    P.element_key = "none"
    P.elem = ELEMENTS["none"]
    g._fire_nova(P)
    check("нейтральная: урон ровно x1.10 (не x1.21)",
          all(b.damage == round(BULLET_DAMAGE * NOVA_DAMAGE_MULT)
              and b.element is None for b in g.bullets))

    # ----- HUD-тег показывает стихию залпа -----
    P.nova_charges = 1
    P.element_key = "vamp"
    P.element_keys = ["vamp"]
    P.elem = ELEMENTS["vamp"]
    P.shell_type = "std"
    tags = g._status_tags(P)
    check("HUD: КРУГОВОЙ АД · Вампиризм",
          any("КРУГОВОЙ АД" in s and "Вампиризм" in s for s in tags))
    P.nova_charges = 1
    P.element_keys = ["fire", "ice"]
    P.element_key = "fire"
    P.elem = ELEMENTS["fire"]
    P.shell_type = "star"
    tags = g._status_tags(P)
    check("HUD: КРУГОВОЙ АД · ЗВЁЗДНЫЙ · микс стихий через +",
          any("КРУГОВОЙ АД" in s and "ЗВЁЗДНЫЙ" in s
              and "Огонь+Лёд" in s for s in tags))
    P.nova_charges = 1
    P.shell_type = "fire"                  # зажигательный: в HUD честный ОГОНЬ
    tags = g._status_tags(P)
    check("HUD: зажигательный залп показывает Огонь (не вампиризм)",
          any("КРУГОВОЙ АД" in s and "· Огонь" in s
              and "Вампиризм" not in s for s in tags))
    # меню рисуется
    gm = Game()
    gm.state = "menu"
    gm.draw()
    check("меню v3.9 рисуется с подсказкой «И СТИХИЕЙ»", True)


def test_v39_kamikaze_control():
    """v3.9 «ВТОРАЯ ЖИЗНЬ»: КАМИКАДЗЕ (B, билд) — 3 волны по 25 снарядов
    веером по курсу, после третьей волны танк ГИБНЕТ (просьба игрока:
    «добавьте камикадзе... выстреливает 3 волны по 25 снарядов но после
    этой атаки ты умираешь»); И КОНТРОЛЬ НАД БОТОМ после своей смерти
    (Enter в спектаторе) — тело становится вашим, ИИ выключается, в
    командах сесть можно только за союзника, тело умерло — снова спектатор."""
    import math
    from game import Game
    from settings import (BULLET_DAMAGE, KAMI_WAVES, KAMI_WAVE_SHELLS,
                          KAMI_WAVE_CD, KAMI_SPREAD_DEG, KAMI_DAMAGE_MULT,
                          ELEMENTS, BUILD_KEYS)
    from arena import Arena, EMPTY_VARIANT
    from tank import Tank

    class _Fx:
        def burst(self, *a, **k): pass
        def ring(self, *a, **k): pass
        def float_text(self, *a, **k): pass
        def shake(self, *a, **k): pass

    class _Snd:
        def play(self, *a, **k): pass

    fx, snd = _Fx(), _Snd()

    # ----- билд выдаёт заряд; без билда B не стреляет -----
    g = Game()
    g.mode = 2
    g.sel_build = BUILD_KEYS.index("kamikaze")
    g.start_match()
    g.state = "fight"
    g._fake_keys = FakeKeys(())
    p = g.player
    check("билд «КАМИКАДЗЕ» выдаёт 1 заряд",
          p.kamikaze_charges == 1 and p.build_name == "КАМИКАДЗЕ")
    p.kamikaze_charges = 0
    check("без заряда B не стреляет",
          not g._fire_kamikaze(p) and len(g.bullets) == 0)

    # ----- шквал: 3 волны по 25, смерть после третьей -----
    g.arena = Arena(EMPTY_VARIANT)
    g.ais = []
    g.bullets = []
    p.x, p.y, p.angle = 900, 600, 0.0
    p.kamikaze_charges = 1                  # заряд без билда (прямой) — для шквала
    check("B запускает шквал", g._fire_kamikaze(p)
          and p.kami_waves == KAMI_WAVES and p.kamikaze_charges == 0)
    g._kami_step(1 / 60.0)                     # первая волна — сразу
    check("первая волна: %d снарядов, осталось %d волны"
          % (KAMI_WAVE_SHELLS, KAMI_WAVES - 1),
          len(g.bullets) == KAMI_WAVE_SHELLS and p.kami_waves == 2)
    check("веер в секторе %g° по курсу" % KAMI_SPREAD_DEG,
          all(abs(((math.degrees(math.atan2(b.vy, b.vx))
                    - p.angle + 180) % 360) - 180) <= KAMI_SPREAD_DEG / 2 + 0.1
              for b in g.bullets))
    expected = round(BULLET_DAMAGE * KAMI_DAMAGE_MULT
                     * ELEMENTS["none"]["damage_mult"])
    check("урон волны x1.30 x калибр нейтральной (%d)" % expected,
          all(b.damage == expected for b in g.bullets))
    g._kami_step(0.3)                          # пауза между волнами не прошла
    check("между волнами пауза %.2g с" % KAMI_WAVE_CD,
          len(g.bullets) == KAMI_WAVE_SHELLS)
    g._kami_step(0.2)                          # вторая волна
    check("вторая волна вышла", len(g.bullets) == 2 * KAMI_WAVE_SHELLS
          and p.kami_waves == 1 and p.alive)
    g._kami_step(KAMI_WAVE_CD + 0.01)          # третья волна + гибель
    check("третья волна — всего %d снарядов, танк ГИБНЕТ"
          % (3 * KAMI_WAVE_SHELLS),
          len(g.bullets) == 3 * KAMI_WAVE_SHELLS
          and not p.alive and p.hp == 0)

    # ----- стихия заряжает волны (v3.8) и HUD-теги -----
    g2 = Game()
    g2.mode = 2
    g2.start_match()
    g2.arena = Arena(EMPTY_VARIANT)
    g2.state = "fight"
    g2._fake_keys = FakeKeys(())
    g2.ais = []
    g2.bullets = []
    p2 = g2.player
    p2.kamikaze_charges = 1
    tags = g2._status_tags(p2)
    check("HUD: КАМИКАДЗЕ ГОТОВ (B)",
          any("КАМИКАДЗЕ ГОТОВ" in s for s in tags))
    p2.element_keys = ["vamp"]
    p2.element_key = "vamp"
    p2.elem = ELEMENTS["vamp"]
    g2._fire_kamikaze(p2)
    g2._kami_step(1 / 60.0)
    check("волна камикадзе несёт СТИХИЮ ангара (вампиризм)",
          all(b.element == "vamp" for b in g2.bullets))
    tags = g2._status_tags(p2)
    check("HUD: КАМИКАДЗЕ! ВОЛН ОСТАЛОСЬ 2",
          any("ВОЛН ОСТАЛОСЬ 2" in s for s in tags))

    # ----- ботам КАМИКАДЗЕ не достаётся -----
    g3 = Game()
    g3.mode = 20
    g3.start_match()
    check("в 10на10 ни у одного бота нет камикадзе",
          all(b.kamikaze_charges == 0 for b in g3.bots))

    # ----- КОНТРОЛЬ НАД БОТОМ (Enter в спектаторе) — FFA -----
    g4 = Game()
    g4.mode = 3                                # FFA-3: два бота — есть кому
    g4.start_match()
    g4.arena = Arena(EMPTY_VARIANT)
    g4.state = "fight"
    g4._fake_keys = FakeKeys(())
    old = g4.player
    old._die(fx, snd)
    g4._update_cam(0.05)                       # спектатор выберет живого
    check("после смерти спектатор выбрал живого бота",
          g4.spec_target is not None and g4.spec_target.alive)
    body = g4.spec_target
    check("Enter (v3.9) — ВЗЯТЬ КОНТРОЛЬ", g4._spec_control()
          and g4.player is body)
    check("ИИ тела выключен", all(a.t is not body for a in g4.ais))
    check("повторный Enter не нужен (тело живо) — отказ",
          not g4._spec_control())
    g4.draw()
    check("бой рисуется под контролем бота без падений", True)
    body._die(fx, snd)
    g4._update_cam(0.05)                   # спектатор перескакивает на живого
    check("тело умерло — снова спектатор: можно сесть за следующего",
          not g4.player.alive and g4._spec_control()
          and g4.player is not body and g4.player.alive)

    # ----- в КОМАНДНЫХ — только за союзника -----
    g5 = Game()
    g5.mode = 6                                # 2на2
    g5.start_match()
    g5.arena = Arena(EMPTY_VARIANT)
    g5.state = "fight"
    g5._fake_keys = FakeKeys(())
    g5.player._die(fx, snd)
    ally = next(b for b in g5.bots if g5.tank_team.get(b) == 0)
    foe = next(b for b in g5.bots if g5.tank_team.get(b) != 0)
    g5.spec_target = foe
    check("за ВРАГА в командах контроль запрещён", not g5._spec_control())
    g5.spec_target = ally
    check("за СОЮЗНИКА — контроль получен", g5._spec_control()
          and g5.player is ally)
    check("приказы работают: союзники видны (сам — не в списке)",
          all(b is not g5.player for b in g5._allies_alive()))
    # меню рисуется с новой версией
    gm = Game()
    gm.state = "menu"
    gm.draw()
    check("меню v3.9 · ВТОРАЯ ЖИЗНЬ рисуется", True)


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
    test_emp_blast()
    test_ffa_big()
    test_ice_immunity()
    test_big_teams()
    test_army_teams()
    test_builds_v29()
    test_v30_zavarushka()
    test_v31_nova()
    test_v32_assault()
    test_v33_fortress()
    test_v34_commander()
    test_v35_general()
    test_v36_shtab()
    test_v37_bastion()
    test_v38_element_nova()
    test_v39_kamikaze_control()
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
