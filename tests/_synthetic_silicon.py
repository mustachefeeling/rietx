"""Forward-modelled silicon for tests that need a pattern with a known answer.

numpy and gemmi's IT92 form factors only, no measured data: Cu Kα1 + Kα2
(intensity ratio 0.5), pseudo-Voigt lines, Lorentz-polarisation, Poisson counting
noise (seed 1), a = 5.43114 Å.  ``kind`` is the background: ``"flat"`` a gently
decaying one, ``"steep"`` one falling from ~2300 to ~800 counts between 11 and
22°.
"""

from __future__ import annotations

import gemmi
import numpy as np

import rietx as rx

A_SI = 5.43114


def silicon_pattern(kind: str) -> rx.PatternData:
    l1, l2, r21 = 1.540598, 1.544426, 0.5
    tt = np.arange(10.0, 110.0, 0.0167)
    y = np.zeros_like(tt)
    it92 = gemmi.Element("Si").it92

    def f0(s2):
        return sum(it92.a[i] * np.exp(-it92.b[i] * s2) for i in range(4)) + it92.c

    sites = [(0, 0, 0), (.5, .5, 0), (.5, 0, .5), (0, .5, .5), (.25, .25, .25),
             (.75, .75, .25), (.75, .25, .75), (.25, .75, .75)]
    for h in range(-8, 9):
        for k in range(-8, 9):
            for ell in range(0, 9):
                if (h, k, ell) == (0, 0, 0):
                    continue
                d = A_SI / np.sqrt(h * h + k * k + ell * ell)
                F = sum(np.exp(2j * np.pi * (h * x + k * yy + ell * z))
                        for x, yy, z in sites)
                if abs(F) < 1e-6:
                    continue
                for lam, w in ((l1, 1.0), (l2, r21)):
                    s = lam / (2 * d)
                    if s >= 1:
                        continue
                    th = np.arcsin(s)
                    t2 = np.degrees(2 * th)
                    lp = (1 + np.cos(2 * th) ** 2) / (np.sin(th) ** 2 * np.cos(th))
                    intensity = (w * abs(F) ** 2 * f0((1 / (2 * d)) ** 2) ** 2 * lp
                                 * np.exp(-2 * 0.46 * (1 / (2 * d)) ** 2))
                    fw = np.sqrt(0.0016 + 0.00002 * np.tan(th) ** 2
                                 + 0.00004 / np.cos(th) ** 2)
                    g = np.exp(-4 * np.log(2) * (tt - t2) ** 2 / fw ** 2)
                    lo = 1 / (1 + 4 * (tt - t2) ** 2 / fw ** 2)
                    y += intensity * (0.4 * lo + 0.6 * g)
    y = y / y.max() * 66000
    if kind == "flat":
        bg = 800 + 1400 * np.exp(-(tt - 10) / 20.0) + 300 * np.exp(-(tt - 10) / 80.0)
    else:
        bg = 780 + 1500 / (1 + np.exp((tt - 16.8) / 2.6)) + 300 * np.exp(-(tt - 10) / 80.0)
    counts = np.random.default_rng(1).poisson(y + bg).astype(float)
    return rx.PatternData(two_theta=tt.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())
