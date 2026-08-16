"""The name-bearing literals, in one place (WP-1062).

Every string in this package that spells the *distribution*, the on-disk
*format tokens* or the *state directory* lives here and nowhere else.  The
module imports nothing — not even from this package — so anything may import
it: the forward model, the GUI server, ``docs/manual/conf.py``, the tests.

Two rules the values below follow, and they point in opposite directions:

* **The brand tokens track the distribution.**  :data:`DIST_NAME` is what
  ``importlib.metadata.version`` is asked for, and :data:`STATE_DIR_NAME`,
  :data:`STATE_DIR_ENV`, :data:`AGENT_TOOL_NAME`, :data:`DATA_PACKAGE`,
  :data:`SERVER_TOKEN` and :data:`DOCS_URL` are user-visible spellings of the
  same name.  Renaming the package moves all seven together.
* **The format tokens do not.**  :data:`PROJECT_SUFFIX`, :data:`TEXTDOC_MAGIC`
  and :data:`PROFILE_FORMAT_KEY` name *versioned contracts*
  (``schemas.project.PROJECT_FORMAT_VERSION``, ``gui.textdoc.FORMAT_VERSION``,
  ``io.instrument_profile.FORMAT_VERSION``), and a contract must not move
  because a brand did.  Keeping them free of the brand is what stops a future
  rename from being a format break, and stops a format inheriting whatever
  ambiguity the brand acquires.

**Import these; never spell them.** ``tests/test_no_stale_name.py`` fails on a
reintroduction of an *old* name, and it greps only old ones: an audit against
the current name would fail on the many places that legitimately say it — the
README, this module, ``prog=`` strings, every ``:func:`~rietx.…``` cross
reference.  The consequence is that a freshly hardcoded ``"rietx"``, ``".rex"``
or ``"rxt"`` is **invisible to every test in the suite**.  Nothing but the rule
catches it.

WP-1066 renamed the brand a second time and left every format token below
untouched, which is the second rule above paying for itself one rename after it
was written.  One of the two names it retired is also a phase this software
analyses, so the audit's grep for it has a foreseeable expiry; the test's own
docstring holds that argument, because spelling the token here would put this
module on the audit's allowlist and blind it to exactly the stale literal it
exists to catch.
"""

#: The distribution name — ``importlib.metadata.version`` argument, the
#: ``pip install 'NAME[extra]'`` hints, and the manual's ``release``.
DIST_NAME = "rietx"

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
STATE_DIR_NAME = ".rietx"
STATE_DIR_ENV = "RIETX_STATE_DIR"

#: Default ``name`` of the LLM tool definition wrapping ``refine_json``.
AGENT_TOOL_NAME = "rietx_refine"

#: Import path of the bundled data package (scattering factors, attenuation
#: and dispersion tables), read through ``importlib.resources``.
DATA_PACKAGE = "rietx.data"

#: Short token for ephemeral server-side names a person may see in a path or a
#: stack trace: the upload staging directory and the run thread.
SERVER_TOKEN = "rietx"

#: Root of the hosted documentation (GitHub Pages, WP-1003), no trailing
#: slash.  The agent tool description appends ``/AGENT_PROTOCOL.md``; the
#: README and ``pyproject.urls`` quote it.  A brand token: a rename or a
#: hosting move changes it here and nowhere else.
DOCS_URL = "https://yue-here.github.io/rietx"
