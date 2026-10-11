"""What a CI leg ran on, printed by one module that every leg calls.

    python -m tests.record_environment

The interpreter, the platform, numpy's build and the two probes an indexing
speed-up is gated on (WP-1509, WP-1519).  Each probe picks an exact, slower
path on a platform whose BLAS or LAPACK fails it, and the tests that ask more
of it skip.  The suite runs at ``-q`` without ``-rs``, so a skip is never
named, and these lines are the only record of which path a leg took.  The
nightly once pasted the probe line into three jobs, where a third probe would
have needed three identical edits and a missed one would have dropped that
platform's answer silently (WP-1547).
"""

import platform
import sys

import numpy
import scipy

from rietx.indexing.engines import row_local_product
from rietx.indexing.reduce import stacked_pinv_exact

print(sys.version, sys.platform, platform.machine())
print("numpy", numpy.__version__, "scipy", scipy.__version__)
numpy.show_config()
print("row_local_product", row_local_product(), "stacked_pinv_exact", stacked_pinv_exact())
