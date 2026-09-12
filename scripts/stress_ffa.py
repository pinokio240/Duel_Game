# -*- coding: utf-8 -*-
"""Стресс: полные FFA-матчи (3/4/5 танков) под dummy-видео — ничто не падает."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
from game import Game  # noqa: E402
import game as game_mod  # noqa: E402

# Мир стал большим (v2.4, 2240x1260 — x3 площади старой карты) и раунды идут дольше — полный матч до
# 5 побед в симуляции занимает 10+ минут. Для стресса (проверить, что ничто
# не падает: раунды, спавны, зона, реванш) сокращаем матч до 2 побед.
game_mod.ROUNDS_TO_WIN = 2


class FakeKeys:
    def __getitem__(self, k):
        return 0


def play_match(mode, max_sec=240):
    g = Game()
    g.mode = mode
    g.state = "menu"
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert g.state == "select"
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert g.state == "intro", g.state
    g._fake_keys = FakeKeys()
    # v2.5: неуязвимости больше нет — ничего снимать не нужно
    frames = 0
    limit = int(max_sec * 60)
    while g.state != "match_end" and frames < limit:
        g.update(1 / 60.0)
        if frames % 60 == 0:
            g.draw()   # HUD/арена/баннеры рисуются на разных состояниях
        frames += 1
    assert g.state == "match_end", "матч %d танков не завершился за %d сек" % (
        mode, max_sec)
    # доигрываем до экрана конца матча и проверяем очки/таблицу
    winner = max(range(len(g.score)), key=lambda i: g.score[i])
    assert g.final_score >= 0
    assert len(g.stats["score_table"]) >= 1
    print("OK матч на %d танков: %d кадров (%.1f сек), счёт %s, итог %d очков"
          % (mode, frames, frames / 60.0, g._score_str(), g.final_score))
    # реванш тоже стартует без ошибок
    g.on_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert g.state == "intro"
    for _ in range(120):
        g.update(1 / 60.0)
    print("OK реванш на %d танков стартовал, раунд 2 идёт" % mode)


if __name__ == "__main__":
    pygame.init()
    # v2.6: карты ещё крупнее + после смерти игрока боты 180 с выясняют
    # победителя (кнопка «УБИТЬ СРАЗУ» отдаёт раунд случайному боту)
    # — раунды длиннее, лимиты выше.
    # Режимы можно передать аргументами: python scripts/stress_ffa.py 16 20
    # (удобно гонять длинный стресс частями), без аргументов — все сразу.
    ALL = {3: 1800, 4: 1800, 5: 1800,
           11: 1200, 12: 1200, 13: 1200, 14: 1800, 15: 1800,
           6: 900, 8: 900, 9: 900, 10: 1200, 7: 1200,
           16: 1500, 17: 1500, 18: 1800, 19: 1800, 20: 1800}
    argv = [int(a) for a in sys.argv[1:] if a.isdigit()]
    for m in (argv if argv else sorted(ALL)):
        play_match(m, max_sec=ALL.get(m, 1800))
    print("СТРЕСС-ТЕСТ ПРОЙДЕН")
