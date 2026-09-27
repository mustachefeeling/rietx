# WP-1469 spike

Three scripts measured the question the WP answers: can a Python renderer
with no new dependency draw the structure viewer's geometry fast enough for
an agent to iterate? Run each from the repo root. The two renderers take an
output directory for their PNGs.

| Script | What it measures |
|---|---|
| `pypi.py` | Wheel size and platforms of 16 Python renderers, from PyPI's JSON API |
| `spike.py` | A numba ray-caster of `structure3d.build()`, and its timings |
| `mpl_baseline.py` | The same scene drawn by matplotlib, back to front, and its timings |

## The renderers on PyPI

Measured 2026-09-27 from `pypi.py`. Sizes are the largest cp312 or
pure-python wheel per platform, in MB.

| Package | Version | Linux | macOS | Windows | Note |
|---|---|---|---|---|---|
| matplotlib | 3.11.2 | 10.7 | 9.5 | 9.3 | plus its own dependencies |
| pillow | 12.3.0 | 6.9 | 5.3 | 7.2 | |
| pycairo | 1.29.1 | - | - | 0.8 | Linux and macOS build against a system cairo |
| cairocffi | 1.7.1 | 0.1 | 0.1 | 0.1 | needs a system libcairo |
| skia-python | 144.0.post2 | 14.4 | 12.2 | 10.9 | no sdist |
| resvg-py | 0.5.0 | 1.5 | 1.3 | 1.2 | SVG to PNG only |
| moderngl | 5.12.0 | 0.3 | 0.1 | 0.1 | needs an OpenGL context |
| vtk | 9.7.0 | 139.7 | 111.0 | 80.4 | pyvista rides on it |
| vispy | 0.17.0 | 2.7 | 1.7 | 1.6 | needs an OpenGL context |
| pyrender | 0.1.45 | 1.2 | 1.2 | 1.2 | last release 2021-02 |
| fresnel | - | - | - | - | the PyPI name is an unrelated 2015 package |

## The ray-caster

`spike.py` is 230 lines. It draws balls or ellipsoids as exact quadrics,
bond halves as finite cylinders and the cell edges as thin cylinders, with
the GUI shader's light, shading and ring rule (`gui/src/lib/gl3d.ts`). It
has no polyhedra, no text and no FLAT_AXIS floor. It antialiases by box
filtering a supersampled z-buffer, and writes the PNG with `zlib`.

Measured 2026-09-27 on NAC (`tests/data/cod_1000236.cif`, `aniso=True`: 185
atoms, 255 bonds), an Apple M4 at load average 4, `[dev]` venv, numba 0.67.
Three renders each, as a range over two runs of the script.

| | ball | ellipsoid |
|---|---|---|
| `build()` | 20-24 ms | |
| first render, compiling | 0.64-0.76 s | |
| 1000 px, 2× | 97-108 ms | 85-87 ms |
| 2000 px, 2× | 375-448 ms | 329-363 ms |
| 3000 px, 1× | 83-92 ms | 59-63 ms |
| 3000 px, 2× | 0.83-0.96 s | 0.73-0.77 s |
| PNG write, 1000 / 3000 px | 21-22 / 132-138 ms | 18 / 121-124 ms |

At 3000 px and 2× the box filter is most of the cost. On its own it takes
514-521 ms, a numpy `mean` over a 6000 × 5656 × 3 array in float64.
Allocating the buffers takes 20-33 ms. Ray-casting is the remaining 0.3 s.

## The matplotlib baseline

`mpl_baseline.py` draws each atom as a flat disc and each bond half as a
flat quadrilateral, sorted by depth, one `PatchCollection`.

| | PNG | SVG | PDF |
|---|---|---|---|
| 1000 px | 39-584 ms | 32-54 ms | 43-2298 ms |
| 3000 px | 152-190 ms | 32-35 ms | 37-63 ms |

`import matplotlib.pyplot` took 181-186 ms warm and 5.4 s cold. The wide
ranges in the first row are the machine; the first render of each format
pays for font loading.

The picture has two faults the ray-caster has not. It is flat. And a bond
sorted by its midpoint's depth is drawn over a ball it passes behind, in
several places on NAC.
