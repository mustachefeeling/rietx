#!/bin/sh
# Build the Sphinx spike as two versions under site-sphinx/docs/, with a switcher and a redirect.
set -e
S=$(cd "$(dirname "$0")/.." && pwd)
OUT=$S/site-sphinx/docs
rm -rf $S/site-sphinx $S/sphinx/_build
mkdir -p $S/sphinx/figures
cp $S/../../manual/using/figures/angular-signatures-*.png $S/sphinx/figures/
for v in dev 1.9; do
  start=$(date +%s)
  # -d keeps the doctree pickles out of the served site (the default is $OUT/$v/.doctrees).
  DOCS_VERSION=$v $S/venv/bin/python -m sphinx -W -q -E -b html -d $S/sphinx/_build/doctrees-$v $S/sphinx $OUT/$v
  echo "built $v in $(( $(date +%s) - start )) s"
done
ln -s 1.9 $OUT/stable
cat > $OUT/switcher.json <<'EOF'
[
  {"name": "dev", "version": "dev", "url": "/docs/dev/"},
  {"name": "1.9 (stable)", "version": "1.9", "url": "/docs/stable/", "preferred": true}
]
EOF
cat > $OUT/index.html <<'EOF'
<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=stable/">
<link rel="canonical" href="stable/"><title>Redirecting</title>
EOF
echo done
