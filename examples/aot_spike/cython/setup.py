"""WP-1939 spike: build the Cython kernels twice, to measure FMA contraction.

``RIETX_SPIKE_CONTRACT=off`` adds ``-ffp-contract=off`` and builds
``rietx_kernels_cy``; unset, the compiler's default stands and the module is
``rietx_kernels_cy_default``, so both import into one process.

Run from this directory: ``python setup.py build_ext --inplace``.
"""

import os
import shutil

from Cython.Build import cythonize
from setuptools import Extension, setup

contract = os.environ.get("RIETX_SPIKE_CONTRACT", "default")
name = "rietx_kernels_cy" if contract == "off" else "rietx_kernels_cy_default"
flags = ["-O3"] + (["-ffp-contract=off"] if contract == "off" else [])
# ``RIETX_SPIKE_ABI3=1``: the Limited API for 3.11+, Cython's route to one
# wheel per platform (typed memoryviews need 3.11 under it).
abi3 = os.environ.get("RIETX_SPIKE_ABI3") == "1"
macros = []
if abi3:
    name += "_abi3"
    macros = [("Py_LIMITED_API", "0x030B0000")]
os.makedirs("build", exist_ok=True)
src = os.path.join("build", f"{name}.pyx")
shutil.copyfile("rietx_kernels_cy.pyx", src)
setup(
    name=name,
    ext_modules=cythonize(
        [Extension(name, [src], extra_compile_args=flags, define_macros=macros,
                   py_limited_api=abi3)],
        compiler_directives={"language_level": 3}),
)
