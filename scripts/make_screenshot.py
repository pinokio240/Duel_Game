# -*- coding: utf-8 -*-
"""Обновляет screenshot.png боя и делает garage.png для проверки верстки."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame
from game import Game

g = Game()
# сборка из 8 частей: шасси, корпус, дуло, перк, стихия, проклятья,
# облегчения, эффекты на врага
g.build = ("medium", "medium", "standard", "none", "fire", (), (), ())   # стихия — в сборке
g.state = "fight"
g._reset_round()
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

# ангар: 5 панелей + жребий + эффекты на врага — снимок для проверки верстки
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
pygame.quit()
