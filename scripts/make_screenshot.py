# -*- coding: utf-8 -*-
"""Обновляет screenshot.png боя, ffa.png (режим на 5) и garage.png."""
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
g.player.x, g.player.y = 340, 420
g.arena.set_dynamic(g.barriers)
g.update(1 / 60.0)
g.draw()
pygame.image.save(g.screen, os.path.join(ROOT, "screenshot.png"))
print("screenshot.png обновлён")

# ----- кадр режима «все против всех» на 5 танков -----
g.mode = 5
g.score = [0] * g.mode
g.bot_builds = [("light", "light", "shotgun", "sprinter", "electric"),
                ("heavy", "armored", "howitzer", "turtle", "fire"),
                ("medium", "medium", "rapidgun", "gunner", "poison"),
                ("sport", "compact", "long", "none", "vamp")]
g._reset_round()
g.arena = Arena(5)          # «Соты» — красиво для толпы
g._fake_keys = type("K", (), {"__getitem__": staticmethod(lambda k: 0)})()
for _ in range(300):        # полминуты боя: следы, снаряды, дым
    g.update(1 / 60.0)
g.draw()
out = "/home/z/my-project/tool-results/ffa.png"
pygame.image.save(g.screen, out)
print("ffa.png:", out)

# ангар: 5 панелей + жребий + эффекты на врага — снимок для проверки верстки
g.mode = 2
g.state = "select"
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

# меню: режимы боя (кнопки 1×1 … 1×1×1×1×1)
g.state = "menu"
g.mode = 3
g.draw()
out3 = "/home/z/my-project/tool-results/menu.png"
pygame.image.save(g.screen, out3)
print("menu.png:", out3)
pygame.quit()
