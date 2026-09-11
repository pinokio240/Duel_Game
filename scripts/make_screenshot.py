# -*- coding: utf-8 -*-
"""Делает свежий screenshot.png боя для README (headless)."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame
from game import Game

g = Game()
g.state = "fight"
g._reset_round()
g._fake_keys = type("K", (), {"__getitem__": staticmethod(lambda k: 0)})()

# прогрев боя, чтобы были снаряды/эффекты
for _ in range(240):
    g.update(1 / 60.0)

# немного постановки: стихия и стена у игрока, бонус на арене
g.player.apply_powerup("fire")
g.player.apply_powerup("barrier")
g._place_barrier(g.player)
g.player.element_shots = 4
g.player.x, g.player.y = 340, 420
g.arena.set_dynamic(g.barriers)
g.update(1 / 60.0)
g.draw()
pygame.image.save(g.screen, os.path.join(ROOT, "screenshot.png"))
print("screenshot.png обновлён")
pygame.quit()
