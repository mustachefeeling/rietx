# WP-1975 toolchain spike

The same three pages built in Sphinx with pydata-sphinx-theme and in mystmd: the front page, one
guide and one Theory page. The results and the choice are in WP-1975 § I. Nothing here is part
of the manual's build or of the test suite.

Set up once, from this directory:

```sh
uv venv venv --python cpython-3.12-macos-aarch64-none
uv pip install --python venv/bin/python sphinx myst-parser pydata-sphinx-theme sphinx-design \
    sphinxcontrib-bibtex sphinx-llms-txt sphinx-markdown-builder playwright -e ../../..
npm --prefix tools/myst install mystmd@1.11.0       # node 22
```

Vale 3.24.0 is a single binary from the errata-ai/vale releases page. Put it at `tools/vale`,
then run `tools/vale --config=vale/vale.ini sync` once to fetch the Microsoft package.

Build and look:

```sh
sh tools/build_sphinx.sh            # site-sphinx/docs/{dev,1.9,stable}, switcher.json, redirect
sh tools/build_myst.sh              # site-myst/docs/{dev,1.9,stable}
cp site-sphinx/docs/index.html site-myst/docs/
venv/bin/python tools/shots.py      # shots/<toolchain>-<page>-<scheme>-<width>.png
venv/bin/python tools/switcher.py   # the Sphinx switcher, banner and redirect
tools/vale --config=vale/vale.ini sphinx/index.md sphinx/guides/calibrate.md sphinx/theory/profiles.md
```

The `myst/` pages differ from the `sphinx/` ones only where mystmd's syntax does. Run
`diff -r sphinx myst` to see every difference.
