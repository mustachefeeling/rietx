#!/bin/sh
# Build the mystmd spike as static HTML under /docs/<version>/.
set -e
S=$(cd "$(dirname "$0")/.." && pwd)
export PATH=$HOME/.nvm/versions/node/v22.15.0/bin:$PATH
MYST=$S/tools/myst/node_modules/.bin/myst
chmod +x $S/myst/plugins/rx.py
rm -rf $S/site-myst
mkdir -p $S/myst/figures $S/myst/parts
cp $S/../../manual/using/figures/angular-signatures-*.png $S/myst/figures/
for v in ${VERSIONS:-dev 1.9}; do
  if [ "$v" = dev ]; then printf "Dev, not yet released · [stable](/docs/stable/)\n" > $S/myst/parts/version.md; else printf "%s · [dev](/docs/dev/)\n" $v > $S/myst/parts/version.md; fi
  (cd $S/myst && rm -rf _build && start=$(date +%s) \
    && BASE_URL=/docs/$v $MYST build --html --strict ${MYST_FLAGS} \
    && echo "built $v in $(( $(date +%s) - start )) s")
  mkdir -p $S/site-myst/docs
  cp -R $S/myst/_build/html $S/site-myst/docs/$v
done
ln -s 1.9 $S/site-myst/docs/stable
echo done
