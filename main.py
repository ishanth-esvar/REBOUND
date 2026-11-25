
"""
REBOUND: The Last Bounce
A physics-based platforming adventure about resilience, recovery and bouncing back.

Run:      python rebound.py
Requires: pip install pygame
Debug:    python rebound.py --debug   (F1 god-mode, F2 all abilities, F3 jump to exit)

Controls
  A / D / Left / Right   move
  Space / W / Up         jump / bounce (hold = higher)
  S / Down               Power Bounce slam (in mid-air, once unlocked)
  Shift                  Energy Dash (once unlocked)
  E                      interact (ability shrines)
  Esc / P                pause
  F11                    fullscreen
"""
import array
import json
import math
import os
import random
import sys
import asyncio

try:
    import pygame
except ImportError:
    print("REBOUND needs pygame:  pip install pygame")
    sys.exit(1)
from pygame import Rect

W, H = 960, 540
FPS = 60
HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(HERE, "rebound_save.json")
DEBUG = "--debug" in sys.argv

# ----------------------------------------------------------------- physics
PS = 30
GRAV = 2100.0
TERM = 1050.0
RUN = 310.0
ACC_G, ACC_A, FRIC_G = 2600.0, 1700.0, 2800.0
ICE_ACC, ICE_FRIC = 520.0, 260.0
JUMP_V = -800.0
DJ_V = -720.0
WALL_VX, WALL_VY, WALL_SLIDE = 300.0, -780.0, 140.0
SPRING_V, POWER_V = -1020.0, -1380.0
SLAM_V, SLAM_BOUNCE = 1150.0, -1180.0
DASH_V, DASH_T, DASH_CD = 780.0, 0.17, 0.45
COYOTE, JBUF = 0.10, 0.12

ABILITIES = [
    ("bounce", "SPACE", "BASIC BOUNCE", ""),
    ("wall",   "WALL",  "WALL REBOUND", "Press SPACE while touching a wall to bounce off it"),
    ("power",  "SLAM",  "POWER BOUNCE", "Press S in mid-air to slam down - land for a huge rebound"),
    ("double", "x2",    "DOUBLE BOUNCE", "Press SPACE again in mid-air for a second bounce"),
    ("dash",   "DASH",  "ENERGY DASH", "Press SHIFT to burst quickly through gaps"),
]

THEMES = [
    dict(name="THE FALL", sub="Learning to stand again", sky=((10, 14, 40), (58, 42, 98)),
         body=(70, 82, 128), top=(120, 170, 230), accent=(70, 210, 255)),
    dict(name="THE FORGOTTEN FOREST", sub="Discovering strength", sky=((4, 24, 28), (18, 78, 62)),
         body=(60, 48, 44), top=(92, 200, 110), accent=(140, 255, 150)),
    dict(name="THE COLLAPSED MACHINE", sub="Facing difficult challenges", sky=((26, 16, 16), (84, 46, 30)),
         body=(78, 78, 92), top=(240, 150, 60), accent=(255, 170, 70)),
    dict(name="THE FROZEN VOID", sub="Learning to adapt", sky=((3, 6, 24), (16, 50, 96)),
         body=(112, 160, 205), top=(226, 246, 255), accent=(150, 230, 255)),
    dict(name="THE LAST REBOUND", sub="Becoming stronger after every fall", sky=((22, 6, 38), (100, 26, 86)),
         body=(70, 50, 104), top=(255, 205, 120), accent=(255, 120, 200)),
]

# ----------------------------------------------------------------- skins
# Each skin recolors the orb body/highlight/glow and the motion trail.
# Costs are in banked energy (earned by finishing levels).
SKINS = [
    dict(key="default", name="SPARK",   cost=0,   desc="A single spark of Core.",
         body=(30, 150, 235),  mid=(170, 245, 255), glow=(30, 120, 170),  trail=(70, 210, 255)),
    dict(key="ember",   name="EMBER",   cost=40,  desc="Runs hot. Never cools.",
         body=(235, 90, 40),   mid=(255, 200, 120), glow=(170, 60, 20),   trail=(255, 150, 70)),
    dict(key="verdant", name="VERDANT", cost=80,  desc="Grown, not built.",
         body=(40, 160, 80),   mid=(140, 255, 160), glow=(20, 100, 50),   trail=(140, 255, 150)),
    dict(key="violet",  name="WRAITH",  cost=140, desc="Not entirely here.",
         body=(120, 60, 200),  mid=(200, 140, 255), glow=(60, 20, 100),   trail=(190, 120, 255)),
    dict(key="aureate", name="AUREATE", cost=220, desc="Earned, not given.",
         body=(210, 160, 40),  mid=(255, 235, 120), glow=(120, 90, 10),   trail=(255, 220, 100)),
    dict(key="void",    name="VOID",    cost=350, desc="The Core, before the light.",
         body=(20, 20, 40),    mid=(80, 80, 140),   glow=(10, 10, 30),    trail=(70, 70, 130)),
]


def skin_by_key(key):
    for s in SKINS:
        if s["key"] == key:
            return s
    return SKINS[0]


FALL_QUOTES = [
    "Up. You know how this goes.",
    "That one was the gap's fault. Obviously.",
    "The ground wins sometimes. Not today.",
    "Nothing broke. Try the timing again.",
    "You've done this jump. Do it again.",
    "Faster next time. Don't think.",
    "Every fall leaves a mark. Use it.",
    "Still glowing. Still here.",
    "The Core is still up there.",
    "Next one. Go.",
]

STORY = [
    "The world ran on the Core. Not metaphorically - it actually ran, an engine of light "
    "buried under five worlds, holding the whole stack of them up and alive.",
    "When the Core cracked, it didn't make a sound. It just stopped. Everything that hung on it "
    "became still, and heavy, and started to fall.",
    "Some of it didn't finish falling. That's where you come in - a single spark of Core, "
    "drifting through the wreck, trying to remember how to put a world back together.",
    "You can't fly. You can only bounce. Fall, land, bounce higher. That's the trick. "
    "That's the whole trick.",
    "Go. Climb the broken world. Light the stations. Reach what's left of the Core.\n\n"
    "And every time you fall - get up. That's not the lesson. That's just how you climb.",
]


# ----------------------------------------------------------------- helpers
def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def approach(v, t, d):
    if v < t:
        return min(t, v + d)
    return max(t, v - d)


def mixc(a, b, t):
    return tuple(int(lerp(a[i], b[i], t)) for i in range(3))


def shade(c, k):
    return tuple(clamp(int(x + k), 0, 255) for x in c)


def ease_out(t):
    t = clamp(t, 0, 1)
    return 1 - (1 - t) ** 3


_glow_cache = {}


def add_glow(surf, pos, r, color):
    r = int(r)
    if r < 2:
        return
    key = (r, color)
    s = _glow_cache.get(key)
    if s is None:
        if len(_glow_cache) > 900:
            _glow_cache.clear()
        s = pygame.Surface((r * 2, r * 2))
        s.fill((0, 0, 0))
        for i in range(r, 0, -2):
            t = (1 - i / r) ** 2
            pygame.draw.circle(s, (int(color[0] * t), int(color[1] * t), int(color[2] * t)), (r, r), i)
        _glow_cache[key] = s
    surf.blit(s, (int(pos[0]) - r, int(pos[1]) - r), special_flags=pygame.BLEND_RGB_ADD)


_text_cache = {}


def render(font, s, color):
    k = (id(font), s, color)
    img = _text_cache.get(k)
    if img is None:
        if len(_text_cache) > 700:
            _text_cache.clear()
        img = font.render(s, True, color)
        _text_cache[k] = img
    return img


def draw_text(surf, s, font, color, pos, anchor="center", shadow=True, alpha=255):
    img = render(font, s, color)
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    r = img.get_rect()
    setattr(r, anchor, (int(pos[0]), int(pos[1])))
    if shadow:
        sh = render(font, s, (0, 0, 0))
        if alpha < 255:
            sh = sh.copy()
            sh.set_alpha(int(alpha * 0.6))
        surf.blit(sh, r.move(2, 2))
    surf.blit(img, r)
    return r


def glow_text(surf, s, font, color, glow, pos, anchor="center", alpha=255):
    key = ("g", id(font), s, glow)
    blur = _text_cache.get(key)
    if blur is None:
        base = font.render(s, True, glow)
        w, h = base.get_size()
        pad = pygame.Surface((w + 40, h + 40), pygame.SRCALPHA)
        pad.blit(base, (20, 20))
        small = pygame.transform.smoothscale(pad, ((w + 40) // 5, (h + 40) // 5))
        blur = pygame.transform.smoothscale(small, (w + 40, h + 40))
        _text_cache[key] = blur
    r = render(font, s, color).get_rect()
    setattr(r, anchor, (int(pos[0]), int(pos[1])))
    b = blur.copy()
    b.set_alpha(min(255, alpha))
    surf.blit(b, (r.x - 20, r.y - 20))
    surf.blit(b, (r.x - 20, r.y - 20))
    draw_text(surf, s, font, color, r.center, "center", True, alpha)


def panel(surf, rect, color=(8, 12, 30), alpha=170, radius=14, border=None, bw=2):
    rect = Rect(rect)
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    if border:
        pygame.draw.rect(s, (*border, min(255, alpha + 60)), s.get_rect(), bw, border_radius=radius)
    surf.blit(s, rect.topleft)


def wrap_text(font, s, width):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.size(t)[0] <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fmt_time(t):
    m = int(t // 60)
    return "%d:%04.1f" % (m, t - m * 60)


def make_gradient(c1, c2, w=W, h=H):
    s = pygame.Surface((w, h))
    for y in range(h):
        pygame.draw.line(s, mixc(c1, c2, y / (h - 1)), (0, y), (w, y))
    return s


# ----------------------------------------------------------------- audio
class Audio:
    def __init__(self, settings):
        self.s = settings
        self.ok = False
        self.sounds = {}
        self.music_cache = {}
        self.music_world = None
        self.music_layer_ch = []
        self.intensity = 0.0
        self.target_intensity = 0.0
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.sr, fmt, self.ch = pygame.mixer.get_init()
            if fmt != -16:
                raise RuntimeError("unsupported mixer format")
            pygame.mixer.set_reserved(3)
            for i in range(3):
                self.music_layer_ch.append(pygame.mixer.Channel(i))
            self.ok = True
            self._build_sfx()
        except Exception:
            self.ok = False

    def _mk(self, samples):
        data = array.array("h")
        for v in samples:
            iv = int(max(-1.0, min(1.0, v)) * 30000)
            for _ in range(self.ch):
                data.append(iv)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _adsr(self, n, a=0.005, d=0.08, s=0.7, r=0.15):
        sr = self.sr
        ai = max(1, int(a * sr)); di = max(1, int(d * sr)); ri = max(1, int(r * sr))
        si = max(0, n - ai - di - ri)
        env = [i / ai for i in range(ai)]
        env += [1.0 - (1.0 - s) * i / di for i in range(di)]
        env += [s] * si
        env += [s * (1.0 - i / ri) for i in range(ri)]
        while len(env) < n:
            env.append(0.0)
        return env[:n]

    def _detune_osc(self, f, n, kind="sine", spread=0.008, voices=3):
        sr = self.sr
        phases = [random.random() * 6.283 for _ in range(voices)]
        out = [0.0] * n
        for v in range(voices):
            det = 1.0 + (v - (voices - 1) / 2) * spread
            w = 2 * math.pi * f * det / sr
            ph = phases[v]
            if kind == "sine":
                for i in range(n):
                    out[i] += math.sin(ph + w * i)
            elif kind == "tri":
                for i in range(n):
                    out[i] += math.asin(math.sin(ph + w * i)) * 2 / math.pi
            else:
                for i in range(n):
                    out[i] += ((ph + w * i) / (2 * math.pi)) % 1.0 * 2 - 1
        return [v / voices for v in out]

    def _comb(self, samples, delay, fb):
        out = [0.0] * len(samples)
        d = max(1, delay)
        for i in range(len(samples)):
            out[i] = samples[i] + (out[i - d] * fb if i >= d else 0)
        return out

    def _allpass(self, samples, delay, g):
        out = [0.0] * len(samples)
        d = max(1, delay)
        buf = [0.0] * d
        for i in range(len(samples)):
            bd = buf[i % d]
            in_ = samples[i] + g * bd
            out[i] = bd - g * in_
            buf[i % d] = in_
        return out

    def _reverb(self, samples, wet=0.22):
        ds = (1116, 1277)
        combs = [self._comb(samples, d, 0.72) for d in ds]
        mixed = [sum(c[i] for c in combs) * 0.5 for i in range(len(samples))]
        ap = self._allpass(self._allpass(mixed, 556, 0.5), 441, 0.5)
        return [samples[i] * (1 - wet) + ap[i] * wet for i in range(len(samples))]

    def _lowpass(self, samples, cutoff):
        out = [0.0] * len(samples)
        alpha = 1.0 - math.exp(-2 * math.pi * cutoff / self.sr)
        prev = 0.0
        for i, s in enumerate(samples):
            prev += alpha * (s - prev)
            out[i] = prev
        return out

    def _build_sfx(self):
        def t(f0, f1, dur, vol=0.5, kind="sine", decay=2.0):
            sr = self.sr; n = int(sr * dur)
            env = [max(0.0, 1 - i / n) ** decay for i in range(n)]
            out = []; ph = 0.0
            for i in range(n):
                x = i / n
                ph += 2 * math.pi * (f0 + (f1 - f0) * x) / sr
                if kind == "sine":
                    v = math.sin(ph)
                elif kind == "tri":
                    v = math.asin(math.sin(ph)) * 2 / math.pi
                elif kind == "square":
                    v = 0.6 if math.sin(ph) > 0 else -0.6
                else:
                    v = random.uniform(-1, 1)
                out.append(v * vol * env[i])
            return out

        def mx(*tr):
            n = max(len(x) for x in tr)
            out = [0.0] * n
            for x in tr:
                for i, v in enumerate(x):
                    out[i] += v
            return out

        def ct(*tr):
            o = []
            for x in tr:
                o.extend(x)
            return o

        d = {
            "jump":    t(360, 640, 0.12, 0.5, decay=1.5),
            "land":    t(130, 70, 0.08, 0.5),
            "spring":  mx(t(260, 900, 0.24, 0.45), t(520, 1300, 0.2, 0.25)),
            "power":   mx(t(150, 45, 0.4, 0.8, decay=1.2), t(0, 0, 0.22, 0.35, "noise", 3)),
            "chime":   mx(t(988, 988, 0.34, 0.28), t(1480, 1480, 0.34, 0.2)),
            "crystal": ct(t(784, 784, 0.09, 0.3), t(1047, 1047, 0.09, 0.3), t(1568, 1568, 0.3, 0.3)),
            "station": mx(t(300, 900, 0.45, 0.3, "square", 1), t(450, 1350, 0.45, 0.2)),
            "unlock":  ct(*[t(f, f, 0.11, 0.35, "tri", 1) for f in (523, 659, 784, 1047, 1319)],
                          t(1568, 1568, 0.6, 0.35, "sine", 1.5)),
            "restore": mx(t(150, 1400, 1.3, 0.4, decay=0.6), t(300, 2800, 1.3, 0.18, "tri", 0.8)),
            "victory": ct(*[t(f, f, 0.16, 0.35, "tri", 1) for f in (523, 659, 784, 659, 784, 1047)],
                          t(1047, 1047, 0.8, 0.4, "tri", 1.5)),
            "die":     t(520, 55, 0.5, 0.5, "tri", 1),
            "dash":    mx(t(0, 0, 0.16, 0.25, "noise", 2), t(500, 220, 0.16, 0.3)),
            "wall":    t(420, 760, 0.1, 0.45),
            "double":  t(520, 1100, 0.16, 0.45),
            "crack":   t(0, 0, 0.1, 0.35, "noise", 3),
            "deny":    t(190, 170, 0.2, 0.4, "square", 1),
            "ui":      t(700, 700, 0.04, 0.3),
            "select":  t(520, 800, 0.1, 0.35),
        }
        for k, v in d.items():
            self.sounds[k] = self._mk(v)

    def _music_layer(self, world, level):
        sr = self.sr
        hz = lambda m: 440.0 * 2 ** ((m - 69) / 12.0)
        progressions = {
            0: ([[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 59], [55, 59, 62, 65]], "piano"),
            1: ([[50, 57, 62, 65], [47, 54, 59, 62], [55, 59, 62, 67], [52, 57, 61, 64]], "ambient"),
            2: ([[40, 47, 52, 55], [36, 43, 48, 51], [43, 50, 55, 58], [38, 45, 50, 53]], "pulse"),
            3: ([[54, 61, 66, 69], [50, 57, 62, 65], [52, 59, 64, 67], [49, 56, 61, 64]], "orch"),
            4: ([[45, 52, 57, 64], [41, 48, 53, 60], [48, 55, 60, 67], [43, 50, 55, 62]], "cine"),
        }[world]
        chords, style = progressions
        cl = 2.5
        L = int(sr * cl)
        n = L * len(chords)
        buf = [0.0] * n
        rng = random.Random(world * 1000 + level)

        def add(start, seg, gain=1.0):
            for j, v in enumerate(seg):
                buf[(start + j) % n] += v * gain

        def pad(f, amp, harm=0.3):
            dur_n = int(sr * cl)
            env = self._adsr(dur_n, a=0.5, d=0.3, s=0.8, r=0.4)
            raw = self._detune_osc(f, dur_n, "sine", spread=0.006, voices=3)
            h2 = self._detune_osc(f * 2, dur_n, "sine", spread=0.004, voices=2)
            return [(raw[i] + h2[i] * harm) * amp * env[i] for i in range(dur_n)]

        def pluck(f, dur, amp, decay=3.0):
            dur_n = int(sr * dur)
            env = [math.exp(-decay * i / sr) for i in range(dur_n)]
            raw = self._detune_osc(f, dur_n, "tri", spread=0.004, voices=2)
            return [raw[i] * amp * env[i] for i in range(dur_n)]

        def bass(f, dur, amp):
            dur_n = int(sr * dur)
            env = self._adsr(dur_n, a=0.02, d=0.1, s=0.6, r=0.1)
            raw = self._detune_osc(f, dur_n, "sine", spread=0.002, voices=2)
            lp = self._lowpass(raw, 400)
            return [lp[i] * amp * env[i] for i in range(dur_n)]

        def kick(amp=0.8):
            dur_n = int(sr * 0.15)
            out = []; ph = 0.0
            for i in range(dur_n):
                f = 90 * math.exp(-20 * i / sr) + 40
                ph += 2 * math.pi * f / sr
                out.append(math.sin(ph) * amp * math.exp(-30 * i / sr))
            return out

        def hat(amp=0.3):
            dur_n = int(sr * 0.05)
            return [rng.uniform(-1, 1) * amp * math.exp(-80 * i / sr) for i in range(dur_n)]

        def snare(amp=0.4):
            dur_n = int(sr * 0.12)
            out = []
            for i in range(dur_n):
                x = i / sr
                env = math.exp(-25 * x)
                out.append((rng.uniform(-1, 1) * 0.6 + math.sin(2 * math.pi * 180 * x) * 0.4) * amp * env)
            return out

        for ci, ch in enumerate(chords):
            s0 = ci * L
            for f in ch:
                add(s0, pad(hz(f - 12), 0.075, 0.25))
            add(s0, bass(hz(ch[0] - 24), cl * 0.9, 0.18))
            if style in ("piano", "orch", "cine"):
                for k in range(3):
                    note = ch[(ci + k) % len(ch)] + 12
                    add(s0 + int(k * 0.75 * sr), pluck(hz(note), 1.4, 0.10, 2.5))

        if level >= 1:
            for ci, ch in enumerate(chords):
                s0 = ci * L
                notes = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 12]
                for k, note in enumerate(notes):
                    add(s0 + int(k * 0.55 * sr), pluck(hz(note), 0.9, 0.14, 3.5))
                if style == "pulse":
                    for k in range(10):
                        add(s0 + int(k * 0.25 * sr), hat(0.20))
                else:
                    for k in range(5):
                        add(s0 + int(k * 0.5 * sr), hat(0.15))
                if style in ("pulse", "orch", "cine"):
                    add(s0, kick(0.55))
                    add(s0 + int(cl * 0.5 * sr), kick(0.45))

        if level >= 2:
            for ci, ch in enumerate(chords):
                s0 = ci * L
                for f in ch:
                    add(s0, pad(hz(f + 12), 0.06, 0.4))
                add(s0, bass(hz(ch[0] - 24), cl * 0.4, 0.20))
                add(s0 + int(cl * 0.5 * sr), snare(0.35))
                if style in ("pulse", "cine"):
                    add(s0 + int(cl * 0.75 * sr), snare(0.25))
                for k in range(16):
                    add(s0 + int(k * 0.15625 * sr), hat(0.12))
                add(s0 + int(cl * 0.25 * sr), pluck(hz(ch[-1] + 24), 1.2, 0.08, 2.0))

        buf = self._reverb(buf, wet=0.22)
        peak = max(1e-6, max(abs(v) for v in buf))
        return [v * (0.55 / peak) for v in buf]

    def music(self, world):
        if not self.ok or world == self.music_world:
            return
        try:
            layers = []
            for lvl in range(3):
                key = (world, lvl)
                snd = self.music_cache.get(key)
                if snd is None:
                    snd = self._mk(self._music_layer(world, lvl))
                    self.music_cache[key] = snd
                layers.append(snd)
            for i, ch in enumerate(self.music_layer_ch):
                ch.stop()
                ch.set_volume(0)
                ch.play(layers[i], loops=-1, fade_ms=1400)
            self.music_world = world
            self.intensity = 0.0
            self.target_intensity = 0.0
            self._apply_layer_volumes()
        except Exception:
            self.ok = False

    def _apply_layer_volumes(self):
        if not self.ok:
            return
        i = clamp(self.intensity, 0, 2)
        if i <= 1:
            vols = [1.0 - i, i, 0.0]
        else:
            vols = [0.0, 2.0 - i, i - 1.0]
        for ch, v in zip(self.music_layer_ch, vols):
            ch.set_volume(v * self.s["music"])

    def set_intensity(self, x):
        self.target_intensity = clamp(x, 0, 2)

    def update(self, dt):
        if not self.ok:
            return
        self.intensity += (self.target_intensity - self.intensity) * min(1.0, dt * 2.5)
        self._apply_layer_volumes()

    def stop_music(self):
        if self.ok:
            for ch in self.music_layer_ch:
                ch.fadeout(600)
        self.music_world = None

    def volumes(self):
        self._apply_layer_volumes()

    def play(self, name, vol=1.0):
        if not self.ok:
            return
        snd = self.sounds.get(name)
        if snd:
            snd.set_volume(clamp(self.s["sfx"] * vol, 0, 1))
            snd.play()


# ----------------------------------------------------------------- save
def default_save():
    return {
        "unlocked": 1,
        "abilities": [],
        "best": {},
        "cores": [],
        "run": None,
        "energy_bank": 0,
        "skins": ["default"],
        "skin": "default",
        "settings": {"music": 0.6, "sfx": 0.8, "shake": True},
    }


def load_save():
    s = default_save()
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
        for k in s:
            if k in data:
                if isinstance(s[k], dict) and isinstance(data[k], dict) and k == "settings":
                    s[k].update(data[k])
                else:
                    s[k] = data[k]
    except Exception:
        pass
    if "default" not in s["skins"]:
        s["skins"].insert(0, "default")
    return s


def write_save(s):
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(s, f)
    except Exception:
        pass


# ----------------------------------------------------------------- level entities
class Plat:
    def __init__(self, x, y, w, h, kind="normal", move=None, phase=0.0, cyc=None):
        self.rect = Rect(x, y, w, h)
        self.kind = kind
        self.base = (x, y)
        self.move = move
        self.phase = phase
        self.delta = (0, 0)
        self.state = "idle"
        self.timer = 0.0
        self.cyc = cyc or (2.0, 1.2, 0.0)
        self.vis = True
        self.warn = False
        self.pulse = 0.0
        self.used = False

    @property
    def solid(self):
        if self.kind == "fragile":
            return self.state != "gone"
        if self.kind == "ghost":
            return self.vis
        return True

    def update(self, t, dt, prect):
        if self.move:
            ax, ay, per = self.move
            s = math.sin(2 * math.pi * t / per + self.phase)
            nx = self.base[0] + int(round(ax * s))
            ny = self.base[1] + int(round(ay * s))
            self.delta = (nx - self.rect.x, ny - self.rect.y)
            self.rect.topleft = (nx, ny)
        else:
            self.delta = (0, 0)
        if self.kind == "fragile":
            if self.state == "crumble":
                self.timer -= dt
                if self.timer <= 0:
                    self.state, self.timer = "gone", 2.6
            elif self.state == "gone":
                self.timer -= dt
                if self.timer <= 0 and not self.rect.colliderect(prect):
                    self.state = "idle"
        elif self.kind == "ghost":
            on, off, o = self.cyc
            c = (t + o) % (on + off)
            self.vis = c < on
            self.warn = self.vis and c > on - 0.55
        if self.pulse > 0:
            self.pulse = max(0.0, self.pulse - dt * 3)


class Spike:
    def __init__(self, x, y, n):
        self.x, self.y, self.n = x, y, n
        self.hit = Rect(x + 3, y - 15, n * 18 - 6, 14)


class Rotor:
    def __init__(self, x, y, L, speed, phase=0.0):
        self.x, self.y, self.L, self.speed, self.phase = x, y, L, speed, phase

    def angle(self, t):
        return self.phase + self.speed * t

    def hits(self, t, cx, cy, r):
        a = self.angle(t)
        dx, dy = math.cos(a), math.sin(a)
        px, py = cx - self.x, cy - self.y
        proj = clamp(px * dx + py * dy, -self.L, self.L)
        qx, qy = dx * proj, dy * proj
        return (px - qx) ** 2 + (py - qy) ** 2 < (r + 6) ** 2


class Barrier:
    def __init__(self, x, y, h, on, off, phase):
        self.x, self.y, self.h, self.on, self.off, self.phase = x, y, h, on, off, phase
        self.rect = Rect(x - 5, y + 8, 10, h - 16)

    def cyc(self, t):
        return (t + self.phase) % (self.on + self.off)

    def active(self, t):
        return self.cyc(t) < self.on

    def warning(self, t):
        c = self.cyc(t)
        return c >= self.on + self.off - 0.4


class Wind:
    def __init__(self, x, y, w, h, ax, ay):
        self.rect = Rect(x, y, w, h)
        self.ax, self.ay = ax, ay


class Station:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.active = False
        self.rect = Rect(x - 22, y - 54, 44, 54)
        self.flash = 0.0


class Shrine:
    def __init__(self, x, y, ability):
        self.x, self.y, self.ability = x, y, ability
        self.need = 0
        self.active = False


class Exit:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.rect = Rect(x - 30, y - 90, 60, 90)


class Item:
    def __init__(self, kind, x, y, iid):
        self.kind, self.x, self.y, self.id = kind, x, y, iid
        self.value = 5 if kind == "crystal" else 1
        self.r = 12 if kind == "crystal" else 8
        self.got = False
        self.ph = (iid * 0.77) % 6.28


class Sign:
    def __init__(self, x, y, text):
        self.x, self.y, self.text = x, y, text


# ----------------------------------------------------------------- level builder
class Builder:
    CHECK = DEBUG or bool(os.environ.get("REBOUND_CHECK"))

    def __init__(self, world, start_y, abil):
        self.world = world
        self.plats, self.spikes, self.rotors, self.barriers = [], [], [], []
        self.winds, self.items, self.stations, self.signs = [], [], [], []
        self.shrine_obj = None
        self.exit_obj = None
        self.x, self.y = 0, start_y
        self.abil = set(abil)
        self.last = None
        self.start = None

    def _limits(self, prev, gap):
        k = prev.kind
        if k == "spring":
            mg, mr = 230, 190
        elif k == "power":
            mg, mr = 270, 380
        else:
            mg, mr = 175, 105
            if "power" in self.abil and gap <= 140:
                mr = 270
            if "double" in self.abil:
                mg, mr = max(mg, 300), max(mr, 210)
            if "dash" in self.abil:
                mg = max(mg, 255)
            if "double" in self.abil and "dash" in self.abil:
                mg = 330
        return mg, mr

    def _iid(self):
        return len(self.items)

    def p(self, w, gap=0, dy=0, kind="normal", h=28, move=None, f=None, ok=None, phase=0.0,
          cyc=None, top=0):
        prev = self.last
        x, y = self.x + gap, self.y + dy
        if prev is not None and Builder.CHECK:
            axp, ayp = (prev.move[0], prev.move[1]) if prev.move else (0, 0)
            axn, ayn = (move[0], move[1]) if move else (0, 0)
            eg = gap - axp - axn
            red = ayp + ayn
            edy = 0 if abs(dy) <= red else (dy - red if dy > 0 else dy + red)
            mg, mr = self._limits(prev, eg)
            if ok:
                if isinstance(ok, tuple):
                    mg, mr = max(mg, ok[0]), max(mr, ok[1])
                else:
                    mg = max(mg, ok)
            if dy > 0 or edy > 0:
                mg += min(max(edy, 0) * 0.6, 90)
            static = not move and not prev.move
            assert eg >= 20 or (static and gap >= 0), "L%d plat@%d: gap too small (%s)" % (self.world + 1, x, eg)
            assert eg <= mg, "L%d plat@%d: gap %s > reach %s" % (self.world + 1, x, eg, mg)
            assert -edy <= mr, "L%d plat@%d: rise %s > reach %s" % (self.world + 1, x, -edy, mr)
        pl = Plat(x, y, w, h, kind, move, phase, cyc)
        if f is None:
            f = 3 if (gap >= 90 and prev is not None) else 0
        for i in range(f):
            t = (i + 1) / (f + 1)
            fx = lerp(self.x, x, t)
            fy = lerp(self.y, y, t) - 26 - 50 * math.sin(math.pi * t)
            self.items.append(Item("frag", fx, fy, self._iid()))
        for i in range(top):
            fx = x + w * (i + 1) / (top + 1)
            self.items.append(Item("frag", fx, y - 30, self._iid()))
        self.plats.append(pl)
        if self.start is None:
            self.start = (130, y)
        self.x, self.y = x + w, y
        self.last = pl
        return pl

    def _on(self, plat):
        return plat or self.last

    def spikes_on(self, off, n, plat=None):
        pl = self._on(plat)
        self.spikes.append(Spike(pl.rect.x + off, pl.rect.y, n))

    def station(self, off=None, plat=None):
        pl = self._on(plat)
        assert pl.kind == "normal" and not pl.move and pl.rect.w >= 140, "bad station platform"
        cx = pl.rect.centerx if off is None else pl.rect.x + off
        self.stations.append(Station(cx, pl.rect.y))

    def shrine(self, ability, off=None):
        pl = self.last
        assert pl.kind == "normal" and not pl.move and pl.rect.w >= 200
        cx = pl.rect.centerx if off is None else pl.rect.x + off
        self.shrine_obj = Shrine(cx, pl.rect.y, ability)
        self.abil.add(ability)

    def exit(self, off=None):
        pl = self.last
        assert pl.kind == "normal" and pl.rect.w >= 200
        cx = pl.rect.centerx if off is None else pl.rect.x + off
        self.exit_obj = Exit(cx, pl.rect.y)

    def sign(self, text, off=None, up=95, plat=None):
        pl = self._on(plat)
        x = pl.rect.x + (pl.rect.w // 2 if off is None else off)
        self.signs.append(Sign(x, pl.rect.y - up, text))

    def crystal(self, dx, up, plat=None):
        pl = self._on(plat)
        self.items.append(Item("crystal", pl.rect.centerx + dx, pl.rect.y - up, self._iid()))

    def crystal_abs(self, x, y):
        self.items.append(Item("crystal", x, y, self._iid()))

    def frag_abs(self, x, y):
        self.items.append(Item("frag", x, y, self._iid()))

    def rotor(self, dx, up, L, speed, phase=0.0, plat=None):
        pl = self._on(plat)
        self.rotors.append(Rotor(pl.rect.centerx + dx, pl.rect.y - up, L, speed, phase))

    def barrier(self, off, height, on, off_t, phase=0.0, plat=None):
        pl = self._on(plat)
        self.barriers.append(Barrier(pl.rect.x + off, pl.rect.y - height, height, on, off_t, phase))

    def wind(self, x, y, w, h, ax, ay):
        self.winds.append(Wind(x, y, w, h, ax, ay))

    def shaft(self, gap, height=470, inner=150, dy=0):
        assert "wall" in self.abil
        floor_w = 80 + 28 + inner + 28
        floor = self.p(floor_w, gap=gap, dy=dy, f=0)
        yf = floor.rect.y
        lx = floor.rect.x + 80
        rx = lx + 28 + inner
        ytop = yf - height
        left = Plat(lx, ytop - 60, 28, height - 30, "wall")
        right = Plat(rx, ytop, 28, height, "wall")
        ledge = Plat(rx + 28, ytop, 190, 28, "normal")
        self.plats += [left, right, ledge]
        cxm = lx + 28 + inner / 2
        for i in range(1, 5):
            self.items.append(Item("frag", cxm + (45 if i % 2 else -45), yf - 40 - i * (height - 140) / 4,
                                   self._iid()))
        self.x, self.y, self.last = rx + 28 + 190, ytop, ledge
        return ledge, cxm, ytop

    def finish(self, frac):
        assert self.exit_obj is not None, "level has no exit"
        return Level(self, frac)


class Level:
    def __init__(self, b, frac):
        self.world = b.world
        self.theme = THEMES[b.world]
        self.plats, self.spikes, self.rotors = b.plats, b.spikes, b.rotors
        self.barriers, self.winds, self.items = b.barriers, b.winds, b.items
        self.stations, self.signs = b.stations, b.signs
        self.shrine = b.shrine_obj
        self.exit = b.exit_obj
        self.start = b.start
        self.movers = [p for p in self.plats if p.move]
        self.width = max(p.rect.right + (abs(p.move[0]) if p.move else 0) for p in self.plats) + 360
        self.min_y = min(p.rect.top - (abs(p.move[1]) if p.move else 0) for p in self.plats)
        self.max_y = max(p.rect.bottom + (abs(p.move[1]) if p.move else 0) for p in self.plats)
        self.kill_y = self.max_y + 420
        self.total = sum(i.value for i in self.items)
        self.need = max(1, int(round(frac * self.total)))
        self.crystals = sum(1 for i in self.items if i.kind == "crystal")
        if self.shrine:
            before = sum(i.value for i in self.items if i.x < self.shrine.x)
            self.shrine.need = int(clamp(math.ceil(0.4 * before), 2, 9))

    def update(self, t, dt, prect):
        for p in self.plats:
            p.update(t, dt, prect)

    def draw(self, surf, cam, t, sc):
        cx, cy = int(cam[0]), int(cam[1])
        P = sc.p
        for w in self.winds:
            self.draw_wind(surf, w, cx, cy, t)
        for p in self.plats:
            self.draw_plat(surf, p, cx, cy, t)
        for s in self.spikes:
            x0 = s.x - cx
            if -80 < x0 < W + 80 and -60 < s.y - cy < H + 60:
                for i in range(s.n):
                    xs = x0 + i * 18
                    ys = s.y - cy
                    pygame.draw.polygon(surf, (235, 70, 90), [(xs, ys), (xs + 9, ys - 18), (xs + 18, ys)])
                    pygame.draw.polygon(surf, (255, 170, 170), [(xs + 9, ys - 18), (xs + 14, ys - 5), (xs + 9, ys)])
                add_glow(surf, (x0 + s.n * 9, s.y - cy - 8), 30 + 6 * s.n, (60, 8, 14))
        for b in self.barriers:
            self.draw_barrier(surf, b, cx, cy, t)
        for r in self.rotors:
            self.draw_rotor(surf, r, cx, cy, t)
        for st in self.stations:
            self.draw_station(surf, st, cx, cy, t)
        if self.shrine:
            self.draw_shrine(surf, self.shrine, cx, cy, t, sc)
        self.draw_exit(surf, cx, cy, t, sc)
        for it in self.items:
            if not it.got:
                self.draw_item(surf, it, cx, cy, t)
        for sg in self.signs:
            d = abs(P.x - sg.x)
            if d < 380:
                a = int(255 * clamp(1 - (d - 220) / 160, 0, 1))
                f = sc.g.fonts["s"]
                lines = wrap_text(f, sg.text, 300)
                hh = len(lines) * 22 + 12
                ww = max(f.size(l)[0] for l in lines) + 24
                r = Rect(0, 0, ww, hh)
                r.midbottom = (int(sg.x - cx), int(sg.y - cy))
                if a > 0:
                    panel(surf, r, (6, 10, 26), int(a * 0.55), 10)
                    for i, l in enumerate(lines):
                        draw_text(surf, l, f, (220, 235, 255), (r.centerx, r.y + 17 + i * 22), alpha=a)

    def draw_wind(self, surf, w, cx, cy, t):
        r = w.rect.move(-cx, -cy)
        if r.right < 0 or r.left > W or r.bottom < 0 or r.top > H:
            return
        col = shade(self.theme["accent"], -70)
        pygame.draw.rect(surf, shade(col, -40), r, 1, border_radius=8)
        n = max(5, (w.rect.w * w.rect.h) // 3500)
        for k in range(n):
            u = (k * 0.618 + t * 0.35 * (1 if w.ax >= 0 else -1) * (1 if w.ax else 0.0)) % 1.0
            v = (k * 0.381 + t * 0.7 * (1 if w.ay > 0 else -1) * (1 if w.ay else 0.0)) % 1.0
            if w.ax:
                x = r.x + (u if w.ax > 0 else 1 - u) * r.w
                y = r.y + ((k * 0.379) % 1.0) * r.h
                pygame.draw.line(surf, col, (x, y), (x + (22 if w.ax > 0 else -22), y), 2)
            else:
                y = r.y + v * r.h
                x = r.x + ((k * 0.379) % 1.0) * r.w
                pygame.draw.line(surf, col, (x, y), (x, y + (22 if w.ay > 0 else -22)), 2)

    def draw_plat(self, surf, p, cx, cy, t):
        th = self.theme
        r = p.rect.move(-cx, -cy)
        if r.right < -40 or r.left > W + 40 or r.bottom < -80 or r.top > H + 80:
            return
        k = p.kind
        body, top = th["body"], th["top"]
        if k == "ghost":
            if not p.vis:
                pygame.draw.rect(surf, shade(top, -90), r, 1, border_radius=6)
                return
            if p.warn and int(t * 12) % 2 == 0:
                pygame.draw.rect(surf, shade(top, -60), r, 2, border_radius=6)
                return
            body, top = shade(body, 30), mixc(top, (255, 255, 255), 0.3)
        if k == "fragile":
            if p.state == "gone":
                return
            if p.state == "crumble":
                r = r.move(random.randint(-2, 2), 0)
            body, top = (118, 92, 78), (190, 150, 110)
        if k == "ice":
            body, top = shade(th["body"], 30), (225, 248, 255)
        if k == "wall":
            pygame.draw.rect(surf, body, r, border_radius=5)
            pygame.draw.rect(surf, shade(body, 22), (r.x, r.y, 5, r.h), border_radius=3)
            pygame.draw.rect(surf, shade(body, -22), (r.right - 6, r.y, 6, r.h), border_radius=3)
            for yy in range(r.y + 20, r.bottom - 6, 34):
                pygame.draw.line(surf, shade(body, -30), (r.x + 4, yy), (r.right - 5, yy), 2)
            pygame.draw.rect(surf, top, (r.x, r.y, r.w, 5), border_radius=3)
            return
        if r.h <= 40 and r.w >= 90 and k in ("normal", "ice", "fragile", "ghost"):
            pygame.draw.polygon(surf, shade(body, -26),
                                [(r.x + 10, r.bottom - 2), (r.right - 10, r.bottom - 2),
                                 (r.centerx + 14, r.bottom + 24), (r.centerx - 14, r.bottom + 24)])
        pygame.draw.rect(surf, body, r, border_radius=7)
        pygame.draw.rect(surf, top, (r.x, r.y, r.w, 8), border_top_left_radius=7, border_top_right_radius=7)
        pygame.draw.line(surf, shade(top, 40), (r.x + 6, r.y + 1), (r.right - 6, r.y + 1), 1)
        if k == "ice":
            for i in range(3):
                x = r.x + 14 + i * (r.w - 28) / 2.5
                pygame.draw.line(surf, (255, 255, 255), (x, r.y + 3), (x + 10, r.y + 3), 1)
        if k == "fragile":
            pygame.draw.line(surf, (70, 50, 40), (r.x + r.w * 0.3, r.y + 3), (r.x + r.w * 0.45, r.bottom - 3), 2)
            pygame.draw.line(surf, (70, 50, 40), (r.x + r.w * 0.7, r.y + 3), (r.x + r.w * 0.58, r.bottom - 3), 2)
        if k == "spring":
            sq = 1 - 0.45 * p.pulse
            if self.world == 1:
                cap = Rect(0, 0, r.w + 14, int(30 * sq))
                cap.midbottom = (r.centerx, r.y + 6)
                pygame.draw.rect(surf, (200, 190, 170), (r.centerx - 8, r.y, 16, r.h))
                pygame.draw.ellipse(surf, (226, 70, 120), cap.inflate(0, 12))
                for dx in (-0.28, 0.05, 0.3):
                    pygame.draw.circle(surf, (255, 230, 240), (int(cap.centerx + dx * cap.w), cap.centery - 2), 4)
                add_glow(surf, (r.centerx, r.y - 8), 40, (50, 10, 25))
            else:
                pad = Rect(r.x + 6, r.y - int(8 * sq), r.w - 12, int(10 * sq) + 2)
                for i in range(4):
                    x = r.x + 12 + i * (r.w - 24) / 3
                    pygame.draw.line(surf, (200, 200, 220), (x, r.y + 2), (x + 6, r.y - int(6 * sq)), 2)
                pygame.draw.rect(surf, (255, 220, 70), pad, border_radius=5)
                add_glow(surf, (r.centerx, r.y - 4), 44, (60, 50, 8))
        if k == "power":
            pad = Rect(r.x + 4, r.y - 10, r.w - 8, 12)
            pygame.draw.rect(surf, (255, 70, 200), pad, border_radius=5)
            for i in range(3):
                x = r.x + r.w * (i + 1) / 4
                yy = r.y - 4 - int(((t * 2 + i * 0.3) % 1) * 22)
                pygame.draw.polygon(surf, (255, 190, 240), [(x - 6, yy), (x, yy - 8), (x + 6, yy)], 2)
            add_glow(surf, (r.centerx, r.y - 6), 64, (90, 14, 70))
        if k == "energy":
            col = (60, 130, 160) if p.used else (70, 240, 255)
            pygame.draw.rect(surf, col, (r.x + 4, r.y - 6, r.w - 8, 8), border_radius=4)
            add_glow(surf, (r.centerx, r.y - 2), 50, shade(col, -120))
        if p.move:
            pygame.draw.circle(surf, th["accent"], (r.x + 8, r.centery), 3)
            pygame.draw.circle(surf, th["accent"], (r.right - 8, r.centery), 3)

    def draw_barrier(self, surf, b, cx, cy, t):
        x, y = b.x - cx, b.y - cy
        if x < -40 or x > W + 40:
            return
        on = b.active(t)
        warn = b.warning(t)
        col = (255, 70, 110)
        pygame.draw.rect(surf, (70, 70, 90), (x - 10, y, 20, 10), border_radius=3)
        pygame.draw.rect(surf, (70, 70, 90), (x - 10, y + b.h - 10, 20, 10), border_radius=3)
        if on:
            jx = random.randint(-2, 2)
            pygame.draw.line(surf, col, (x + jx, y + 10), (x - jx, y + b.h - 10), 4)
            pygame.draw.line(surf, (255, 220, 230), (x, y + 10), (x, y + b.h - 10), 1)
            add_glow(surf, (x, y + b.h / 2), 70, (90, 14, 30))
        else:
            c = (160, 90, 110) if warn and int(t * 14) % 2 == 0 else (60, 50, 70)
            for yy in range(int(y + 14), int(y + b.h - 10), 14):
                pygame.draw.line(surf, c, (x, yy), (x, yy + 4), 2)

    def draw_rotor(self, surf, r, cx, cy, t):
        x, y = r.x - cx, r.y - cy
        if x < -150 or x > W + 150:
            return
        a = r.angle(t)
        dx, dy = math.cos(a) * r.L, math.sin(a) * r.L
        pygame.draw.line(surf, (110, 110, 130), (x - dx, y - dy), (x + dx, y + dy), 6)
        pygame.draw.line(surf, (190, 190, 210), (x - dx, y - dy), (x + dx, y + dy), 2)
        for sgn in (-1, 1):
            ex, ey = x + dx * sgn, y + dy * sgn
            pygame.draw.circle(surf, (235, 70, 90), (int(ex), int(ey)), 10)
            pygame.draw.circle(surf, (255, 190, 190), (int(ex), int(ey)), 4)
            add_glow(surf, (ex, ey), 30, (80, 10, 20))
        pygame.draw.circle(surf, (70, 70, 90), (int(x), int(y)), 10)
        pygame.draw.circle(surf, self.theme["accent"], (int(x), int(y)), 4)

    def draw_station(self, surf, st, cx, cy, t):
        x, y = st.x - cx, st.y - cy
        if x < -60 or x > W + 60:
            return
        col = self.theme["accent"] if st.active else (90, 100, 120)
        pygame.draw.rect(surf, (60, 66, 90), (x - 16, y - 8, 32, 8), border_radius=3)
        pygame.draw.rect(surf, shade(col, -60), (x - 4, y - 36, 8, 30), border_radius=3)
        bob = math.sin(t * 3 + st.x) * 3
        rad = 13 + (3 * math.sin(t * 5) if st.active else 0)
        pygame.draw.circle(surf, col, (int(x), int(y - 46 + bob)), int(rad), 3)
        pygame.draw.circle(surf, mixc(col, (255, 255, 255), 0.5 if st.active else 0.1),
                           (int(x), int(y - 46 + bob)), 5)
        if st.active:
            add_glow(surf, (x, y - 46 + bob), 60, shade(col, -150))
        if st.flash > 0:
            add_glow(surf, (x, y - 46), int(60 + 120 * (1 - st.flash)), mixc((0, 0, 0), col, st.flash))

    def draw_shrine(self, surf, sh, cx, cy, t, sc):
        x, y = sh.x - cx, sh.y - cy
        if x < -80 or x > W + 80:
            return
        col = self.theme["accent"] if sh.active else (200, 170, 90)
        pygame.draw.polygon(surf, (70, 74, 100), [(x - 28, y), (x - 18, y - 30), (x + 18, y - 30), (x + 28, y)])
        pygame.draw.rect(surf, (90, 96, 130), (x - 20, y - 36, 40, 8), border_radius=3)
        bob = math.sin(t * 2.2) * 5
        pygame.draw.circle(surf, col, (int(x), int(y - 66 + bob)), 20, 3)
        label = {"wall": "WALL", "power": "SLAM", "double": "x2", "dash": ">>"}[sh.ability]
        draw_text(surf, label, sc.g.fonts["s"], col, (x, y - 66 + bob))
        add_glow(surf, (x, y - 66 + bob), 80 if sh.active else 60, shade(col, -150))

    def draw_exit(self, surf, cx, cy, t, sc):
        e = self.exit
        x, y = e.x - cx, e.y - cy
        if x < -100 or x > W + 100:
            return
        ready = sc.energy >= self.need
        col = self.theme["accent"] if ready else (150, 90, 100)
        pygame.draw.rect(surf, (74, 78, 104), (x - 36, y - 100, 12, 100), border_radius=4)
        pygame.draw.rect(surf, (74, 78, 104), (x + 24, y - 100, 12, 100), border_radius=4)
        pygame.draw.rect(surf, (96, 102, 134), (x - 40, y - 108, 80, 12), border_radius=5)
        n = 8 if ready else 3
        for i in range(n):
            a = t * (2 if ready else 0.6) + i * 6.283 / n
            px = x + math.cos(a) * 18 * (0.6 + 0.4 * math.sin(t + i))
            py = y - 52 + math.sin(a) * 38
            pygame.draw.circle(surf, col, (int(px), int(py)), 3)
        add_glow(surf, (x, y - 52), 84 if ready else 40, shade(col, -130))
        txt = "RESTORE" if ready else "NEED %d ENERGY" % (self.need - sc.energy)
        draw_text(surf, txt, sc.g.fonts["xs"], col, (x, y - 122))

    def draw_item(self, surf, it, cx, cy, t):
        x = it.x - cx
        y = it.y - cy + math.sin(t * 2.5 + it.ph) * 3
        if x < -30 or x > W + 30 or y < -30 or y > H + 30:
            return
        col = self.theme["accent"] if it.kind == "frag" else (230, 120, 255)
        if it.kind == "frag":
            w = 3 + 5 * abs(math.cos(t * 3 + it.ph))
            pts = [(x, y - 9), (x + w, y), (x, y + 9), (x - w, y)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, (235, 255, 255), pts, 1)
            add_glow(surf, (x, y), 20, shade(col, -140))
        else:
            w = 6 + 6 * abs(math.cos(t * 2 + it.ph))
            pts = [(x, y - 15), (x + w, y - 5), (x + w, y + 7), (x, y + 15), (x - w, y + 7), (x - w, y - 5)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, (255, 235, 255), pts, 2)
            add_glow(surf, (x, y), 36, (90, 30, 110))


# ----------------------------------------------------------------- levels
def build_level(idx, check=None):
    prev = Builder.CHECK
    if check is not None:
        Builder.CHECK = check
    try:
        return [level1, level2, level3, level4, level5][idx]()
    finally:
        Builder.CHECK = prev


def level1():
    b = Builder(0, 340, [])
    b.p(440)
    b.sign("A / D or Left / Right to move", 90)
    b.sign("SPACE bounces. Hold it for a higher hop.", 330)
    b.p(150, gap=100)
    b.p(150, gap=120, dy=-40)
    b.p(260, gap=120, dy=-30, top=2)
    b.spikes_on(110, 2)
    b.sign("Spikes hurt. Hop over them!", 70)
    b.p(170, gap=130, dy=30)
    b.station()
    b.sign("Rebound Stations save your progress.", 85)
    b.p(110, gap=150, kind="spring")
    b.crystal(0, 205)
    b.sign("Springs bounce you automatically.", 55)
    b.p(190, gap=150, dy=-150, f=3)
    b.sign("Fragile platforms crumble. Keep moving!", 95)
    b.p(100, gap=110, kind="fragile")
    b.p(100, gap=90, kind="fragile")
    b.p(100, gap=90, kind="fragile")
    b.p(250, gap=110, dy=-20, top=2)
    b.station()
    b.p(120, gap=180, move=(80, 0, 3.6))
    b.p(120, gap=190, dy=-30, move=(0, 60, 3.0))
    b.p(320, gap=150, dy=-20)
    b.station(off=40)
    b.spikes_on(130, 2)
    b.spikes_on(220, 2)
    b.p(150, gap=140, dy=-40)
    b.p(130, gap=130, dy=-40)
    b.crystal(0, 70)
    b.p(110, gap=150, kind="spring")
    b.p(280, gap=160, dy=-170)
    b.sign("Falling is not the end.", 140)
    b.exit()
    return b.finish(0.35)


def level2():
    b = Builder(1, 400, ["bounce"])
    b.p(380)
    b.sign("Mushrooms are bouncy. The forest hides secrets.", 110)
    b.p(110, gap=130, dy=-10, kind="spring")
    b.crystal(0, 205)
    b.p(200, gap=140, dy=-130, top=2)
    b.p(130, gap=130, dy=-40, move=(0, 70, 3.4))
    b.p(150, gap=140)
    b.p(260, gap=130, dy=30, top=2)
    b.station()
    b.p(100, gap=150, kind="spring")
    b.p(120, gap=190, dy=-150)
    b.p(120, gap=150, move=(90, 0, 3.8))
    b.p(300, gap=170, dy=-10)
    b.station(off=50)
    b.shrine("wall", off=200)
    b.sign("Collect energy, then press E at the shrine.", 120, up=130)
    b.p(110, gap=130, kind="spring")
    b.p(190, gap=140, dy=-100)
    ledge, cxm, ytop = b.shaft(gap=120, height=470)
    b.crystal_abs(cxm, ytop + 30)
    b.sign("Wall Rebound: press SPACE against a wall, then hop to the other.", 60, up=110)
    b.p(260, gap=130, dy=0, top=2)
    b.station()
    b.p(100, gap=150, kind="spring")
    b.p(120, gap=170, dy=-110, move=(80, 0, 3.4))
    b.p(100, gap=150, dy=-20, move=(0, 80, 3.0))
    b.p(300, gap=140, dy=10, top=2)
    b.station(off=60)
    b.spikes_on(150, 3)
    b.p(100, gap=150, kind="spring")
    b.crystal(0, 215)
    b.p(280, gap=170, dy=-120)
    b.exit()
    return b.finish(0.4)


def level3():
    b = Builder(2, 400, ["bounce", "wall"])
    b.p(360)
    b.sign("Machines never sleep. Mind the timing.", 110)
    b.p(160, gap=130, dy=-30, move=(0, 60, 3.0))
    b.p(260, gap=140, top=2)
    b.rotor(0, 70, 70, 1.5)
    b.p(200, gap=130, dy=20)
    b.station()
    b.p(110, gap=150, kind="power")
    b.sign("Power platforms launch you very high.", 55, up=60)
    b.p(180, gap=170, dy=-330, top=2)
    b.crystal(-120, 120)
    b.p(200, gap=140)
    b.p(120, gap=150, dy=-30, kind="ghost", cyc=(2.2, 1.2, 0.0))
    b.p(120, gap=120, kind="ghost", cyc=(2.2, 1.2, 0.9))
    b.p(120, gap=120, kind="ghost", cyc=(2.2, 1.2, 1.8))
    b.p(320, gap=130, dy=-10)
    b.station(off=40)
    b.shrine("power", off=220)
    b.p(180, gap=140, dy=-15, top=1)
    b.sign("Slam: press S in mid-air, then land for a huge rebound.", 90, up=100)
    b.p(140, gap=100, dy=-270)
    b.p(130, gap=140, dy=10, move=(80, 0, 3.2))
    b.p(300, gap=170, dy=0)
    b.rotor(-70, 70, 70, 1.7)
    b.rotor(80, 70, 70, -1.7)
    b.p(200, gap=140, dy=30)
    b.station()
    b.p(110, gap=150, kind="power")
    b.p(150, gap=170, dy=-300)
    b.crystal(0, 110)
    b.p(120, gap=140, dy=40, kind="ghost", cyc=(2.2, 1.2, 0.0))
    b.p(120, gap=120, kind="ghost", cyc=(2.2, 1.2, 0.9))
    b.p(300, gap=140, dy=10)
    b.spikes_on(100, 2)
    b.spikes_on(190, 2)
    b.p(300, gap=150, dy=-20)
    b.exit()
    return b.finish(0.4)


def level4():
    b = Builder(3, 400, ["bounce", "wall", "power"])
    b.p(380, kind="ice")
    b.sign("Ice is slippery. Plan your stops.", 110)
    b.p(150, gap=110, dy=-20, kind="ice")
    b.p(150, gap=130, dy=-20, kind="ice")
    b.p(260, gap=130, dy=20, kind="normal", top=2)
    b.station()
    b.p(120, gap=150, dy=-30, kind="ice", move=(70, 0, 3.4))
    b.p(140, gap=150, dy=-30, kind="ice")
    b.p(110, gap=130, kind="fragile")
    b.p(110, gap=100, kind="fragile")
    b.p(300, gap=120, dy=10)
    b.station(off=50)
    b.shrine("double", off=210)
    b.p(110, gap=290, dy=-20, kind="ice")
    b.sign("Double Bounce makes long gaps possible.", 55, up=60)
    b.p(110, gap=290, dy=0, kind="ice", f=3)
    b.p(260, gap=270, dy=-40)
    b.station(off=60)
    b.p(110, gap=220, dy=-190, kind="ice", ok=(300, 210))
    b.crystal(0, 90)
    b.p(110, gap=280, dy=-20, kind="ice")
    b.p(120, gap=250, dy=70, kind="ghost", cyc=(2.4, 1.2, 0.0))
    b.p(120, gap=200, kind="ghost", cyc=(2.4, 1.2, 1.0))
    b.p(120, gap=200, kind="ghost", cyc=(2.4, 1.2, 2.0))
    b.p(300, gap=250, dy=-40)
    b.station(off=40)
    b.spikes_on(130, 2)
    b.p(110, gap=300, dy=-30, kind="ice", move=(0, 80, 3.2))
    b.p(110, gap=270, dy=-40, kind="ice")
    b.p(110, gap=250, dy=60, kind="fragile")
    b.p(320, gap=200, dy=-20, kind="normal")
    b.exit()
    return b.finish(0.4)


def level5():
    b = Builder(4, 420, ["bounce", "wall", "power", "double"])
    b.p(380)
    b.sign("Everything you learned. One last climb.", 110)
    b.p(110, gap=140, kind="spring")
    b.p(150, gap=170, dy=-120, move=(70, 0, 3.4))
    b.p(300, gap=170, dy=-10, top=1)
    b.rotor(0, 72, 70, 1.6)
    b.station(off=40)
    b.p(110, gap=240, dy=20, kind="ghost", cyc=(2.4, 1.2, 0.0))
    b.p(110, gap=220, kind="ghost", cyc=(2.4, 1.2, 1.0))
    b.p(110, gap=220, kind="ghost", cyc=(2.4, 1.2, 2.0))
    b.p(320, gap=220, dy=-20)
    b.barrier(160, 320, 1.4, 1.8, 0.0)
    b.p(110, gap=140, kind="power")
    b.p(150, gap=170, dy=-330)
    b.crystal(0, 100)
    b.p(300, gap=140, dy=40)
    b.station(off=50)
    b.shrine("dash", off=220)
    b.sign("Shift = Energy Dash. Cross gaps in a flash.", 120, up=130)
    b.p(110, gap=250, dy=0, kind="ice")
    b.p(110, gap=300, dy=-30, kind="ice")
    b.p(110, gap=300, dy=40, kind="fragile")
    b.p(300, gap=300, dy=0)
    b.station(off=40)
    b.p(150, gap=130, dy=0, move=(0, 90, 2.8))
    b.p(160, gap=150, dy=-60)
    up_left = b.x + 20
    b.p(150, gap=170, dy=-380, ok=(260, 400))
    b.wind(up_left, b.y - 60, 150, 470, 0, -3600)
    b.p(320, gap=150, dy=0)
    b.rotor(-80, 72, 70, 1.8)
    b.rotor(80, 72, 70, -1.8)
    b.p(300, gap=200, dy=30)
    b.barrier(60, 320, 1.3, 1.8, 0.3)
    b.barrier(240, 320, 1.3, 1.8, 1.4)
    b.station(off=150)
    b.p(110, gap=250, dy=-30, kind="ghost", cyc=(2.2, 1.2, 0.0))
    b.p(110, gap=230, dy=-20, kind="ghost", cyc=(2.2, 1.2, 1.1))
    b.p(110, gap=230, dy=-20, kind="ghost", cyc=(2.2, 1.2, 2.2))
    b.p(300, gap=230, dy=10)
    b.spikes_on(110, 2)
    b.spikes_on(190, 2)
    b.p(420, gap=200, dy=-20)
    b.exit()
    return b.finish(0.5)


# ----------------------------------------------------------------- background
class Background:
    def __init__(self, world):
        self.world = world
        th = THEMES[world]
        self.grad = make_gradient(*th["sky"])
        rng = random.Random(world * 977 + 13)
        self.layers = []
        tw, thh = 1280, H + 160
        far = pygame.Surface((tw, thh), pygame.SRCALPHA)
        mid = pygame.Surface((tw, thh), pygame.SRCALPHA)
        near = pygame.Surface((tw, thh), pygame.SRCALPHA)
        acc = th["accent"]
        for _ in range(110):
            c = rng.randint(120, 255)
            pygame.draw.circle(far, (c, c, 255, rng.randint(60, 190)), (rng.randrange(tw), rng.randrange(thh)),
                               rng.choice((1, 1, 2)))
        for _ in range(4):
            pygame.draw.circle(far, (*acc, 14), (rng.randrange(tw), rng.randrange(thh)), rng.randint(90, 200))
        sil = shade(th["sky"][1], -22)
        if world == 0:
            for lay, n, alpha, sc in ((mid, 7, 120, 1.0), (near, 5, 190, 1.6)):
                for _ in range(n):
                    self._island(lay, rng.randrange(tw), rng.randint(180, 520), int(rng.randint(70, 170) * sc),
                                 (*shade(sil, 4), alpha))
        elif world == 1:
            for lay, n, alpha, sc in ((mid, 11, 130, 1.0), (near, 7, 210, 1.5)):
                for _ in range(n):
                    self._tree(lay, rng.randrange(tw), thh, int(rng.randint(160, 300) * sc), (*shade(sil, 3), alpha))
        elif world == 2:
            for lay, n, alpha, sc in ((mid, 5, 120, 1.0), (near, 4, 190, 1.6)):
                for _ in range(n):
                    self._gear(lay, rng.randrange(tw), rng.randint(100, 480), int(rng.randint(40, 90) * sc),
                               (*shade(sil, 6), alpha))
            for _ in range(7):
                x = rng.randrange(tw)
                pygame.draw.rect(near, (*shade(sil, -4), 210), (x, 0, 18, thh))
        elif world == 3:
            for lay, n, alpha, sc in ((mid, 14, 110, 1.0), (near, 9, 190, 1.5)):
                for _ in range(n):
                    self._crystal(lay, rng.randrange(tw), thh, int(rng.randint(100, 240) * sc),
                                  (*shade(th["body"], -70), alpha))
            for _ in range(3):
                pygame.draw.ellipse(far, (80, 220, 200, 22), (rng.randrange(tw), rng.randint(0, 200), 600, 120))
        else:
            for lay, n, alpha, sc in ((mid, 5, 110, 1.0), (near, 3, 180, 1.4)):
                for _ in range(n):
                    x, y, r = rng.randrange(tw), rng.randint(140, 440), int(rng.randint(60, 130) * sc)
                    pygame.draw.circle(lay, (*shade(acc, -110), alpha), (x, y), r, 5)
                    pygame.draw.circle(lay, (*shade(acc, -140), alpha), (x, y), int(r * 0.6), 3)
            for lay, n, alpha in ((mid, 6, 120),):
                for _ in range(n):
                    x = rng.randrange(tw)
                    hgt = rng.randint(160, 340)
                    pygame.draw.rect(lay, (*shade(sil, -4), alpha), (x, thh - hgt, 26, hgt))
        self.layers = [(0.06, far), (0.2, mid), (0.45, near)]
        self.motes = [[rng.random() * W, rng.random() * H, rng.random() * 6.28, rng.uniform(0.3, 1.0)]
                      for _ in range(42)]
        self.mote_col = acc

    @staticmethod
    def _island(s, x, y, w, col):
        pygame.draw.polygon(s, col, [(x, y), (x + w, y), (x + w * 0.62, y + w * 0.42), (x + w * 0.5, y + w * 0.7),
                                     (x + w * 0.38, y + w * 0.42)])

    @staticmethod
    def _tree(s, x, base, h, col):
        pygame.draw.rect(s, col, (x - 8, base - h, 16, h))
        for dx, dy, r in ((0, -h, 48), (-36, -h + 24, 36), (36, -h + 20, 38), (0, -h + 44, 40)):
            pygame.draw.circle(s, col, (x + dx, base + dy), r)

    @staticmethod
    def _gear(s, x, y, r, col):
        pygame.draw.circle(s, col, (x, y), r)
        for i in range(10):
            a = i * 6.283 / 10
            pygame.draw.circle(s, col, (int(x + math.cos(a) * r), int(y + math.sin(a) * r)), max(4, r // 5))
        pygame.draw.circle(s, (0, 0, 0, 0), (x, y), r // 3)

    @staticmethod
    def _crystal(s, x, base, h, col):
        w = h // 4
        pygame.draw.polygon(s, col, [(x - w, base), (x, base - h), (x + w, base)])
        pygame.draw.polygon(s, col, [(x + w, base), (x + w * 1.8, base - h * 0.6), (x + w * 2.6, base)])

    def draw(self, surf, camx, camy, t):
        surf.blit(self.grad, (0, 0))
        for f, tile in self.layers:
            tw = tile.get_width()
            ox = int(-camx * f) % tw
            oy = int(-80 + clamp(-camy * f * 0.2, -80, 80))
            x = ox - tw
            while x < W:
                surf.blit(tile, (x, oy))
                x += tw
        for m in self.motes:
            x = (m[0] - camx * 0.3 * m[3] + math.sin(t * 0.6 + m[2]) * 20) % W
            y = (m[1] - t * 8 * m[3] - camy * 0.1) % H
            add_glow(surf, (x, y), 5 + int(3 * m[3]), shade(self.mote_col, -150))


def make_vignette():
    v = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(0, 70, 2):
        a = int(120 * (1 - i / 70) ** 2)
        pygame.draw.rect(v, (0, 0, 0, a), Rect(i, i, W - 2 * i, H - 2 * i), 2)
    return v


# ----------------------------------------------------------------- screen fx
class ScreenFX:
    def __init__(self):
        rng = random.Random(42)
        self.grain = []
        for _ in range(4):
            g = pygame.Surface((W, H), pygame.SRCALPHA)
            for _ in range(1400):
                x, y = rng.randrange(W), rng.randrange(H)
                c = rng.randint(80, 200)
                a = rng.randint(8, 22)
                g.set_at((x, y), (c, c, c, a))
            self.grain.append(g)
        self.grain_i = 0
        self.grain_t = 0.0
        self.flash_col = None
        self.flash_a = 0.0

    def flash(self, col, a=180):
        self.flash_col = col
        self.flash_a = a

    def update(self, dt):
        self.grain_t += dt
        if self.grain_t > 0.1:
            self.grain_t = 0
            self.grain_i = (self.grain_i + 1) % len(self.grain)
        if self.flash_a > 0:
            self.flash_a = max(0, self.flash_a - dt * 500)

    def draw(self, surf, danger=0.0):
        surf.blit(self.grain[self.grain_i], (0, 0))
        if danger > 0.02:
            v = pygame.Surface((W, H), pygame.SRCALPHA)
            v.fill((140, 20, 40, int(80 * danger)))
            surf.blit(v, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        if self.flash_a > 0 and self.flash_col:
            v = pygame.Surface((W, H), pygame.SRCALPHA)
            v.fill((*self.flash_col, int(self.flash_a)))
            surf.blit(v, (0, 0))

    def speed_lines(self, surf, vx, vy):
        sp = math.hypot(vx, vy)
        if sp < 700:
            return
        a = clamp((sp - 700) / 800, 0, 1)
        cx, cy = W // 2, H // 2
        for _ in range(int(6 + 6 * a)):
            ang = random.random() * 6.283
            r1 = 300 + random.random() * 100
            r2 = r1 + 60 + random.random() * 100
            x1, y1 = cx + math.cos(ang) * r1, cy + math.sin(ang) * r1
            x2, y2 = cx + math.cos(ang) * r2, cy + math.sin(ang) * r2
            pygame.draw.line(surf, (200, 230, 255), (x1, y1), (x2, y2), 1)


# ----------------------------------------------------------------- particles
class Particles:
    def __init__(self):
        self.p = []

    def emit(self, x, y, vx, vy, life, size, color, grav=0.0, drag=0.0):
        if len(self.p) < 700:
            self.p.append([x, y, vx, vy, life, life, size, color, grav, drag])

    def burst(self, x, y, n, speed, life, size, color, grav=0.0, a0=0.0, a1=6.283):
        for _ in range(n):
            a = random.uniform(a0, a1)
            s = random.uniform(0.3, 1.0) * speed
            self.emit(x, y, math.cos(a) * s, math.sin(a) * s, life * random.uniform(0.6, 1.1), size, color, grav, 1.5)

    def ring(self, x, y, n, speed, life, size, color):
        for i in range(n):
            a = i * 6.283 / n
            self.emit(x, y, math.cos(a) * speed, math.sin(a) * speed * 0.35, life, size, color, 0, 2.0)

    def update(self, dt):
        out = []
        for q in self.p:
            q[4] -= dt
            if q[4] <= 0:
                continue
            q[2] -= q[2] * q[9] * dt
            q[3] += q[8] * dt - q[3] * q[9] * dt * 0.5
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            out.append(q)
        self.p = out

    def draw(self, surf, cam):
        for q in self.p:
            a = q[4] / q[5]
            k = round(a * 6) / 6
            if k <= 0:
                continue
            c = (int(q[7][0] * k), int(q[7][1] * k), int(q[7][2] * k))
            add_glow(surf, (q[0] - cam[0], q[1] - cam[1]), max(3, q[6] * (0.4 + a) * 1.6), c)


# ----------------------------------------------------------------- player
class Player:
    def __init__(self):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.ground = None
        self.reset_state()

    def reset_state(self):
        self.vx = self.vy = 0.0
        self.ground = None
        self.coyote = 0.0
        self.jbuf = 0.0
        self.jflag = False
        self.wall = 0
        self.lock = 0.0
        self.dj_used = False
        self.dash_t = self.dash_cd = 0.0
        self.dash_dir = 1
        self.dash_ready = True
        self.dash_req = 0.0
        self.slam = False
        self.slam_req = 0.0
        self.bounce_cd = 0.0
        self.face = 1
        self.sx = self.sy = 1.0
        self.glow = 0.0
        self.spawn_t = 0.0
        self.blink = 3.0
        self.trail = 0.0
        self.trail_history = []

    def respawn(self, x, ytop):
        self.x, self.y = x - PS / 2, ytop - PS - 1
        self.reset_state()

    @property
    def cx(self):
        return self.x + PS / 2

    @property
    def cy(self):
        return self.y + PS / 2

    def rect(self):
        return Rect(int(self.x), int(self.y), PS, PS)

    def move_x(self, dx, solids):
        if dx == 0:
            return False
        self.x += dx
        hit = False
        for p in solids:
            r = p.rect
            if self.x < r.right and self.x + PS > r.left and self.y < r.bottom and self.y + PS > r.top:
                self.x = r.left - PS if dx > 0 else r.right
                hit = True
        return hit

    def move_y(self, dy, solids):
        if dy == 0:
            return None
        self.y += dy
        res = None
        for p in solids:
            r = p.rect
            if self.x < r.right and self.x + PS > r.left and self.y < r.bottom and self.y + PS > r.top:
                if dy > 0:
                    self.y = r.top - PS
                    res = ("down", p)
                else:
                    self.y = r.bottom
                    res = ("up", p)
        return res


# ----------------------------------------------------------------- UI widgets
class ListMenu:
    def __init__(self, game, items, font="m", gap=50, horizontal=False):
        self.g, self.items, self.sel = game, items, 0
        self.font, self.gap, self.horizontal = font, gap, horizontal
        self.rects = []
        self._fix()

    def _fix(self):
        if not self.enabled(self.sel):
            self.move(1)

    def label(self, i):
        l = self.items[i]["label"]
        return l() if callable(l) else l

    def enabled(self, i):
        e = self.items[i].get("enabled", True)
        return e() if callable(e) else e

    def move(self, d):
        n = len(self.items)
        for _ in range(n):
            self.sel = (self.sel + d) % n
            if self.enabled(self.sel):
                break
        self.g.audio.play("ui", 0.6)

    def act(self, key="action"):
        fn = self.items[self.sel].get(key)
        if fn:
            self.g.audio.play("select", 0.7)
            fn()

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            k = e.key
            prev = (pygame.K_LEFT, pygame.K_a) if self.horizontal else (pygame.K_UP, pygame.K_w)
            nxt = (pygame.K_RIGHT, pygame.K_d) if self.horizontal else (pygame.K_DOWN, pygame.K_s)
            if k in prev:
                self.move(-1)
            elif k in nxt:
                self.move(1)
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.act()
            elif not self.horizontal and k in (pygame.K_LEFT, pygame.K_a):
                self.act("left")
            elif not self.horizontal and k in (pygame.K_RIGHT, pygame.K_d):
                self.act("right")
        elif e.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.rects):
                if r.collidepoint(e.pos) and self.enabled(i) and i != self.sel:
                    self.sel = i
                    self.g.audio.play("ui", 0.4)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.rects):
                if r.collidepoint(e.pos) and self.enabled(i):
                    self.sel = i
                    self.act()

    def draw(self, surf, cx, y, t, color=(90, 220, 255)):
        f = self.g.fonts[self.font]
        self.rects = []
        x = cx
        if self.horizontal:
            widths = [f.size(self.label(i))[0] + 50 for i in range(len(self.items))]
            total = sum(widths) + 14 * (len(widths) - 1)
            x = cx - total / 2
        for i in range(len(self.items)):
            lab = self.label(i)
            en = self.enabled(i)
            sel = i == self.sel
            if self.horizontal:
                r = Rect(int(x), int(y), widths[i], 46)
                x += widths[i] + 14
            else:
                r = Rect(0, 0, 360, 44)
                r.center = (cx, int(y + i * self.gap))
            self.rects.append(r)
            if sel:
                panel(surf, r, color, int(60 + 25 * math.sin(t * 6)), 12, color)
            col = (255, 255, 255) if sel else ((170, 185, 210) if en else (90, 100, 120))
            draw_text(surf, lab, f, col, r.center)


# ----------------------------------------------------------------- scenes
class MenuScene:
    def __init__(self, game):
        self.g = game
        self.t = 0.0
        self.bg = Background(0)
        self.orb_y, self.orb_v = 380.0, 0.0
        s = game.save
        items = [
            dict(label="Continue", action=self.cont, enabled=lambda: bool(s["run"]) or s["unlocked"] > 1
                 or bool(s["best"])),
            dict(label="New Game", action=self.new_game),
            dict(label="Level Selection", action=lambda: game.set_scene(SelectScene(game))),
            dict(label="Skins", action=lambda: game.set_scene(SkinScene(game))),
            dict(label="Settings", action=lambda: game.set_scene(SettingsScene(game, lambda: MenuScene(game)))),
            dict(label="Exit", action=game.quit),
        ]
        self.menu = ListMenu(game, items, "m", 46)
        self.parts = Particles()
        game.audio.music(0)
        game.audio.set_intensity(0.4)

    def cont(self):
        s = self.g.save
        if s["run"]:
            self.g.set_scene(PlayScene(self.g, s["run"]["level"], s["run"]))
        else:
            self.g.set_scene(PlayScene(self.g, min(s["unlocked"], 5) - 1))

    def new_game(self):
        s = self.g.save
        if s["run"] or s["unlocked"] > 1 or s["best"]:
            self.g.set_scene(ConfirmScene(self.g, "Start over? Your saved progress will be erased.", self.reset,
                                          lambda: MenuScene(self.g)))
        else:
            self.reset()

    def reset(self):
        st = self.g.save["settings"]
        bank = self.g.save.get("energy_bank", 0)
        skins = self.g.save.get("skins", ["default"])
        skin = self.g.save.get("skin", "default")
        self.g.save.update(default_save())
        self.g.save["settings"] = st
        self.g.save["energy_bank"] = bank
        self.g.save["skins"] = skins
        self.g.save["skin"] = skin
        write_save(self.g.save)
        self.g.set_scene(StoryScene(self.g))

    def handle(self, e):
        self.menu.handle(e)

    def update(self, dt):
        self.t += dt
        self.orb_v += 1500 * dt
        self.orb_y += self.orb_v * dt
        if self.orb_y > 410:
            self.orb_y = 410
            self.orb_v = -640
            self.parts.burst(W // 2 + 280, 440, 8, 140, 0.5, 4, (70, 210, 255), 200)
        self.parts.update(dt)
        self.g.audio.update(dt)

    def draw(self, surf):
        self.bg.draw(surf, self.t * 40, 0, self.t)
        px = W // 2 + 280
        pygame.draw.rect(surf, THEMES[0]["body"], (px - 70, 440, 140, 26), border_radius=7)
        pygame.draw.rect(surf, THEMES[0]["top"], (px - 70, 440, 140, 8), border_radius=7)
        st = 1 + clamp(abs(self.orb_v) / 3000, 0, 0.2)
        draw_orb(surf, px, self.orb_y, 1 / st if self.orb_v < 0 else 1.0,
                 st if self.orb_v < 0 else 1.0, 0.4, self.orb_v / 2, self.t,
                 skin=skin_by_key(self.g.save["skin"]))
        self.parts.draw(surf, (0, 0))
        glow_text(surf, "REBOUND", self.g.fonts["xxl"], (235, 250, 255), (30, 160, 255), (W // 2, 110))
        draw_text(surf, "THE LAST BOUNCE", self.g.fonts["l"], (120, 220, 255), (W // 2, 178))
        draw_text(surf, "Every fall is an opportunity to bounce back stronger.", self.g.fonts["s"],
                  (190, 205, 235), (W // 2, 214))
        self.menu.draw(surf, W // 2 - 120, 255, self.t)
        # banked energy readout bottom-left
        bank = self.g.save.get("energy_bank", 0)
        draw_text(surf, "BANKED  %d" % bank, self.g.fonts["s"], (255, 235, 150), (26, H - 22), anchor="topleft")
        draw_text(surf, "Arrows / Enter or mouse", self.g.fonts["xs"], (130, 150, 190), (W // 2, H - 18))


class ConfirmScene:
    def __init__(self, game, text, yes, back):
        self.g, self.text, self.t = game, text, 0.0
        self.bg = Background(0)
        self.menu = ListMenu(game, [dict(label="Yes", action=yes),
                                    dict(label="Back", action=lambda: game.set_scene(back()))], "m", 50)
        self.menu.sel = 1

    def handle(self, e):
        self.menu.handle(e)

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        self.bg.draw(surf, self.t * 30, 0, self.t)
        panel(surf, (W // 2 - 300, 150, 600, 240), (8, 12, 30), 200, 18, (90, 220, 255))
        draw_text(surf, self.text, self.g.fonts["s"], (230, 240, 255), (W // 2, 205))
        self.menu.draw(surf, W // 2, 265, self.t)


class SettingsScene:
    def __init__(self, game, back):
        self.g, self.back, self.t = game, back, 0.0
        self.bg = Background(0)
        s = game.save["settings"]

        def bar(v):
            n = int(round(v * 10))
            return "|" * n + "." * (10 - n)

        def step(key, d):
            s[key] = clamp(round(s[key] + d, 2), 0.0, 1.0)
            game.audio.volumes()
            write_save(game.save)

        def toggle_shake():
            s["shake"] = not s["shake"]
            write_save(game.save)

        items = [
            dict(label=lambda: "Music  < %s >" % bar(s["music"]), left=lambda: step("music", -0.1),
                 right=lambda: step("music", 0.1), action=lambda: step("music", 0.1)),
            dict(label=lambda: "Effects  < %s >" % bar(s["sfx"]), left=lambda: step("sfx", -0.1),
                 right=lambda: step("sfx", 0.1), action=lambda: (step("sfx", 0.1), game.audio.play("chime"))),
            dict(label=lambda: "Screen Shake: %s" % ("On" if s["shake"] else "Off"), action=toggle_shake,
                 left=toggle_shake, right=toggle_shake),
            dict(label="Fullscreen (F11)", action=lambda: pygame.display.toggle_fullscreen()),
            dict(label="Back", action=lambda: game.set_scene(back())),
        ]
        self.menu = ListMenu(game, items, "m", 52)

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.g.set_scene(self.back())
            return
        self.menu.handle(e)

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        self.bg.draw(surf, self.t * 30, 0, self.t)
        glow_text(surf, "SETTINGS", self.g.fonts["xl"], (235, 250, 255), (30, 160, 255), (W // 2, 90))
        self.menu.draw(surf, W // 2, 190, self.t)


class SkinScene:
    def __init__(self, game):
        self.g, self.t = game, 0.0
        self.bg = Background(4)
        self.sel = 0
        # find currently equipped index as starting selection
        for i, s in enumerate(SKINS):
            if s["key"] == game.save["skin"]:
                self.sel = i
                break
        cols, rows = 3, 2
        cw, ch = 250, 180
        gap = 20
        total_w = cols * cw + (cols - 1) * gap
        x0 = (W - total_w) // 2
        y0 = 155
        self.cards = []
        for i in range(len(SKINS)):
            c, r = i % cols, i // cols
            self.cards.append(Rect(x0 + c * (cw + gap), y0 + r * (ch + gap), cw, ch))
        self.msg = ""
        self.msg_t = 0.0
        game.audio.music(4)
        game.audio.set_intensity(0.4)

    def act(self):
        skin = SKINS[self.sel]
        save = self.g.save
        if skin["key"] == save["skin"]:
            self.flash_msg("Already wearing that.")
            self.g.audio.play("ui", 0.6)
            return
        if skin["key"] in save["skins"]:
            save["skin"] = skin["key"]
            write_save(save)
            self.flash_msg("Equipped: " + skin["name"])
            self.g.audio.play("select")
            return
        cost = skin["cost"]
        if save["energy_bank"] < cost:
            self.flash_msg("Need %d more energy" % (cost - save["energy_bank"]))
            self.g.audio.play("deny")
            return
        save["energy_bank"] -= cost
        save["skins"].append(skin["key"])
        save["skin"] = skin["key"]
        write_save(save)
        self.flash_msg("Unlocked: " + skin["name"])
        self.g.audio.play("unlock")

    def flash_msg(self, s):
        self.msg = s
        self.msg_t = 2.0

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                self.g.set_scene(MenuScene(self.g))
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.sel = (self.sel - 1) % len(SKINS)
                self.g.audio.play("ui", 0.6)
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.sel = (self.sel + 1) % len(SKINS)
                self.g.audio.play("ui", 0.6)
            elif k in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 3) % len(SKINS)
                self.g.audio.play("ui", 0.6)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 3) % len(SKINS)
                self.g.audio.play("ui", 0.6)
            elif k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.act()
        elif e.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.cards):
                if r.collidepoint(e.pos) and i != self.sel:
                    self.sel = i
                    self.g.audio.play("ui", 0.4)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.cards):
                if r.collidepoint(e.pos):
                    self.sel = i
                    self.act()

    def update(self, dt):
        self.t += dt
        self.msg_t = max(0.0, self.msg_t - dt)
        self.g.audio.update(dt)

    def draw(self, surf):
        self.bg.draw(surf, self.t * 30, 0, self.t)
        glow_text(surf, "SKINS", self.g.fonts["xl"], (235, 250, 255), (30, 160, 255), (W // 2, 56))
        bank = self.g.save.get("energy_bank", 0)
        draw_text(surf, "BANKED ENERGY", self.g.fonts["xs"], (140, 160, 200), (W // 2, 92))
        draw_text(surf, "%d" % bank, self.g.fonts["l"], (255, 235, 150), (W // 2, 118))
        draw_text(surf, "Complete levels to earn more.", self.g.fonts["xs"], (150, 170, 200), (W // 2, 145))

        for i, r in enumerate(self.cards):
            skin = SKINS[i]
            owned = skin["key"] in self.g.save["skins"]
            equipped = skin["key"] == self.g.save["skin"]
            sel = i == self.sel
            rr = r.inflate(6, 6) if sel else r
            panel(surf, rr, (8, 12, 30), 200, 14,
                  skin["trail"] if sel else (60, 70, 100), 2)
            cx, cy = rr.centerx, rr.y + 56
            draw_skin_preview(surf, cx, cy, 28, skin, self.t + i * 0.6)
            draw_text(surf, skin["name"], self.g.fonts["m"], (245, 250, 255), (rr.centerx, rr.y + 108))
            draw_text(surf, skin["desc"], self.g.fonts["xs"], (180, 195, 225), (rr.centerx, rr.y + 130))
            if equipped:
                draw_text(surf, "EQUIPPED", self.g.fonts["s"], (140, 255, 180), (rr.centerx, rr.y + 156))
            elif owned:
                draw_text(surf, "OWNED  -  click to equip", self.g.fonts["xs"], (160, 200, 255),
                          (rr.centerx, rr.y + 156))
            else:
                can = bank >= skin["cost"]
                col = (255, 235, 150) if can else (150, 120, 120)
                draw_text(surf, "%d energy" % skin["cost"], self.g.fonts["s"], col, (rr.centerx, rr.y + 156))

        if self.msg_t > 0:
            a = int(255 * clamp(self.msg_t / 0.4, 0, 1))
            draw_text(surf, self.msg, self.g.fonts["m"], (255, 255, 255), (W // 2, H - 60), alpha=a)
        draw_text(surf, "Arrows - Enter to select - Esc to go back", self.g.fonts["xs"], (170, 185, 215),
                  (W // 2, H - 24))


class SelectScene:
    def __init__(self, game):
        self.g, self.t = game, 0.0
        self.sel = max(0, min(game.save["unlocked"], 5) - 1)
        self.bgs = [Background(i) for i in range(5)]
        self.rects = [Rect(30 + i * 180, 130, 168, 300) for i in range(5)]

    def go(self, i):
        if i < self.g.save["unlocked"]:
            self.g.audio.play("select")
            self.g.set_scene(PlayScene(self.g, i))
        else:
            self.g.audio.play("deny")

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_LEFT, pygame.K_a):
                self.sel = (self.sel - 1) % 5
                self.g.audio.play("ui", 0.6)
            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                self.sel = (self.sel + 1) % 5
                self.g.audio.play("ui", 0.6)
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.go(self.sel)
            elif e.key == pygame.K_ESCAPE:
                self.g.set_scene(MenuScene(self.g))
        elif e.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.rects):
                if r.collidepoint(e.pos):
                    self.sel = i
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.rects):
                if r.collidepoint(e.pos):
                    self.sel = i
                    self.go(i)

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        self.bgs[self.sel].draw(surf, self.t * 40, 0, self.t)
        glow_text(surf, "LEVEL SELECTION", self.g.fonts["xl"], (235, 250, 255), (30, 160, 255), (W // 2, 70))
        s = self.g.save
        for i, r in enumerate(self.rects):
            th = THEMES[i]
            locked = i >= s["unlocked"]
            sel = i == self.sel
            rr = r.inflate(10, 10) if sel else r
            card = pygame.Surface(rr.size)
            card.blit(pygame.transform.smoothscale(make_gradient(*th["sky"], 8, 8), rr.size), (0, 0))
            if locked:
                card.fill((18, 20, 30))
            surf.blit(card, rr.topleft)
            pygame.draw.rect(surf, th["accent"] if sel else (80, 90, 120), rr, 3 if sel else 1, border_radius=4)
            draw_text(surf, "WORLD %d" % (i + 1), self.g.fonts["s"], (200, 215, 240), (rr.centerx, rr.y + 26))
            for j, line in enumerate(wrap_text(self.g.fonts["m"], th["name"], 140)):
                draw_text(surf, line, self.g.fonts["s"], (255, 255, 255) if not locked else (110, 120, 140),
                          (rr.centerx, rr.y + 70 + j * 24))
            if locked:
                draw_text(surf, "LOCKED", self.g.fonts["m"], (130, 140, 170), (rr.centerx, rr.centery + 30))
            else:
                b = s["best"].get(str(i))
                draw_text(surf, th["sub"], self.g.fonts["xs"], (190, 205, 235), (rr.centerx, rr.y + 150))
                if b:
                    draw_text(surf, "Best  " + fmt_time(b["time"]), self.g.fonts["s"], (255, 235, 150),
                              (rr.centerx, rr.y + 220))
                    draw_text(surf, "Energy %d" % b["energy"], self.g.fonts["s"], th["accent"],
                              (rr.centerx, rr.y + 245))
                    draw_text(surf, "Falls %d" % b["falls"], self.g.fonts["s"], (200, 210, 230),
                              (rr.centerx, rr.y + 270))
                else:
                    draw_text(surf, "Not restored yet", self.g.fonts["s"], (160, 175, 205),
                              (rr.centerx, rr.y + 240))
        draw_text(surf, "Left / Right - Enter to play - Esc to go back", self.g.fonts["xs"], (170, 185, 215),
                  (W // 2, H - 30))


class StoryScene:
    def __init__(self, game):
        self.g, self.t, self.page = game, 0.0, 0
        self.bg = Background(0)
        game.audio.music(0)
        game.audio.set_intensity(0.3)

    def next(self):
        self.page += 1
        self.t = 0.0
        if self.page >= len(STORY):
            self.g.set_scene(PlayScene(self.g, 0))

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.g.set_scene(PlayScene(self.g, 0))
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.next()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.next()

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        self.bg.draw(surf, self.t * 10, 0, self.t)
        a = int(255 * clamp(self.t / 1.2, 0, 1))
        y = 190
        for para in STORY[self.page].split("\n"):
            for line in wrap_text(self.g.fonts["m"], para, 760):
                draw_text(surf, line, self.g.fonts["m"], (225, 238, 255), (W // 2, y), alpha=a)
                y += 40
        if self.page == 3 and self.t > 1.0:
            draw_orb(surf, W // 2, 400, 1.0, 1.0, min(1, (self.t - 1.0)), 0, self.t,
                     scale=2.2, skin=skin_by_key(self.g.save["skin"]))
        draw_text(surf, "Enter / click to continue   -   Esc to skip", self.g.fonts["xs"], (130, 150, 190),
                  (W // 2, H - 24))


class EndingScene:
    def __init__(self, game):
        self.g, self.t = game, 0.0
        self.bg = Background(4)
        game.audio.music(4)
        game.audio.set_intensity(0.8)
        self.rng = random.Random(5)
        self.isl = [(self.rng.uniform(80, 880), self.rng.uniform(80, 460), self.rng.uniform(70, 150),
                     self.rng.uniform(-6, 6)) for _ in range(9)]
        self.parts = Particles()
        self.flag = False

    def handle(self, e):
        if self.t > 15 and ((e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE))
                            or e.type == pygame.MOUSEBUTTONDOWN):
            self.g.set_scene(MenuScene(self.g))

    def update(self, dt):
        self.t += dt
        if self.t > 3.0 and not self.flag:
            self.flag = True
            self.g.audio.play("restore")
            self.g.audio.set_intensity(1.4)
        if self.t > 9.5 and int(self.t * 4) % 4 == 0:
            self.parts.burst(random.uniform(100, 860), random.uniform(60, 300), 2, 80, 1.4, 4,
                             random.choice([THEMES[i]["accent"] for i in range(5)]), -20)
        self.parts.update(dt)
        self.g.audio.update(dt)

    def draw(self, surf):
        t = self.t
        self.bg.draw(surf, t * 12, 0, t)
        dark = pygame.Surface((W, H))
        dark.set_alpha(int(235 * (1 - clamp((t - 3) / 4, 0, 1))))
        surf.blit(dark, (0, 0))
        k = ease_out((t - 3.0) / 4.0)
        for i, (x, y, w, dy) in enumerate(self.isl):
            tx = 70 + i * 100
            ty = 330 + (i % 3) * 22
            px, py = lerp(x, tx, k), lerp(y, ty, k)
            th = THEMES[i % 5]
            if k > 0.02:
                pygame.draw.rect(surf, th["body"], (px - 46, py, 92, 24), border_radius=7)
                pygame.draw.rect(surf, th["top"], (px - 46, py, 92, 8), border_radius=7)
                if t > 7.0:
                    gk = clamp((t - 7.0) / 2.0, 0, 1)
                    pygame.draw.circle(surf, shade(th["top"], -30), (int(px), int(py - 12 * gk)), int(14 * gk))
        cx, cy = W // 2, 190
        if t < 3.2:
            for i in range(5):
                a = t * 1.6 + i * 6.283 / 5
                r = lerp(300, 0, ease_out(t / 3.0))
                px, py = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.6
                col = THEMES[i]["accent"]
                pygame.draw.circle(surf, col, (int(px), int(py)), 8)
                add_glow(surf, (px, py), 34, shade(col, -120))
        gl = clamp((t - 3) / 2, 0, 1)
        add_glow(surf, (cx, cy), int(40 + 150 * gl), (int(120 * gl) + 20, int(80 * gl) + 20, int(120 * gl) + 30))
        pygame.draw.circle(surf, mixc((40, 40, 60), (255, 240, 255), gl), (cx, cy), 26)
        if t > 3.0:
            for j in range(6):
                rr = ((t - 3.0) * 140 + j * 130) % 800
                col = THEMES[j % 5]["accent"]
                pygame.draw.circle(surf, shade(col, -int(rr * 0.25)), (cx, cy), int(rr), 3)
        self.parts.draw(surf, (0, 0))
        if t > 6.5:
            draw_orb(surf, cx, 420, 1.0, 1.0, 1.0, 0, t, scale=1.6, skin=skin_by_key(self.g.save["skin"]))
        lines = ["You were never defined by how many times you fell.",
                 "You were defined by how many times you bounced back."]
        for i, l in enumerate(lines):
            a = int(255 * clamp((t - 8.0 - i * 2.2) / 1.5, 0, 1))
            if a:
                draw_text(surf, l, self.g.fonts["m"], (240, 245, 255), (W // 2, 90 + i * 40), alpha=a)
        a = int(255 * clamp((t - 13.0) / 1.5, 0, 1))
        if a:
            glow_text(surf, "THE WORLD IS RESTORED", self.g.fonts["xl"], (255, 245, 230), (255, 150, 60),
                      (W // 2, 500), alpha=a)
        if t > 15:
            draw_text(surf, "Press Enter", self.g.fonts["s"], (190, 205, 235), (W - 90, H - 24))


# ----------------------------------------------------------------- orb drawing
def draw_orb(surf, cx, bottom, sx, sy, alpha_scale, vel, t, glow=0.0, scale=1.0, vx=0.0,
             blink=False, glow_col=None, skin=None):
    if skin is None:
        skin = SKINS[0]
    if glow_col is None:
        glow_col = skin["glow"]
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    body_c = mixc(skin["body"], skin["mid"], clamp(glow, 0, 1) * 0.6)
    pygame.draw.circle(s, body_c, (32, 32), 15)
    pygame.draw.circle(s, mixc(body_c, skin["mid"], 0.6), (32, 32), 12)
    pygame.draw.circle(s, mixc(skin["mid"], (255, 255, 255), glow), (32, 37), 6)
    ex = clamp(vx / 300, -1, 1) * 1.6
    ey = clamp(vel / 900, -1, 1) * 1.5
    for dx in (-5, 5):
        if blink:
            pygame.draw.line(s, (240, 255, 255), (32 + dx - 3, 29), (32 + dx + 3, 29), 2)
        else:
            pygame.draw.ellipse(s, (245, 255, 255), (32 + dx - 3, 24, 6, 9))
            pygame.draw.ellipse(s, (15, 50, 100), (32 + dx - 1 + ex, 27 + ey, 3, 5))
    w = max(2, int(64 * sx * scale))
    h = max(2, int(64 * sy * scale))
    img = pygame.transform.smoothscale(s, (w, h))
    a = clamp(alpha_scale, 0, 1)
    if a < 1:
        img.set_alpha(int(255 * a))
    gx, gy = cx, bottom - 15 * sy * scale
    add_glow(surf, (gx, gy), int((46 + 14 * glow) * scale * max(0.3, a)), shade(glow_col, int(60 * glow)))
    surf.blit(img, (cx - w / 2, bottom - 47 * sy * scale))
    breath = 0.6 + 0.4 * math.sin(t * 3.2)
    pygame.draw.circle(surf, mixc(skin["glow"], skin["trail"], glow),
                       (int(cx), int(bottom - 15 * sy * scale)), int(20 * scale * breath), 1)


def draw_skin_preview(surf, cx, cy, r, skin, t):
    breath = 0.6 + 0.4 * math.sin(t * 3.0)
    add_glow(surf, (cx, cy), int(r * 2.0), skin["glow"])
    pygame.draw.circle(surf, skin["body"], (int(cx), int(cy)), r)
    pygame.draw.circle(surf, skin["mid"], (int(cx), int(cy)), int(r * 0.78))
    pygame.draw.circle(surf, mixc(skin["mid"], (255, 255, 255), 0.6),
                       (int(cx + r * 0.05), int(cy + r * 0.15)), max(2, int(r * 0.32)))
    pygame.draw.circle(surf, mixc(skin["glow"], skin["trail"], 0.5),
                       (int(cx), int(cy)), int(r * 1.18 * breath), 2)


# ----------------------------------------------------------------- play scene
class PlayScene:
    def __init__(self, game, idx, run=None):
        self.g = game
        self.idx = idx
        self.level = build_level(idx)
        self.theme = self.level.theme
        self.bg = Background(self.level.world)
        self.vig = game.vignette
        self.abil = set(game.save["abilities"]) | {"bounce"}
        self.skin = skin_by_key(game.save["skin"])
        self.p = Player()
        self.parts = Particles()
        self.fx = ScreenFX()
        self.echoes = []
        self.cam = [0.0, 0.0]
        self.t = 0.0
        self.time = 0.0
        self.falls = 0
        self.energy = 0
        self.collected = set()
        self.station = -1
        self.mode = "play"
        self.mode_t = 0.0
        self.shake = 0.0
        self.msg = ("", 0.0)
        self.banner = None
        self.intro = 3.0
        self.god = False
        self.interact = False
        self.paused = False
        self.combo = 0
        self.combo_t = 0.0
        self.new_best = False
        self.earned_energy = 0
        self.menu_done = None
        if self.level.shrine and self.level.shrine.ability in self.abil:
            self.level.shrine.active = True
        if run and run.get("level") == idx:
            self.station = run["station"]
            self.collected = set(run["collected"])
            self.time = run.get("time", 0.0)
            self.falls = run.get("falls", 0)
            for it in self.level.items:
                if it.id in self.collected:
                    it.got = True
                    self.energy += it.value
            for i, st in enumerate(self.level.stations):
                st.active = i <= self.station
        self.respawn(first=True)
        self.menu_pause = ListMenu(game, [
            dict(label="Resume", action=self.resume),
            dict(label="Restart Checkpoint", action=self.restart_checkpoint),
            dict(label="Restart Level", action=self.restart_level),
            dict(label="Settings", action=lambda: game.set_scene(SettingsScene(game, lambda: self._return_pause()))),
            dict(label="Main Menu", action=self.to_menu),
        ], "m", 48)
        game.audio.music(self.level.world)

    def _return_pause(self):
        self.paused = True
        return self

    def resume(self):
        self.paused = False

    def restart_checkpoint(self):
        self.paused = False
        self.respawn()

    def restart_level(self):
        self.g.save["run"] = None
        self.g.set_scene(PlayScene(self.g, self.idx))

    def to_menu(self):
        self.g.set_scene(MenuScene(self.g))

    def spawn_point(self):
        if self.station >= 0:
            st = self.level.stations[self.station]
            return st.x, st.y
        return self.level.start

    def respawn(self, first=False):
        x, y = self.spawn_point()
        self.p.respawn(x, y)
        self.p.spawn_t = 0.0
        self.mode = "play"
        self.cam[0] = self.p.cx - W * 0.42
        self.cam[1] = self.p.cy - H * 0.55
        self.clamp_cam()
        if not first:
            self.parts.burst(self.p.cx, self.p.cy, 18, 220, 0.6, 5, self.theme["accent"])

    def say(self, text, t=2.2):
        self.msg = (text, t)

    def save_run(self):
        self.g.save["run"] = {"level": self.idx, "station": self.station,
                              "collected": sorted(self.collected),
                              "time": self.time, "falls": self.falls}
        write_save(self.g.save)

    def handle(self, e):
        if self.mode == "complete":
            if self.menu_done:
                self.menu_done.handle(e)
            return
        if self.paused:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_p):
                self.paused = False
                return
            self.menu_pause.handle(e)
            return
        P = self.p
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_ESCAPE, pygame.K_p):
                self.paused = True
                self.menu_pause.sel = 0
            elif k in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                P.jbuf = JBUF
            elif k in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                P.dash_req = 0.12
            elif k in (pygame.K_s, pygame.K_DOWN):
                P.slam_req = 0.12
            elif k == pygame.K_e:
                self.interact = True
            elif DEBUG and k == pygame.K_F1:
                self.god = not self.god
                self.say("God mode " + ("ON" if self.god else "OFF"))
            elif DEBUG and k == pygame.K_F2:
                self.abil |= {"wall", "power", "double", "dash"}
                self.say("All abilities")
            elif DEBUG and k == pygame.K_F3:
                P.x, P.y = self.level.exit.x - 20, self.level.exit.y - PS - 4
        elif e.type == pygame.KEYUP:
            if e.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                if P.jflag and P.vy < -260:
                    P.vy *= 0.5
                P.jflag = False
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if Rect(W - 54, 12, 40, 40).collidepoint(e.pos):
                self.paused = True

    def update(self, dt):
        dt = min(dt, 1 / 30)
        if self.paused:
            return
        self.t += dt
        self.fx.update(dt)
        self.shake = max(0.0, self.shake - dt * 30)
        self.msg = (self.msg[0], max(0.0, self.msg[1] - dt))
        if self.banner:
            self.banner = (self.banner[0], self.banner[1], self.banner[2] - dt)
            if self.banner[2] <= 0:
                self.banner = None
        self.combo_t = max(0.0, self.combo_t - dt)
        if self.combo_t == 0:
            self.combo = 0
        for st in self.level.stations:
            st.flash = max(0.0, st.flash - dt * 1.5)
        self.level.update(self.t, dt, self.p.rect())
        if self.mode == "play":
            self.intro = max(0.0, self.intro - dt)
            self.time += dt
            self.update_player(dt)
        elif self.mode == "dead":
            self.mode_t += dt
            if self.mode_t > 0.85:
                self.respawn()
        elif self.mode == "restoring":
            self.mode_t += dt
            if self.mode_t > 2.6:
                self.finish_level()
        elif self.mode == "complete":
            self.mode_t += dt
        self.parts.update(dt)
        self.update_camera(dt)
        sp = math.hypot(self.p.vx, self.p.vy)
        danger = clamp(1.0 - (self.level.kill_y - self.p.cy) / 300, 0, 1)
        if self.mode == "complete":
            self.g.audio.set_intensity(1.6)
        elif self.mode == "restoring":
            self.g.audio.set_intensity(2.0)
        else:
            self.g.audio.set_intensity(0.3 + min(1.0, sp / 900) * 0.9 + danger * 0.7 + min(1.0, self.combo * 0.12))
        self.g.audio.update(dt)
        self.interact = False

    def keys(self):
        return self.g.keys()

    def update_player(self, dt):
        P, lv, ab = self.p, self.level, self.abil
        keys = self.keys()
        d = (1 if (keys[pygame.K_d] or keys[pygame.K_RIGHT]) else 0) - (
            1 if (keys[pygame.K_a] or keys[pygame.K_LEFT]) else 0)
        if P.lock > 0:
            d = 0
        P.lock = max(0.0, P.lock - dt)
        P.spawn_t += dt
        P.jbuf = max(0.0, P.jbuf - dt)
        P.coyote = max(0.0, P.coyote - dt)
        P.dash_req = max(0.0, P.dash_req - dt)
        P.slam_req = max(0.0, P.slam_req - dt)
        P.dash_cd = max(0.0, P.dash_cd - dt)
        P.bounce_cd = max(0.0, P.bounce_cd - dt)
        P.glow = max(0.0, P.glow - dt * 1.6)
        P.sx += (1.0 - P.sx) * min(1.0, dt * 18)
        P.sy += (1.0 - P.sy) * min(1.0, dt * 18)
        if d:
            P.face = d

        solids = [p for p in lv.plats if p.solid and p.rect.right > P.x - 420 and p.rect.left < P.x + PS + 420]

        for m in lv.movers:
            dx, dy = m.delta
            if not (dx or dy) or not m.solid:
                continue
            if P.ground is m:
                P.move_x(dx, solids)
                P.move_y(dy, solids)
            elif m.rect.left < P.x + PS and m.rect.right > P.x and m.rect.top < P.y + PS and m.rect.bottom > P.y:
                if dy < 0 and P.y + PS - m.rect.top <= -dy + 6:
                    P.y = m.rect.top - PS
                elif dx:
                    P.x = m.rect.right if dx > 0 else m.rect.left - PS

        P.wall = 0
        if P.ground is None:
            for p in solids:
                r = p.rect
                if r.top < P.y + PS - 6 and r.bottom > P.y + 6:
                    if abs(P.x - r.right) <= 1.5:
                        P.wall = -1
                        break
                    if abs(P.x + PS - r.left) <= 1.5:
                        P.wall = 1
                        break

        wx = 0.0
        for w in lv.winds:
            if w.rect.collidepoint(P.cx, P.cy):
                if w.ax:
                    wx += w.ax
                if w.ay:
                    P.vy = clamp(P.vy + w.ay * dt, -430 if w.ay < 0 else -9999, TERM)
                    P.jflag = False
                    if w.ay < 0:
                        P.dj_used = False

        if P.jbuf > 0:
            if P.ground is not None or P.coyote > 0:
                P.vy = JUMP_V
                P.jflag = True
                P.jbuf = P.coyote = 0.0
                P.ground = None
                P.dash_t = 0.0
                P.sx, P.sy = 0.78, 1.3
                self.g.audio.play("jump", 0.7)
                self.parts.burst(P.cx, P.y + PS, 6, 90, 0.35, 3, self.theme["accent"])
            elif P.wall and "wall" in ab:
                P.vy = WALL_VY
                P.vx = -P.wall * WALL_VX
                P.jbuf = 0
                P.face = -P.wall
                P.wall = 0
                P.jflag = True
                P.dj_used = False
                P.lock = 0.08
                P.sx, P.sy = 0.8, 1.25
                self.shake = 4
                self.g.audio.play("wall", 0.7)
                self.parts.burst(P.cx, P.cy, 10, 140, 0.4, 4, self.theme["accent"])
            elif "double" in ab and not P.dj_used and P.ground is None:
                P.vy = DJ_V
                P.jbuf = 0
                P.dj_used = True
                P.jflag = True
                P.sx, P.sy = 0.85, 1.2
                self.g.audio.play("double", 0.7)
                self.parts.ring(P.cx, P.cy, 12, 180, 0.5, 4, (200, 220, 255))
                P.glow = 0.6

        if "dash" in ab and P.dash_req > 0 and P.dash_cd <= 0 and P.dash_t <= 0:
            P.dash_req = 0
            P.dash_t = DASH_T
            P.dash_cd = DASH_CD
            P.dash_dir = P.face
            P.vy = min(P.vy * 0.3, 100)
            P.slam = False
            self.g.audio.play("dash")
            self.shake = 6
            self.parts.burst(P.cx, P.cy, 14, 200, 0.4, 5, self.theme["accent"])

        if P.dash_t > 0:
            P.dash_t -= dt
            P.vx = DASH_V * P.dash_dir
            P.vy = 0
            if random.random() < 0.5:
                self.parts.emit(P.cx, P.cy, -P.dash_dir * 120, random.uniform(-40, 40), 0.35, 4,
                                self.theme["accent"])

        if "power" in ab and P.slam_req > 0 and P.ground is None and not P.slam and P.dash_t <= 0:
            P.slam_req = 0
            P.slam = True
            P.vy = SLAM_V
            self.g.audio.play("power", 0.6)
            self.parts.burst(P.cx, P.cy, 10, 80, 0.4, 4, (255, 100, 200))

        if P.slam:
            P.vy = SLAM_V
            if random.random() < 0.4:
                self.parts.emit(P.cx + random.uniform(-8, 8), P.y + PS, 0, -60, 0.3, 3, (255, 100, 200))

        if P.dash_t <= 0:
            if d:
                target = d * RUN
                accel = ACC_G if P.ground else ACC_A
                if P.ground and P.ground.kind == "ice":
                    accel = ICE_ACC
                P.vx = approach(P.vx, target, accel * dt)
                if P.vx * d < 0 and P.ground:
                    P.vx = approach(P.vx, 0, FRIC_G * dt * 2)
            else:
                fr = FRIC_G
                if P.ground and P.ground.kind == "ice":
                    fr = ICE_FRIC
                if P.ground is None:
                    fr *= 0.35
                P.vx = approach(P.vx, 0, fr * dt)

        if P.wall and P.ground is None and P.vy > WALL_SLIDE and P.dash_t <= 0:
            P.vy = min(P.vy, WALL_SLIDE)
            if random.random() < 0.15:
                self.parts.emit(P.cx + P.wall * (PS // 2), P.cy, -P.wall * 30, -30, 0.4, 2,
                                self.theme["accent"])

        if wx:
            P.vx = clamp(P.vx + wx * dt, -RUN * 2, RUN * 2)

        if P.dash_t <= 0 and not P.slam:
            P.vy = min(P.vy + GRAV * dt, TERM)

        if P.move_x(P.vx * dt, solids):
            if P.dash_t <= 0:
                P.vx = 0
        res = P.move_y(P.vy * dt, solids)

        P.ground = None
        if res:
            kind, pl = res
            if kind == "down":
                P.ground = pl
                P.coyote = COYOTE
                P.dj_used = False
                if P.slam:
                    P.slam = False
                    P.vy = SLAM_BOUNCE
                    self.shake = 12
                    self.g.audio.play("power")
                    self.parts.ring(P.cx, P.y + PS, 22, 300, 0.6, 6, (255, 100, 200))
                    self.parts.burst(P.cx, P.y + PS, 16, 220, 0.5, 5, (255, 100, 200))
                    self.fx.flash((255, 120, 220), 90)
                    P.sx, P.sy = 1.4, 0.6
                else:
                    if P.vy > 200:
                        self.g.audio.play("land", 0.4)
                        self.parts.burst(P.cx, P.y + PS, 6, 80, 0.3, 3, (200, 210, 230))
                        P.sx, P.sy = 1.2, 0.8
                    P.vy = 0
                if pl.kind == "spring":
                    P.vy = SPRING_V
                    P.ground = None
                    P.coyote = 0
                    P.jflag = False
                    self.g.audio.play("spring")
                    self.shake = 5
                    pl.pulse = 1.0
                    self.parts.burst(P.cx, P.y + PS, 10, 220, 0.5, 4, (255, 220, 80))
                elif pl.kind == "power":
                    P.vy = POWER_V
                    P.ground = None
                    P.coyote = 0
                    P.jflag = False
                    self.g.audio.play("power")
                    self.shake = 8
                    self.parts.burst(P.cx, P.y + PS, 16, 280, 0.6, 5, (255, 100, 200))
                elif pl.kind == "fragile" and pl.state == "idle":
                    pl.state = "crumble"
                    pl.timer = 0.55
                    self.g.audio.play("crack", 0.6)
                    self.parts.burst(pl.rect.centerx, pl.rect.y, 12, 120, 0.6, 4, (170, 130, 100))
                elif pl.kind == "energy" and not pl.used:
                    pl.used = True
                    P.vy = POWER_V
                    P.ground = None
                    self.g.audio.play("spring")
                    self.parts.burst(P.cx, P.cy, 16, 240, 0.5, 5, (80, 240, 255))
            else:
                P.vy = max(P.vy, 0)
                if P.slam:
                    P.slam = False

        for it in lv.items:
            if it.got:
                continue
            dx = it.x - P.cx
            dy = it.y - P.cy
            if dx * dx + dy * dy < (it.r + PS * 0.5) ** 2:
                it.got = True
                self.energy += it.value
                self.collected.add(it.id)
                self.combo += 1
                self.combo_t = 2.5
                if it.kind == "crystal":
                    self.g.audio.play("crystal")
                    self.parts.burst(it.x, it.y, 14, 180, 0.6, 5, (230, 120, 255))
                    self.shake = 4
                else:
                    self.g.audio.play("chime", 0.4)
                    self.parts.burst(it.x, it.y, 5, 80, 0.4, 3, self.theme["accent"])

        self._check_echoes()

        pr = P.rect()
        for i, st in enumerate(lv.stations):
            if st.active:
                continue
            if pr.colliderect(st.rect):
                st.active = True
                st.flash = 1.0
                self.station = i
                self.save_run()
                self.g.audio.play("station")
                self.shake = 3
                self.parts.burst(st.x, st.y - 46, 20, 200, 0.8, 4, lv.theme["accent"])
                self.banner = ("CHECKPOINT", 0.0, 1.2)

        if self.interact and lv.shrine and not lv.shrine.active:
            if abs(P.cx - lv.shrine.x) < 80:
                if self.energy >= lv.shrine.need:
                    lv.shrine.active = True
                    self.abil.add(lv.shrine.ability)
                    if lv.shrine.ability not in self.g.save["abilities"]:
                        self.g.save["abilities"].append(lv.shrine.ability)
                    write_save(self.g.save)
                    self.g.audio.play("unlock")
                    self.parts.burst(lv.shrine.x, lv.shrine.y - 66, 30, 280, 1.0, 5, lv.theme["accent"])
                    self.shake = 6
                    for k, lab, title, hint in ABILITIES:
                        if k == lv.shrine.ability:
                            self.banner = ("UNLOCKED  " + title, 0.0, 3.0)
                            break
                else:
                    self.banner = ("Need %d more energy" % (lv.shrine.need - self.energy), 0.0, 1.6)
                    self.g.audio.play("deny")

        if lv.exit and P.rect().colliderect(lv.exit.rect):
            if self.energy >= lv.need:
                if self.mode == "play":
                    self.mode = "restoring"
                    self.mode_t = 0.0
                    P.vx = P.vy = 0
                    self.g.audio.play("restore")
                    self.shake = 8
                    self.fx.flash((220, 240, 255), 120)
            elif not self.banner:
                self.banner = ("Need %d more energy" % (lv.need - self.energy), 0.0, 1.6)
                self.g.audio.play("deny")

        if self.god:
            if P.cy > lv.kill_y:
                P.vy = min(P.vy, 0)
                P.y = lv.kill_y - 240
        else:
            if P.cy > lv.kill_y or self.collides_hazard():
                self._die()

        P.trail_history.append((P.cx, P.cy))
        if len(P.trail_history) > 12:
            P.trail_history.pop(0)

    def collides_hazard(self):
        P, lv = self.p, self.level
        r = P.rect()
        for s in lv.spikes:
            if r.colliderect(s.hit):
                return True
        for b in lv.barriers:
            if b.active(self.t) and r.colliderect(b.rect):
                return True
        for rot in lv.rotors:
            if rot.hits(self.t, P.cx, P.cy, PS / 2):
                return True
        return False

    def _die(self):
        ex, ey = self.p.cx, self.p.cy
        if all(abs(e["x"] - ex) + abs(e["y"] - ey) > 140 for e in self.echoes):
            self.echoes.append({"x": ex, "y": ey, "t": 0.0})
        self.falls += 1
        self.combo = 0
        self.mode = "dead"
        self.mode_t = 0.0
        self.shake = 14.0
        self.fx.flash((255, 80, 100), 200)
        self.g.audio.play("die")
        self.parts.burst(ex, ey, 30, 280, 0.8, 6, self.theme["accent"])
        self.say(random.choice(FALL_QUOTES), 2.0)

    def _check_echoes(self):
        for e in list(self.echoes):
            dx = e["x"] - self.p.cx
            dy = e["y"] - self.p.cy
            if dx * dx + dy * dy < 40 * 40:
                self.echoes.remove(e)
                self.energy += 3
                self.p.glow = 1.0
                self.parts.burst(e["x"], e["y"], 22, 220, 0.8, 5, (140, 255, 200))
                self.g.audio.play("crystal")
                self.say("Echo absorbed  +3", 1.6)

    def finish_level(self):
        self.mode = "complete"
        self.mode_t = 0.0
        s = self.g.save
        key = str(self.idx)
        first = key not in s["best"]
        best = s["best"].get(key)
        if not best or self.time < best["time"]:
            s["best"][key] = {"time": self.time, "energy": self.energy, "falls": self.falls}
            self.new_best = True
        if self.idx + 1 < 5:
            s["unlocked"] = max(s["unlocked"], self.idx + 2)
        if self.level.shrine and self.level.shrine.active:
            if self.level.shrine.ability not in s["abilities"]:
                s["abilities"].append(self.level.shrine.ability)
        # bank energy for the skins shop
        earned = self.energy + (15 if first else 5)
        self.earned_energy = earned
        s["energy_bank"] = s.get("energy_bank", 0) + earned
        s["run"] = None
        write_save(s)
        self.g.audio.play("victory")
        items = []
        if self.idx < 4:
            items.append(dict(label="Next Level", action=self.next_level))
            items.append(dict(label="Replay", action=self.restart_level))
        else:
            items.append(dict(label="See the Ending", action=lambda: self.g.set_scene(EndingScene(self.g))))
        items.append(dict(label="Main Menu", action=self.to_menu))
        self.menu_done = ListMenu(self.g, items, "m", 52)

    def next_level(self):
        if self.idx < 4:
            self.g.set_scene(PlayScene(self.g, self.idx + 1))
        else:
            self.g.set_scene(EndingScene(self.g))

    def update_camera(self, dt):
        P = self.p
        tx = P.cx - W * 0.42 + P.vx * 0.12
        ty = P.cy - H * 0.55 + P.vy * 0.05
        kx = 1 - (1 - 0.12) ** (dt * 60)
        ky = 1 - (1 - 0.08) ** (dt * 60)
        self.cam[0] = lerp(self.cam[0], tx, kx)
        self.cam[1] = lerp(self.cam[1], ty, ky)
        self.clamp_cam()

    def clamp_cam(self):
        lv = self.level
        self.cam[0] = clamp(self.cam[0], 0, max(0, lv.width - W))
        self.cam[1] = clamp(self.cam[1], lv.min_y - 220, lv.max_y - H + 120)

    def draw(self, surf):
        lv = self.level
        t = self.t
        sx = sy = 0.0
        if self.shake > 0.1 and self.g.save["settings"].get("shake", True):
            sx = random.uniform(-self.shake, self.shake)
            sy = random.uniform(-self.shake, self.shake)
        cam = (self.cam[0] + sx, self.cam[1] + sy)
        self.bg.draw(surf, cam[0], cam[1], t)
        lv.draw(surf, cam, t, self)
        self.draw_echoes(surf, int(cam[0]), int(cam[1]), t)
        cxi, cyi = int(cam[0]), int(cam[1])
        th = self.p.trail_history[:-1]
        for i, (tx, ty) in enumerate(th):
            a = (i + 1) / max(1, len(th))
            r = int(10 * a * a)
            if r > 1:
                col = mixc((0, 0, 0), self.skin["trail"], a * 0.5)
                pygame.draw.circle(surf, col, (int(tx - cxi), int(ty - cyi)), r)
        P = self.p
        if P.spawn_t > 0.35 and self.mode != "dead":
            draw_orb(surf, P.cx - cxi, P.y + PS - cyi, P.sx, P.sy, 1.0, P.vy, t,
                     glow=P.glow, scale=1.0, vx=P.vx, skin=self.skin)
        self.parts.draw(surf, cam)
        surf.blit(self.vig, (0, 0))
        self.fx.speed_lines(surf, P.vx, P.vy)
        danger = clamp(1.0 - (lv.kill_y - P.cy) / 300, 0, 1)
        self.fx.draw(surf, danger)
        self.draw_hud(surf)
        if self.banner:
            text, _, tleft = self.banner
            a = int(255 * clamp(tleft / 0.5, 0, 1))
            glow_text(surf, text, self.g.fonts["l"], (255, 250, 220), self.theme["accent"],
                      (W // 2, 150), alpha=a)
        if self.mode == "complete":
            self.draw_complete(surf)
        if self.paused:
            self.draw_pause(surf)
        if self.intro > 0 and self.mode == "play":
            self.draw_intro(surf)

    def draw_echoes(self, surf, cx, cy, t):
        for e in self.echoes:
            x, y = e["x"] - cx, e["y"] - cy + math.sin(t * 2 + e["x"] * 0.1) * 4
            pulse = 0.6 + 0.4 * math.sin(t * 4 + e["x"])
            r = int(10 + 6 * pulse)
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (140, 255, 200, int(180 * pulse)), (r, r), r, 2)
            pygame.draw.circle(s, (255, 255, 255, int(200 * pulse)), (r, r), 3)
            surf.blit(s, (x - r, y - r))
            add_glow(surf, (x, y), 40, (30, 80, 50))

    def draw_hud(self, surf):
        g = self.g
        lv = self.level
        panel(surf, (12, 12, 232, 46), (6, 10, 26), 190, 12)
        draw_text(surf, "ENERGY", g.fonts["xs"], (140, 160, 200), (26, 22), anchor="topleft")
        draw_text(surf, "%d / %d" % (self.energy, lv.need), g.fonts["m"], lv.theme["accent"],
                  (26, 42), anchor="topleft")
        frac = clamp(self.energy / max(1, lv.need), 0, 1)
        pygame.draw.rect(surf, (20, 30, 50), (120, 26, 110, 8), border_radius=4)
        if frac > 0:
            pygame.draw.rect(surf, lv.theme["accent"], (120, 26, int(110 * frac), 8), border_radius=4)

        x = W // 2 - (len(ABILITIES) * 90) // 2
        for k, lab, title, hint in ABILITIES:
            col = lv.theme["accent"] if k in self.abil else (70, 80, 100)
            panel(surf, (x, 12, 82, 38), (6, 10, 26), 170, 10)
            draw_text(surf, lab, g.fonts["s"], col, (x + 41, 31))
            x += 90

        panel(surf, (W - 232, 12, 220, 46), (6, 10, 26), 190, 12)
        draw_text(surf, "TIME", g.fonts["xs"], (140, 160, 200), (W - 220, 22), anchor="topleft")
        draw_text(surf, fmt_time(self.time), g.fonts["m"], (220, 235, 255), (W - 220, 42), anchor="topleft")
        draw_text(surf, "FALLS", g.fonts["xs"], (140, 160, 200), (W - 108, 22), anchor="topleft")
        draw_text(surf, "%d" % self.falls, g.fonts["m"], (220, 235, 255), (W - 108, 42), anchor="topleft")

        panel(surf, (W - 54, 12, 40, 40), (6, 10, 26), 190, 10)
        pygame.draw.line(surf, (200, 220, 255), (W - 42, 22), (W - 42, 42), 3)
        pygame.draw.line(surf, (200, 220, 255), (W - 34, 22), (W - 34, 42), 3)

        if self.combo >= 3:
            a = int(255 * clamp(self.combo_t / 0.5, 0, 1))
            draw_text(surf, "x%d" % self.combo, g.fonts["l"], (255, 230, 130), (W // 2, 80), alpha=a)

        if self.msg[1] > 0:
            a = int(255 * clamp(self.msg[1] / 0.4, 0, 1))
            draw_text(surf, self.msg[0], g.fonts["m"], (255, 255, 255), (W // 2, 108), alpha=a)

        if lv.shrine and not lv.shrine.active and abs(self.p.cx - lv.shrine.x) < 100:
            txt = "Press E to unlock  (%d / %d)" % (self.energy, lv.shrine.need)
            draw_text(surf, txt, g.fonts["s"], (255, 235, 150), (W // 2, H - 60))

    def draw_pause(self, surf):
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        v.fill((0, 0, 0, 170))
        surf.blit(v, (0, 0))
        glow_text(surf, "PAUSED", self.g.fonts["xl"], (235, 250, 255), (30, 160, 255), (W // 2, 130))
        self.menu_pause.draw(surf, W // 2, 200, self.t)

    def draw_complete(self, surf):
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        v.fill((0, 0, 0, 170))
        surf.blit(v, (0, 0))
        lv = self.level
        glow_text(surf, "RESTORED", self.g.fonts["xl"], (255, 250, 220), lv.theme["accent"], (W // 2, 70))
        draw_text(surf, lv.theme["name"], self.g.fonts["l"], (220, 235, 255), (W // 2, 116))
        draw_text(surf, "Time  " + fmt_time(self.time), self.g.fonts["m"], (200, 220, 250), (W // 2, 172))
        draw_text(surf, "Energy  %d / %d" % (self.energy, lv.total), self.g.fonts["m"], lv.theme["accent"],
                  (W // 2, 202))
        draw_text(surf, "Falls  %d" % self.falls, self.g.fonts["m"], (200, 220, 250), (W // 2, 232))
        draw_text(surf, "+%d energy banked for skins" % self.earned_energy, self.g.fonts["s"],
                  (255, 235, 150), (W // 2, 266))
        if self.new_best:
            draw_text(surf, "NEW BEST", self.g.fonts["s"], (255, 235, 150), (W // 2, 296))
        if self.mode_t > 0.6 and self.menu_done:
            self.menu_done.draw(surf, W // 2, 340, self.t)

    def draw_intro(self, surf):
        a = int(255 * clamp(self.intro / 1.0, 0, 1) * clamp((3.0 - self.intro) / 1.0, 0, 1))
        if a <= 0:
            return
        lv = self.level
        glow_text(surf, lv.theme["name"], self.g.fonts["xl"], (235, 250, 255), lv.theme["accent"],
                  (W // 2, H // 2 - 20), alpha=a)
        draw_text(surf, lv.theme["sub"], self.g.fonts["m"], (190, 205, 235), (W // 2, H // 2 + 30), alpha=a)


# ----------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("REBOUND: The Last Bounce")
        flags = 0 if sys.platform == "emscripten" else pygame.SCALED
        self.screen = pygame.display.set_mode((W, H), flags)
        self.clock = pygame.time.Clock()
        self.save = load_save()
        self.vignette = make_vignette()
        self.fonts = {}
        font_names = "georgia,dejavuserif,liberationserif,cambria,timesnewroman,serif"
        for name, size in (("xxl", 96), ("xl", 56), ("l", 36), ("m", 26), ("s", 18), ("xs", 14)):
            try:
                self.fonts[name] = pygame.font.SysFont(font_names, size)
            except Exception:
                self.fonts[name] = pygame.font.Font(None, size)
        self.audio = Audio(self.save["settings"])
        self._keys = pygame.key.get_pressed()
        self._running = True
        self.scene = MenuScene(self)

    def keys(self):
        return self._keys

    def set_scene(self, scene):
        self.scene = scene

    def quit(self):
        self._running = False

    async def run(self):
        while self._running:
            dt = self.clock.tick(FPS) / 1000.0
            self._keys = pygame.key.get_pressed()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self._running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    if sys.platform != "emscripten":
                        pygame.display.toggle_fullscreen()
                else:
                    self.scene.handle(e)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()
            await asyncio.sleep(0)
        write_save(self.save)
        pygame.quit()


async def main():
    if "--check" in sys.argv:
        for i in range(5):
            build_level(i, check=True)
        print("All levels OK")
        return
    await Game().run()


if __name__ == "__main__":
    asyncio.run(main())
