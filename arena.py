# -*- coding: utf-8 -*-
"""Арена: 21 вариант расстановки препятствий, стены, коллизии, лучи.
v2.1: РАНДОМИЗАЦИЯ — перед боем карта может зеркально отразиться и получить
несколько случайных баррикад, а сама арена переразыгрывается КАЖДЫЙ РАУНД.
v2.2: КАРТЫ ПОБОЛЬШЕ — мир больше окна 1280x720: камера следует за игроком
(в game.py).
v2.5: РАЗМЕРЫ ПОД РЕЖИМ: обычные карты 2752x1548 (ещё x1.5 площади к v2.4),
командные 3888x2187 (ещё x3 площади к v2.4) — каждая арена несёт свой
размер, масштаб раскладки и толщину стен.
v2.8: АРМЕЙСКИЕ карты 5120x2880 — под командные 6на6…10на10 (12-20 танков).
v3.3: КРЕПОСТЬ — ШТУРМОВЫЕ КАРТЫ со ЗДАНИЕМ из казённых прочных стен
(защитники внутри, точка захвата в здании) и СВОИ КАРТЫ игрока из
редактора: папка maps/custom_*.txt рядом с игрой."""
import math
import os
import random
import pygame
from settings import (SCREEN_W, SCREEN_H, COL_WALL, COL_GRID, COL_BG,
                      PROP_MAX, ARENA_W, ARENA_H,
                      TEAM_ARENA_W, TEAM_ARENA_H,
                      ARMY_ARENA_W, ARMY_ARENA_H,
                      BARRIER_LEN, ASSAULT_BUILD_OUT_TIER,
                      ASSAULT_BUILD_IN_TIER, ASSAULT_DEF_SPAWNS,
                      ASSAULT_ATK_SPAWNS, MAPS_DIR,
                      EDITOR_COLS, EDITOR_ROWS, EDITOR_CELL)

WALL_T = 60  # толщина внешних стен в исходной раскладке (масштабируется)

# Масштаб/стены ДЛЯ ОБЫЧНОЙ карты (по умолчанию) — оставлены для совместимости;
# каждая арена с v2.5 считает свои значения в __init__ (self.wall_t).
_S = ARENA_W / float(SCREEN_W)
WALL_TS = int(WALL_T * _S)

# классические точки появления танков в ИСХОДНЫХ координатах
_SPAWN_SRC = ((240, 360), (1040, 360))


def _scaled_layout(rects, s):
    """Раскладка из исходных координат 1280x720 — в мир масштаба s."""
    return [(int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s)))
            for (x, y, w, h) in rects]

# Восемь симметричных раскладок арены (все зеркалятся по центру)
LAYOUTS = [
    # «Классика»: центральная колонна и блоки по сторонам
    [(600, 300, 80, 120),
     (330, 160, 130, 36), (820, 160, 130, 36),
     (330, 524, 130, 36), (820, 524, 130, 36),
     (140, 330, 36, 60), (1104, 330, 36, 60)],
    # «Крестовина»: длинные козырьки и точки-укрытия
    [(600, 320, 80, 80),
     (400, 180, 36, 36), (844, 180, 36, 36),
     (400, 504, 36, 36), (844, 504, 36, 36),
     (480, 140, 320, 36), (480, 544, 320, 36)],
    # «Колонны»: зал с колоннами, узкие проходы для снарядов
    [(330, 210, 40, 130), (330, 380, 40, 130),
     (910, 210, 40, 130), (910, 380, 40, 130),
     (610, 330, 60, 60)],
    # «Уголки»: угловые L-блоки и пятачок в центре
    [(170, 130, 140, 36), (970, 554, 140, 36),
     (170, 130, 36, 140), (1074, 450, 36, 140),
     (970, 130, 140, 36), (170, 554, 140, 36),
     (1074, 130, 36, 140), (170, 450, 36, 140),
     (600, 330, 80, 60)],
    # «Полоса»: три горизонтальные стены со сдвигом — заходишь с фланга
    [(240, 190, 170, 36), (870, 494, 170, 36),
     (640, 190, 170, 36), (470, 494, 170, 36),
     (510, 342, 260, 36)],
    # «Соты»: поле колонн-точек, вечная погоня по диагоналям
    [(300, 180, 56, 56), (924, 484, 56, 56),
     (560, 180, 56, 56), (664, 484, 56, 56),
     (300, 484, 56, 56), (924, 180, 56, 56),
     (430, 332, 56, 56), (794, 332, 56, 56),
     (612, 332, 56, 56)],
    # «Мосты»: центральная колонна с проходом, ступени по углам
    [(590, 120, 100, 180), (590, 420, 100, 180),
     (300, 120, 140, 36), (840, 564, 140, 36),
     (300, 564, 140, 36), (840, 120, 140, 36)],
    # «Бункер»: большая коробка в центре и точки по диагоналям
    [(560, 280, 160, 160),
     (350, 180, 36, 36), (894, 504, 36, 36),
     (350, 504, 36, 36), (894, 180, 36, 36)],
    # «Веер»: лучи блоков от центра — кружим по дугам
    [(600, 120, 80, 80), (600, 520, 80, 80),
     (280, 140, 90, 90), (910, 490, 90, 90),
     (280, 490, 90, 90), (910, 140, 90, 90),
     (164, 330, 36, 100), (1080, 330, 36, 100),
     (595, 320, 90, 80)],
    # «Шахты»: сетка столбов-колонн, вечный поиск просвета
    [(160, 160, 50, 50), (1070, 510, 50, 50),
     (160, 510, 50, 50), (1070, 160, 50, 50),
     (160, 340, 50, 50), (1070, 330, 50, 50),
     (420, 160, 60, 36), (800, 524, 60, 36),
     (420, 524, 60, 36), (800, 160, 60, 36),
     (600, 330, 80, 60)],
    # ----- шесть новых арен v2.1 -----
    # «Вилка»: стена по центру с проёмом, укрытия по сторонам
    [(620, 60, 40, 170), (620, 490, 40, 170),
     (380, 180, 90, 36), (810, 180, 90, 36),
     (380, 504, 90, 36), (810, 504, 90, 36),
     (140, 330, 36, 60), (1104, 330, 36, 60)],
    # «Кольцо»: стены по кругу с диагональными проходами и столб в центре
    [(600, 150, 80, 36), (600, 534, 80, 36),
     (430, 340, 36, 80), (814, 340, 36, 80),
     (470, 210, 36, 36), (774, 210, 36, 36),
     (470, 474, 36, 36), (774, 474, 36, 36),
     (612, 340, 56, 40)],
    # «Зигзаг»: три горизонтальные стены со сдвигом и разрывом по центру
    [(140, 170, 280, 36), (860, 170, 280, 36),
     (420, 342, 130, 36), (730, 342, 130, 36),
     (140, 514, 280, 36), (860, 514, 280, 36)],
    # «Казармы»: две стены-перегородки с дверями по центру
    [(300, 60, 36, 220), (300, 400, 36, 260),
     (944, 60, 36, 220), (944, 400, 36, 260),
     (560, 100, 160, 36), (560, 584, 160, 36),
     (612, 330, 56, 60)],
    # «Ступени»: две диагонали блоков — нырки по лестнице
    [(180, 130, 100, 36), (300, 250, 100, 36),
     (420, 370, 100, 36), (540, 490, 100, 36),
     (1000, 130, 100, 36), (880, 250, 100, 36),
     (760, 370, 100, 36), (640, 490, 100, 36),
     (612, 330, 56, 56)],
    # «Бухта»: боковые карманы и козырьки сверху/снизу
    [(140, 240, 36, 240), (1104, 240, 36, 240),
     (300, 100, 200, 36), (780, 100, 200, 36),
     (300, 584, 200, 36), (780, 584, 200, 36),
     (560, 250, 40, 40), (680, 430, 40, 40)],
    # ----- четыре новые арены v3.2 (просьба игрока: «добавьте больше карт») -----
    # «Цитадель»: крепость-коробка в центре с воротами по сторонам
    [(576, 288, 48, 36), (656, 288, 48, 36),
     (576, 396, 48, 36), (656, 396, 48, 36),
     (576, 324, 36, 72), (668, 324, 36, 72),
     (300, 140, 72, 72), (908, 508, 72, 72),
     (300, 508, 72, 72), (908, 140, 72, 72)],
    # «Тиски»: два капкана по бокам и перекладины сверху/снизу
    [(430, 220, 80, 280), (770, 220, 80, 280),
     (250, 250, 110, 60), (920, 250, 110, 60),
     (560, 130, 160, 36), (560, 554, 160, 36)],
    # «Гребёнка»: вертикальные зубцы сверху и снизу, площадка в центре
    [(300, 80, 40, 140), (480, 80, 40, 140),
     (760, 80, 40, 140), (940, 80, 40, 140),
     (300, 500, 40, 140), (480, 500, 40, 140),
     (760, 500, 40, 140), (940, 500, 40, 140),
     (590, 330, 100, 60)],
    # «Перекрёсток»: Г-углы по квадрантам и столб в центре
    [(380, 180, 140, 36), (380, 180, 36, 140),
     (760, 504, 140, 36), (864, 404, 36, 140),
     (760, 180, 140, 36), (864, 180, 36, 140),
     (380, 504, 140, 36), (380, 404, 36, 140),
     (602, 332, 76, 56)],
    # v3.3 «Пустырь»: чистый пол — база для СВОИХ карт из редактора
    # (и честная дуэль без укрытий, если выпадет в обычных режимах)
    [],
]

MAP_NAMES = ["Классика", "Крестовина", "Колонны", "Уголки",
             "Полоса", "Соты", "Мосты", "Бункер", "Веер", "Шахты",
             "Вилка", "Кольцо", "Зигзаг", "Казармы", "Ступени", "Бухта",
             "Цитадель", "Тиски", "Гребёнка", "Перекрёсток",
             "Пустырь"]

# индекс пустой раскладки — на ней строятся СВОИ карты из редактора
EMPTY_VARIANT = len(LAYOUTS) - 1


# ================= ШТУРМОВЫЕ КАРТЫ (v3.3 «КРЕПОСТЬ») =================
#
# Три встроенные карты со ЗДАНИЕМ: защитники запираются внутри, точка
# захвата стоит в здании, атака приезжает с противоположной стороны.
# Здание собрано из КАЗЁННЫХ стен-барьеров: их можно ПРОЛОМАТЬ снарядами
# и ЧИНИТЬ ключом (H) — но только защитникам.

# наружные стены — ОЧЕНЬ ПРОЧНЫЕ, перегородки — ПРОЧНЫЕ (см. settings)


def _wall_run(x, y, ux, uy, n, tier, skip=()):
    """Прямой ряд из n сегментов стен шагом РОВНО в длину сегмента —
    концы сходятся встык, щелей нет. skip — номера сегментов,
    вырезанных под дверной проём."""
    out = []
    for i in range(n):
        if i in skip:
            continue
        out.append((x + ux * BARRIER_LEN * i, y + uy * BARRIER_LEN * i,
                    0.0 if ux else 90.0, tier))
    return out


def _door_skips(n, frac, units):
    """Номера сегментов, попавших в дверной проём шириной units сегментов
    с центром на frac доле стороны (0…1). Дырка в 2 сегмента = 152 px —
    танк (48 px) проходит свободно."""
    c = frac * (n - 1)
    return tuple(i for i in range(n) if abs(i - c) < units / 2.0)


def _assault_map(name, variant, bx, by, cols, rows, doors, inners,
                 atk_side):
    """Собрать штурмовую карту: здание cols×rows сегментов с центром
    (bx, by), двери на сторонах (N/S/W/E), перегородки внутри.
    doors: [(сторона, доля вдоль стороны, ширина в сегментах)].
    inners: [("h"|"v", смещение в сегментах от левого/верхнего края,
    от, до, доля двери, ширина двери)]. atk_side — где появляются
    атакующие (противоположная зданию сторона)."""
    hw, hh = cols * BARRIER_LEN / 2.0, rows * BARRIER_LEN / 2.0
    x0, y0 = bx - hw, by - hh
    segs = []
    for side, n, sx, sy, ux, uy in (
            ("N", cols, x0 + BARRIER_LEN / 2, y0, 1, 0),
            ("S", cols, x0 + BARRIER_LEN / 2,
             y0 + rows * BARRIER_LEN, 1, 0),
            ("W", rows, x0, y0 + BARRIER_LEN / 2, 0, 1),
            ("E", rows, x0 + cols * BARRIER_LEN,
             y0 + BARRIER_LEN / 2, 0, 1)):
        skip = set()
        for dside, frac, units in doors:
            if dside == side:
                skip |= set(_door_skips(n, frac, units))
        segs += _wall_run(sx, sy, ux, uy, n, ASSAULT_BUILD_OUT_TIER, skip)
    for kind, off, a, b, dfrac, dunits in inners:
        if kind == "h":
            segs += _wall_run(x0 + a * BARRIER_LEN + BARRIER_LEN / 2,
                              y0 + off * BARRIER_LEN, 1, 0, b - a,
                              ASSAULT_BUILD_IN_TIER,
                              _door_skips(b - a, dfrac, dunits))
        else:
            segs += _wall_run(x0 + off * BARRIER_LEN,
                              y0 + a * BARRIER_LEN + BARRIER_LEN / 2,
                              0, 1, b - a, ASSAULT_BUILD_IN_TIER,
                              _door_skips(b - a, dfrac, dunits))
    # защитники — кольцом вокруг точки ВНУТРИ здания (радиус 190:
    # до перегородок остаётся зазор, танки появляются не в стенах)
    def_spawns = []
    for j in range(ASSAULT_DEF_SPAWNS):
        a = math.radians(90 + j * 360.0 / ASSAULT_DEF_SPAWNS)
        def_spawns.append((bx + math.cos(a) * 190,
                           by + math.sin(a) * 190))
    # атакующие — ровной шеренгой ВО ВСЮ противоположную сторону
    # (всегда внутри карты, шаг ≥ 158 px)
    atk_spawns = []
    for j in range(ASSAULT_ATK_SPAWNS):
        t = j * (TEAM_ARENA_W - 760) / (ASSAULT_ATK_SPAWNS - 1.0) + 380
        s = j * (TEAM_ARENA_H - 760) / (ASSAULT_ATK_SPAWNS - 1.0) + 380
        if atk_side == "S":
            atk_spawns.append((t, TEAM_ARENA_H - 320))
        elif atk_side == "N":
            atk_spawns.append((t, 320))
        elif atk_side == "W":
            atk_spawns.append((420, s))
        else:                                   # "E"
            atk_spawns.append((TEAM_ARENA_W - 420, s))
    return dict(name=name, variant=variant, segs=segs, point=(bx, by),
                hw=hw, hh=hh, def_spawns=def_spawns,
                atk_spawns=atk_spawns)


ASSAULT_MAPS = [
    # «ДОМ»: жилье на севере карты; главный вход с юга (широкие ворота),
    # боковые двери с запада и востока; внутри — зал с двумя галереями
    _assault_map("ДОМ", 15, 1944, 760, 18, 10,
                 doors=(("S", 0.5, 3), ("W", 0.5, 2), ("E", 0.35, 2)),
                 inners=(("h", 2, 2, 16, 0.5, 2),
                         ("h", 8, 2, 16, 0.5, 2)),
                 atk_side="S"),
    # «СКЛАД»: длинное хранилище у восточной стены; ворота с запада (двое),
    # калитки с севера и юга; внутри — ряды стеллажей-перегородок
    _assault_map("СКЛАД", 12, 3054, 1094, 14, 18,
                 doors=(("W", 0.3, 2), ("W", 0.75, 2),
                        ("N", 0.5, 2), ("S", 0.5, 2)),
                 inners=(("v", 2, 2, 16, 0.5, 2),
                         ("v", 12, 2, 16, 0.5, 2)),
                 atk_side="W"),
    # «ФОРТ»: крепость в северо-западном углу; ворота с юга и калитка
    # с востока; внутри — казарма-перегородка и колонный зал
    _assault_map("ФОРТ", 10, 910, 644, 16, 9,
                 doors=(("S", 0.4, 3), ("E", 0.6, 2)),
                 inners=(("h", 3, 2, 14, 0.5, 2),
                         ("v", 4, 2, 6, 0.5, 0)),
                 atk_side="S"),
]

# ================= СВОИ КАРТЫ (v3.3: редактор карт) =================
#
# Формат maps/custom_N.txt: первая строка — название, дальше 27 строк
# по 48 символов (клетка 81 px = ровно командная арена):
#   .  пусто          #  стена (вечная)      S/H/U  прочные стены-барьеры
#   P  точка захвата  D  спавн обороны       A      спавн атаки
# v3.4: те же сетки с именем custom_battle_N.txt — карты для ВСЕХ
# остальных режимов (FFA и командные): P не нужен, D — спавн союзников,
# A — спавн врагов (в FFA те и другие — просто точки появления).

_CUSTOM_TIER = {"S": "strong", "H": "heavy", "U": "ultra"}


def custom_map_path(idx):
    return os.path.join(MAPS_DIR, "custom_%d.txt" % idx)


def save_custom_map(name, grid):
    """Сохранить карту редактора: ищем свободный номер custom_N.txt.
    grid — список из EDITOR_ROWS строк по EDITOR_COLS символов.
    Возвращает путь записанного файла."""
    os.makedirs(MAPS_DIR, exist_ok=True)
    idx = 1
    while os.path.exists(custom_map_path(idx)):
        idx += 1
    path = custom_map_path(idx)
    with open(path, "w", encoding="utf-8") as f:
        f.write((name or "Карта игрока") + "\n")
        for row in grid:
            f.write("".join(row) + "\n")
    return path


def parse_custom_map(path):
    """Разобрать файл своей карты. Возвращает dict с именем, стенами,
    сегментами барьеров, точкой и спавнами — или None, если карта
    нечитаема/неполноценна (нет точки или спавнов)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f]
    except OSError:
        return None
    lines = [ln for ln in lines if ln.strip() != ""]
    if len(lines) < EDITOR_ROWS + 1:
        return None
    name = lines[0].strip()[:40] or "Карта игрока"
    grid = lines[1:1 + EDITOR_ROWS]
    walls, segs, point = [], [], None
    def_spawns, atk_spawns = [], []
    for r, row in enumerate(grid):
        for c, ch in enumerate(row[:EDITOR_COLS]):
            wx, wy = c * EDITOR_CELL + EDITOR_CELL / 2.0, \
                     r * EDITOR_CELL + EDITOR_CELL / 2.0
            if ch == "#":
                walls.append(pygame.Rect(c * EDITOR_CELL, r * EDITOR_CELL,
                                         EDITOR_CELL, EDITOR_CELL))
            elif ch in _CUSTOM_TIER:
                segs.append((wx, wy, 0.0, _CUSTOM_TIER[ch]))
            elif ch == "P":
                point = (wx, wy)
            elif ch == "D":
                def_spawns.append((wx, wy))
            elif ch == "A":
                atk_spawns.append((wx, wy))
    if point is None or not def_spawns or not atk_spawns:
        return None
    return dict(name=name, custom=True, walls=walls, segs=segs,
                point=point, def_spawns=def_spawns,
                atk_spawns=atk_spawns)


def load_custom_maps():
    """Все свои ШТУРМОВЫЕ карты из папки maps (custom_*.txt, но НЕ
    custom_battle_* — те для обычных режимов) — пригодные к бою.
    Папки может не быть — это нормально, вернём пустой список."""
    if not os.path.isdir(MAPS_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(MAPS_DIR)):
        if not (fn.startswith("custom_") and fn.endswith(".txt")):
            continue
        if fn.startswith("custom_battle_"):
            continue      # v3.4: боевые карты — отдельная ротация
        m = parse_custom_map(os.path.join(MAPS_DIR, fn))
        if m is not None:
            out.append(m)
    return out


# ================= СВОИ БОЕВЫЕ КАРТЫ (v3.4: редактор для ВСЕХ режимов) =================

def custom_battle_path(idx):
    return os.path.join(MAPS_DIR, "custom_battle_%d.txt" % idx)


def save_custom_battle_map(name, grid):
    """Сохранить БОЕВУЮ карту редактора (FFA и командные режимы):
    ищем свободный номер custom_battle_N.txt. Возвращает путь файла."""
    os.makedirs(MAPS_DIR, exist_ok=True)
    idx = 1
    while os.path.exists(custom_battle_path(idx)):
        idx += 1
    path = custom_battle_path(idx)
    with open(path, "w", encoding="utf-8") as f:
        f.write((name or "Арена игрока") + "\n")
        for row in grid:
            f.write("".join(row) + "\n")
    return path


def parse_custom_battle_map(path):
    """Разобрать БОЕВУЮ карту (для FFA и командных): стены, барьеры
    и СПАВНЫ (D — союзники/игрок, A — враги; в FFA те и другие —
    просто точки появления). Точки захвата здесь не нужны.
    Возвращает dict или None, если карта неполноценна (нет D или A)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f]
    except OSError:
        return None
    lines = [ln for ln in lines if ln.strip() != ""]
    if len(lines) < EDITOR_ROWS + 1:
        return None
    name = lines[0].strip()[:40] or "Арена игрока"
    grid = lines[1:1 + EDITOR_ROWS]
    walls, segs = [], []
    spawns_d, spawns_a = [], []
    for r, row in enumerate(grid):
        for c, ch in enumerate(row[:EDITOR_COLS]):
            wx, wy = c * EDITOR_CELL + EDITOR_CELL / 2.0, \
                     r * EDITOR_CELL + EDITOR_CELL / 2.0
            if ch == "#":
                walls.append(pygame.Rect(c * EDITOR_CELL, r * EDITOR_CELL,
                                         EDITOR_CELL, EDITOR_CELL))
            elif ch in _CUSTOM_TIER:
                segs.append((wx, wy, 0.0, _CUSTOM_TIER[ch]))
            elif ch == "D":
                spawns_d.append((wx, wy))
            elif ch == "A":
                spawns_a.append((wx, wy))
    if not spawns_d or not spawns_a:
        return None
    return dict(name=name, custom=True, battle=True, walls=walls, segs=segs,
                spawns_d=spawns_d, spawns_a=spawns_a)


def load_custom_battle_maps():
    """Все свои БОЕВЫЕ карты (custom_battle_*.txt) — для FFA и командных
    режимов. Папки может не быть — это нормально."""
    if not os.path.isdir(MAPS_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(MAPS_DIR)):
        if fn.startswith("custom_battle_") and fn.endswith(".txt"):
            m = parse_custom_battle_map(os.path.join(MAPS_DIR, fn))
            if m is not None:
                out.append(m)
    return out


class Arena:
    def __init__(self, variant=0, shuffle=False, team=False, army=False):
        """shuffle=True — случайное зеркало и/или случайные баррикады:
        одна и та же карта каждый раз играет по-новому.
        team=True — БОЛЬШАЯ карта: крупнее обычной (v2.5), там много
        танков; с v2.7 на них играют и большие FFA (6-10 танков).
        army=True (v2.8) — САМАЯ БОЛЬШАЯ карта: под 6на6…10на10,
        где танков от 12 до 20 (перекрывает флаг team)."""
        self.variant = variant % len(LAYOUTS)
        if army:
            self.w, self.h = ARMY_ARENA_W, ARMY_ARENA_H
        elif team:
            self.w, self.h = TEAM_ARENA_W, TEAM_ARENA_H
        else:
            self.w, self.h = ARENA_W, ARENA_H
        s = self.w / float(SCREEN_W)      # масштаб исходной раскладки
        self.wall_t = int(WALL_T * s)     # толщина внешних стен
        self.spawn_cols = [(int(x * s), int(y * s)) for x, y in _SPAWN_SRC]
        w, h = self.w, self.h
        wt = self.wall_t
        self.walls = [
            pygame.Rect(0, 0, w, wt),
            pygame.Rect(0, h - wt, w, wt),
            pygame.Rect(0, 0, wt, h),
            pygame.Rect(w - wt, 0, wt, h),
        ]
        obs = [pygame.Rect(r) for r in _scaled_layout(LAYOUTS[self.variant], s)]
        tags = []
        if shuffle:
            mx, my = (random.random() < 0.5, random.random() < 0.5)
            if mx:   # зеркалим по горизонтали
                obs = [pygame.Rect(w - r.x - r.w, r.y, r.w, r.h) for r in obs]
            if my:   # и по вертикали
                obs = [pygame.Rect(r.x, h - r.y - r.h, r.w, r.h) for r in obs]
            if mx or my:
                tags.append("зеркало")
            added = self._add_props(obs)
            if added:
                tags.append("+%d баррикад" % added)
        self.obstacles = obs
        self.rects = self.walls + self.obstacles
        self.name = (MAP_NAMES[self.variant]
                     + (" [огромная]" if army else
                        " [большая]" if team else "")
                     + (" ★" if tags else ""))
        self.dynamic = []   # живые препятствия (стены-барьеры), меняются в бою
        self._bg = self._make_background()

    def _add_props(self, obs):
        """Накидать 0..PROP_MAX случайных баррикад в свободные места —
        подальше от стен, других препятствий и точек появления танков.
        Размер баррикад и отступы тянутся за масштабом карты (v2.5)."""
        s = self.w / float(SCREEN_W)
        k = s / 1.5           # базовые размеры рассчитаны на масштаб 1.5
        wt, w, h = self.wall_t, self.w, self.h
        added = 0
        for _ in range(70):
            if added >= PROP_MAX:
                break
            if added and random.random() < 0.4:
                break            # бывает и пара баррикад, и ноль
            pw, ph = random.choice(((54, 54), (84, 42), (42, 84), (72, 72)))
            pw, ph = max(20, int(pw * k)), max(20, int(ph * k))
            x = random.uniform(wt + 100 * k, w - wt - 100 * k - pw)
            y = random.uniform(wt + 90 * k, h - wt - 90 * k - ph)
            r = pygame.Rect(int(x), int(y), pw, ph)
            if any(r.inflate(int(110 * k), int(110 * k)).colliderect(o)
                   for o in obs):
                continue
            cx, cy = r.center
            if any((cx - sx) ** 2 + (cy - sy) ** 2 < (210 * k) ** 2
                   for sx, sy in self.spawn_cols):
                continue
            obs.append(r)
            added += 1
        return added

    def set_dynamic(self, blockers):
        self.dynamic = blockers

    def clear_around(self, x, y, r):
        """v3.2: убрать статические препятствия, попадающие в круг (x, y, r).
        ШТУРМ ставит точку захвата в центр карты — обломки стен в точке
        и в зоне форта не нужны."""
        box = pygame.Rect(int(x - r), int(y - r), int(2 * r), int(2 * r))
        self.obstacles = [o for o in self.obstacles if not o.colliderect(box)]
        self.rects = self.walls + self.obstacles

    def clear_box(self, rect):
        """v3.3: убрать статические препятствия, влезающие в ПРЯМОУГОЛЬНИК
        (под здание штурмовой карты — круг там срезал бы углы)."""
        rect = pygame.Rect(rect)
        self.obstacles = [o for o in self.obstacles
                          if not o.colliderect(rect)]
        self.rects = self.walls + self.obstacles

    def add_static(self, rects):
        """v3.3: добавить статические препятствия (свои карты редактора).
        Вечные, как и прочие стены арены: снаряды отскакивают, танки
        объезжают. Возвращает число добавленных."""
        rects = [pygame.Rect(r) for r in rects]
        self.obstacles.extend(rects)
        self.rects = self.walls + self.obstacles
        return len(rects)

    def walls_only(self):
        """Вид арены без барьеров — для снарядов (те бьют барьеры отдельно)."""
        return _WallsView(self)

    # ----- фон: неоновая сетка на весь большой мир -----
    def _make_background(self):
        bg = pygame.Surface((self.w, self.h))
        bg.fill(COL_BG)
        for gx in range(0, self.w, 48):
            pygame.draw.line(bg, COL_GRID, (gx, 0), (gx, self.h))
        for gy in range(0, self.h, 48):
            pygame.draw.line(bg, COL_GRID, (0, gy), (self.w, gy))
        return bg

    def draw(self, surf, ox=0, oy=0):
        surf.blit(self._bg, (int(ox), int(oy)))
        for r in self.obstacles:
            glow = r.inflate(12, 12)
            pygame.draw.rect(surf, (36, 44, 84), glow.move(int(ox), int(oy)), border_radius=8)
            pygame.draw.rect(surf, COL_WALL, r.move(int(ox), int(oy)), border_radius=6)
            pygame.draw.rect(surf, (150, 165, 230), r.move(int(ox), int(oy)), 2, border_radius=6)

    # ----- коллизии -----
    @staticmethod
    def _circle_rect(x, y, radius, rect):
        cx = max(rect.left, min(x, rect.right))
        cy = max(rect.top, min(y, rect.bottom))
        return (x - cx) ** 2 + (y - cy) ** 2 < radius * radius

    def circle_collides(self, x, y, radius):
        if any(self._circle_rect(x, y, radius, r) for r in self.rects):
            return True
        return any(d.blocks_circle(x, y, radius) for d in self.dynamic)

    def point_blocked(self, x, y):
        if any(r.collidepoint(x, y) for r in self.rects):
            return True
        return any(d.blocks_point(x, y) for d in self.dynamic)

    def line_blocked(self, x1, y1, x2, y2, step=24):
        """Есть ли препятствие на линии (проверка: видит ли бот цель)."""
        d = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(d // step))
        for i in range(1, n):
            t = i / n
            if self.point_blocked(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
                return True
        return False

    def raycast(self, x, y, angle, max_dist=2000.0, step=6.0):
        """Куда попадёт мгновенный луч из (x, y) под углом angle.
        Возвращает точку попадания в стену/препятствие или конец луча."""
        rad = math.radians(angle)
        dx, dy = math.cos(rad) * step, math.sin(rad) * step
        dist = 0.0
        while dist < max_dist:
            x += dx
            y += dy
            dist += step
            if self.point_blocked(x, y):
                return x, y
        return x, y

    def free_spot(self, avoid=(), avoid_dist=150):
        """Случайная свободная точка (для появления бонусов)."""
        for _ in range(200):
            x = random.uniform(self.wall_t + 70, self.w - self.wall_t - 70)
            y = random.uniform(self.wall_t + 70, self.h - self.wall_t - 70)
            if self.circle_collides(x, y, 30):
                continue
            if all((x - ax) ** 2 + (y - ay) ** 2 > avoid_dist ** 2 for ax, ay in avoid):
                return x, y
        return self.w / 2, self.h / 2


class _WallsView:
    """Тонкая обёртка: та же арена, но без динамических барьеров.
    Нужна снарядам — те взаимодействуют с барьерами через урон в game.py."""

    def __init__(self, arena):
        self._a = arena

    @property
    def rects(self):
        return self._a.rects

    def circle_collides(self, x, y, radius):
        return any(self._a._circle_rect(x, y, radius, r) for r in self._a.rects)

    def point_blocked(self, x, y):
        return any(r.collidepoint(x, y) for r in self._a.rects)

    def line_blocked(self, x1, y1, x2, y2, step=24):
        d = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(d // step))
        for i in range(1, n):
            t = i / n
            if self.point_blocked(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
                return True
        return False
