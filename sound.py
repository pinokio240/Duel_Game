# -*- coding: utf-8 -*-
"""
Звуки генерируются кодом через numpy — никаких файлов не нужно.
Если numpy или аудиоустройство недоступны, игра спокойно работает без звука.
"""
import pygame


class SoundBank:
    def __init__(self):
        self.ok = False
        self.sounds = {}
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            import numpy as np
            self.np = np
            self._build()
            self.ok = True
        except Exception:
            self.ok = False  # играем без звука

    # ----- помощники синтеза -----
    def _arr(self, samples):
        arr = (self.np.clip(samples, -1.0, 1.0) * 32000).astype(self.np.int16)
        return pygame.sndarray.make_sound(arr)

    def _env(self, n, p=2.0):
        """Огибающая спада громкости."""
        return self.np.linspace(1.0, 0.0, n) ** p

    def _tone(self, freq, dur, vol=0.5, shape="sine", sweep=0.0):
        np, sr = self.np, 22050
        n = int(sr * dur)
        f = np.linspace(freq, freq + sweep, n) if sweep else np.full(n, float(freq))
        ph = np.cumsum(2 * np.pi * f / sr)
        if shape == "sine":
            w = np.sin(ph)
        elif shape == "square":
            w = np.sign(np.sin(ph)) * 0.7
        else:  # saw
            w = (((ph / np.pi) % 2) - 1) * 0.6
        return w * self._env(n) * vol

    def _noise(self, dur, vol=0.5, p=2.5, sub_freq=0, sub_vol=0.0):
        np, sr = self.np, 22050
        n = int(sr * dur)
        w = np.random.uniform(-1, 1, n) * self._env(n, p) * vol
        if sub_freq:
            w = w + np.sin(2 * np.pi * sub_freq * np.arange(n) / sr) * self._env(n) * sub_vol
        return w

    # ----- набор звуков игры -----
    def _build(self):
        np = self.np
        s = self._arr
        self.sounds["shoot"]   = s(self._tone(900, 0.09, 0.35, "square", sweep=-520))
        self.sounds["ric"]     = s(self._tone(310, 0.06, 0.22, "square", sweep=140))
        self.sounds["hit"]     = s(self._noise(0.12, 0.45, p=3) + self._tone(160, 0.12, 0.3))
        self.sounds["explode"] = s(self._noise(0.55, 0.6, p=2) + self._tone(70, 0.55, 0.4))
        self.sounds["pickup"]  = s(np.concatenate([self._tone(660, 0.09, 0.35),
                                                   self._tone(990, 0.13, 0.35)]))
        self.sounds["round"]   = s(self._tone(440, 0.18, 0.32))
        self.sounds["laser"]   = s(self._tone(1400, 0.22, 0.35, "saw", sweep=-1150))
        self.sounds["freeze"]  = s(np.concatenate([self._tone(1250, 0.08, 0.3),
                                                   self._tone(1750, 0.12, 0.3)]))
        self.sounds["smoke"]   = s(self._noise(0.3, 0.3, p=1.6))
        self.sounds["mine"]    = s(self._tone(880, 0.07, 0.3, "square"))
        self.sounds["win"]     = s(np.concatenate([self._tone(523, 0.13, 0.35),
                                                   self._tone(659, 0.13, 0.35),
                                                   self._tone(784, 0.22, 0.4)]))
        self.sounds["lose"]    = s(np.concatenate([self._tone(392, 0.15, 0.35),
                                                   self._tone(330, 0.15, 0.35),
                                                   self._tone(262, 0.26, 0.4)]))
        for snd in self.sounds.values():
            snd.set_volume(0.55)

    def play(self, name):
        if self.ok and name in self.sounds:
            self.sounds[name].play()
