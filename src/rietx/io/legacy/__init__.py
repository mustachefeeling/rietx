"""Legacy instrument-file layouts: documented deviations, read only on request.

A **legacy layout** is a file that deviates from a *published* format in a way
the format's documentation does not describe, observed in files a facility
actually wrote.  The strict readers refuse such a file by name, and they stay
strict; a reader in this package accepts exactly the deviations it names and
nothing else, and only when a caller asks for it by name — nothing dispatches
here, no format registry lists it, and a strict refusal at most points at it.

Three rules every module here keeps:

* **Integrated but independent.**  A legacy reader reuses the strict reader's
  record splitting, column checks and refusals by *calling* them, never by
  copying them, and it produces the same schema the strict reader does; a file
  the strict reader accepts is handed to it and comes back unchanged.  It never
  touches ``model/``: the physics is the rebuilt package's, and a deviation the
  model cannot express is refused, naming what the model would need.
* **Each deviation is named and reported.**  Every accepted deviation emits a
  ``Diagnostic`` saying what was restated and on what evidence.
* **The evidence is stated, not implied.**  A legacy layout comes from the
  package's own files, checked against another program's *output* run as a
  black box; which program, which version and which calls are recorded in the
  module that reads it.
"""

from .lansce_iparm import read_lansce_iparm

__all__ = ["read_lansce_iparm"]
