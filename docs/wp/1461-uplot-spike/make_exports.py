"""Write today's `write_html` page from the prototype's arrays, for a size and load-time comparison."""
import json
import pathlib
import sys

import numpy as np
from rietx.viz.html import figure_from_arrays

here = pathlib.Path(sys.argv[1])
a = json.loads((here / "arrays.json").read_text())
fig = figure_from_arrays(np.asarray(a["x"]), np.asarray(a["obs"]), np.asarray(a["calc"]),
                         np.asarray(a["bkg"]), a["ticks"], title="synthetic, 22 003 points")
out = here / "plotly_export.html"
fig.write_html(str(out), include_plotlyjs=True, full_html=True, config={"displaylogo": False})
print(out.name, out.stat().st_size)
