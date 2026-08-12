"""The name-bearing literals, in one place (WP-1062).

Every string in this package that spells the *distribution*, the on-disk
*format tokens* or the *state directory* lives here and nowhere else.  The
module imports nothing — not even from this package — so anything may import
it: the forward model, the GUI server, ``docs/manual/conf.py``, the tests.

Two rules the values below follow, and they point in opposite directions:

* **The brand tokens track the distribution.**  :data:`DIST_NAME` is what
  ``importlib.metadata.version`` is asked for, and :data:`STATE_DIR_NAME`,
  :data:`STATE_DIR_ENV`, :data:`AGENT_TOOL_NAME`, :data:`DATA_PACKAGE` and
  :data:`SERVER_TOKEN` are user-visible spellings of the same name.  Renaming
  the package moves all six together.
* **The format tokens do not.**  :data:`PROJECT_SUFFIX`, :data:`TEXTDOC_MAGIC`
  and :data:`PROFILE_FORMAT_KEY` name *versioned contracts*
  (``schemas.project.PROJECT_FORMAT_VERSION``, ``gui.textdoc.FORMAT_VERSION``,
  ``io.instrument_profile.FORMAT_VERSION``), and a contract must not move
  because a brand did.  Keeping them free of the brand is what stops a future
  rename from being a format break, and stops a format inheriting whatever
  ambiguity the brand acquires.
"""

#: The distribution name — ``importlib.metadata.version`` argument, the
#: ``pip install 'NAME[extra]'`` hints, and the manual's ``release``.
DIST_NAME = "anatase"

#: Conventional suffix of a project *directory* (``project.py``).  Not
#: enforced there; the GUI wizard is what actually offers it.
PROJECT_SUFFIX = ".rex"

#: First word of the project text document's header line, ``<magic> N``, and
#: its file extension (``gui/textdoc.py``, and the CodeMirror language on the
#: frontend side, which cannot import this and carries its own copy).
TEXTDOC_MAGIC = "rxt"

#: Tag identifying an instrument-profile JSON file
#: (``io/instrument_profile.py``).
PROFILE_FORMAT_KEY = "instrument_profile"

#: Per-user state the GUI keeps outside any project — the recent list and the
#: theme — under ``$HOME``, with the env var overriding it so tests and a
#: sandboxed build never touch a real home directory.
STATE_DIR_NAME = ".anatase"
STATE_DIR_ENV = "ANATASE_STATE_DIR"

#: Default ``name`` of the LLM tool definition wrapping ``refine_json``.
AGENT_TOOL_NAME = "anatase_refine"

#: Import path of the bundled data package (scattering factors, attenuation
#: and dispersion tables), read through ``importlib.resources``.
DATA_PACKAGE = "anatase.data"

#: Short token for ephemeral server-side names a person may see in a path or a
#: stack trace: the upload staging directory and the run thread.
SERVER_TOKEN = "anatase"
