# -*- coding: utf-8 -*-
"""Обновляет screenshot.png боя, ffa.png (режим на 5), boss.png (БОСС),
team44.png (4 на 4), console.png (консоль разработчика) и garage.png."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame
from game import Game
from arena import Arena

g = Game()
# сборка из 8 частей: шасси, корпус, дуло, перк, стихия, проклятья,
# облегчения, эффекты на врага
g.build = ("medium", "medium", "standard", "none", "fire", (), (), ())   # стихия — в сборке
g.state = "fight"
g._reset_round()
g.arena = Arena(0)   # фиксированная «Классика» для стабильного кадра
g._fake_keys = type("K", (), {"__getitem__": staticmethod(lambda k: 0)})()

# прогрев боя, чтобы были снаряды/эффекты
for _ in range(240):
    g.update(1 / 60.0)

# немного постановки: стена у игрока, бонус на арене
g.player.apply_powerup("barrier")
g._place_barrier(g.player)
g.player.x, g.player.y = 480, 630
g._cam_snap()
g.arena.set_dynamic(g.barriers)
g.update(1 / 60.0)
g.draw()
pygame.image.save(g.screen, os.path.join(ROOT, "screenshot.png"))
print("screenshot.png обновлён")

# ----- кадр режима «все против всех» — БОЛЬШОЙ FFA на 8 танков (v2.7) -----
g.mode = 13
g.score = [0] * 8
g.bot_builds = [("light", "light", "shotgun", "sprinter", "electric"),
                ("heavy", "armored", "howitzer", "turtle", "fire"),
                ("medium", "medium", "rapidgun", "gunner", "poison"),
                ("sport", "compact", "long", "none", "vamp"),
                ("light", "compact", "twin", "sprinter", "water"),
                ("heavy", "heavy", "standard", "gunner", "earth"),
                ("sport", "light", "shotgun", "none", "ice")]
g._reset_round()
g.arena = Arena(5, team=True)   # «Соты» на КРУПНОЙ карте — красиво для толпы
g._fake_keys = type("K", (), {"__getitem__": staticmethod(lambda k: 0)})()
for _ in range(300):        # полминуты боя: следы, снаряды, дым
    g.update(1 / 60.0)
# v2.9: постановочная ТУРЕЛЬ у игрока — новинка в кадре
g.player.turret_charges = 1
g._place_turret(g.player)
g._cam_snap()
g.draw()
out = "/home/z/my-project/tool-results/ffa.png"
pygame.image.save(g.screen, out)
print("ffa.png:", out)

# ----- кадр командного режима «2 против БОССА» -----
g.mode = 7
g.score = [0, 0]
g.bot_builds = [("light", "light", "shotgun", "sprinter", "electric"),
                ("heavy", "heavy", "shotgun", "turtle", "fire")]
g._reset_round()
g.arena = Arena(0, team=(g.mode >= 6))
g._fake_keys = type("K", (), {"__getitem__": staticmethod(lambda k: 0)})()
for _ in range(200):
    g.update(1 / 60.0)
g._cam_snap()
g.draw()
out = "/home/z/my-project/tool-results/boss.png"
pygame.image.save(g.screen, out)
print("boss.png:", out)

# ----- кадр режима «4 НА 4» (v2.3): две шеренги по четыре танка -----
g.mode = 9
g.score = [0, 0]
g.bot_builds = [("light", "compact", "rapidgun", "sprinter", "electric"),
                ("sport", "light", "shotgun", "none", "earth"),
                ("heavy", "armored", "howitzer", "turtle", "poison"),
                ("medium", "medium", "twin", "gunner", "water"),
                ("light", "light", "long", "none", "none"),
                ("heavy", "armored", "standard", "turtle", "fire"),
                ("sport", "compact", "shotgun", "sprinter", "vamp")]
g._reset_round()
g._fake_keys = type("K", (), {"__getitem__": staticmethod(lambda k: 0)})()
for _ in range(240):
    g.update(1 / 60.0)
g._cam_snap()
g.draw()
out = "/home/z/my-project/tool-results/team44.png"
pygame.image.save(g.screen, out)
print("team44.png:", out)

# ----- кадр КОНСОЛИ РАЗРАБОТЧИКА: пишем «Ту», внизу подсказка «Турбо» -----
g.state = "fight"
g.con_open = True
g.con_input = "Ту"
g.con_lines = ["> Огонь Игрок", "Выдано «Огонь»: Игрок",
               "> Гаубица Бот", "Выдано «Гаубица»: Бот",
               "> Веер", "Кликни по карте, чтобы поставить «ВЕЕР»."]
g._cam_snap()
g.draw()
out = "/home/z/my-project/tool-results/console.png"
pygame.image.save(g.screen, out)
print("console.png:", out)
g.con_open = False

# ангар: панель БИЛДОВ + 5 панелей сборки + жребий + эффекты на врага
# (v2.9: выбран билд «СТРОИТЕЛЬ» — видно подсветку и новейшую панель)
g.mode = 2
g.state = "select"
g.sel_build = 0                  # СТРОИТЕЛЬ выделен
g.sel_el = 1                    # «Огонь» выделен
g.sel_curses = ["shaky", "rusty"]      # взято два проклятья
g.sel_blessings = ["armor"]            # открыто три облегчения, взято одно
g.sel_enemy_keys = ["e_sabotage"]      # саботаж на врага
g.sel_en = 1                           # курсор на «Саботаже»
g._draw_select()
out = "/home/z/my-project/tool-results/garage.png"
pygame.image.save(g.screen, out)
print("garage.png:", out)

# тултип: курсор над карточкой «Лёгкое» — окошко с описанием крупным шрифтом
g.draw()
zone = next(r for r, kd, d in g._click_zones if kd == "ch" and d == 0)
g._mouse = zone.center
g.draw()
out2 = "/home/z/my-project/tool-results/tooltip.png"
pygame.image.save(g.screen, out2)
print("tooltip.png:", out2)

# меню: режимы боя (кнопки 1×1 … 2×БОСС)
g.state = "menu"
g.mode = 3
g.draw()
out3 = "/home/z/my-project/tool-results/menu.png"
pygame.image.save(g.screen, out3)
print("menu.png:", out3)
pygame.quit()
