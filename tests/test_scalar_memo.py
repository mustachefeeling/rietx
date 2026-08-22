"""The scalar-chain memo in ``CompiledModel.phase_peaks`` (WP-1109).

``_peak_chain_column`` re-runs the whole of ``phase_peaks`` once per Jacobian
column, at a θ where most of its blocks did not move: a column perturbing a
Biso leaves the cell block alone, one perturbing a profile width leaves both
the cell block and |F|² alone.  Each block is therefore memoised on the small
set of decoded scalars it reads, reused iff they compare bit-equal — the
contract ``_cached_fcj_nodes`` already uses one rank down.

The failure mode this file is written against is a **key narrower than its
block**: the memo then hands back a stale array and the fit quietly optimises
the wrong model.  So the main test does not check the keys by reading them.  It
perturbs every parameter the table carries, one at a time, and demands the
memoised model agree bit-for-bit with a model that has no cache at all.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    AnisoU,
    Atom,
    Cell,
    Phase,
    PreferredOrientation,
    StephensStrain,
    Structure,
)


def _rich_models():
    """A model that exercises every block the memo covers at once.

    Bragg-Brentano so the displacement and transparency shifts are live, a Cu
    Kα doublet so the per-line blocks have more than one entry, and a first
    phase carrying preferred orientation, anisotropic strain and an
    anisotropic ADP.  A single-block model would let a narrow key pass.
    """
    rutile_cell = Cell(a=Parameter(value=4.5941), b=Parameter(value=4.5941),
        c=Parameter(value=2.9589), alpha=Parameter(value=90.0),
        beta=Parameter(value=90.0), gamma=Parameter(value=90.0))
    rutile = Phase(
        name="rutile", space_group="P42/mnm", cell=rutile_cell,
        atoms=[
            # anisotropic, so the |F|² key has to reach the six U^ij too
            Atom(label="Ti", species="Ti", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0),
                 biso=Parameter(value=0.5, vary=False),
                 aniso=AnisoU.isotropic(0.006, rutile_cell)),
            Atom(label="O", species="O", x=Parameter(value=0.3053),
                 y=Parameter(value=0.3053), z=Parameter(value=0.0),
                 biso=Parameter(value=0.7)),
        ],
        preferred_orientation=PreferredOrientation(axis=(0, 0, 1),
                                                   r=Parameter(value=0.9)),
        microstrain=StephensStrain.isotropic(800.0, rutile_cell),
    )
    rutile.scale.value = 1e-3
    rutile.lor_size.value = 0.02
    rutile.gauss_size.value = 0.01

    fluorite = Phase(
        name="fluorite", space_group="Fm-3m",
        cell=Cell(a=Parameter(value=5.4626), b=Parameter(value=5.4626),
                  c=Parameter(value=5.4626), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[
            Atom(label="Ca", species="Ca", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0),
                 biso=Parameter(value=0.6)),
            Atom(label="F", species="F", x=Parameter(value=0.25),
                 y=Parameter(value=0.25), z=Parameter(value=0.25),
                 biso=Parameter(value=0.9)),
        ],
    )
    fluorite.scale.value = 5e-4

    structure = Structure(phases=[rutile, fluorite])
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 8e-3
    ins.profile.u.value = 2e-3
    ins.profile.x.value = 5e-3
    ins.profile.y.value = 4e-3
    ins.geometry.sample_displacement.value = 0.01
    ins.geometry.sample_transparency.value = 0.005
    tt = np.arange(20.0, 90.0, 0.05)
    pattern = rx.PatternData(two_theta=tt.tolist(),
                             intensity=np.full(tt.shape, 100.0).tolist())
    return structure, ins, pattern


@pytest.fixture(scope="module")
def rich():
    structure, ins, pattern = _rich_models()
    table = ParameterTable(structure, ins)
    cached = compile_model(structure, ins, pattern, mode="rietveld")
    plain = compile_model(structure, ins, pattern, mode="rietveld")
    for cp in plain.phases:          # the same model with the memo denied
        cp.scalar_cache = None
    return cached, plain, table


def _same(a, b) -> bool:
    return all(np.array_equal(x, y)
               for pa, pb in zip(a, b, strict=True)
               for x, y in zip(pa, pb, strict=True))


def test_the_memo_is_allocated_and_actually_used(rich):
    cached, plain, table = rich
    assert all(cp.scalar_cache == {} for cp in cached.phases)
    values = table.decode(table.x0())
    cached.phase_peaks(0, values)
    filled = cached.phases[0].scalar_cache
    # every block this model exercises has a slot
    assert set(filled) == {"cell", "f2", "po", "aniso", "pos", "widths",
                           "lp", "abs"}
    assert all(cp.scalar_cache is None for cp in plain.phases)


def _paths(table):
    return [e.path for e in table.entries]


def test_every_parameter_defeats_the_memo_it_should(rich):
    """The one that matters.  For each parameter in turn: prime the memo at the
    base point, perturb that parameter alone, and demand the memoised model
    agree bit-for-bit with a model that has no memo.

    A key too narrow for its block fails here and nowhere else — the arrays
    returned would be the base point's, which is a plausible-looking answer to
    every tolerance-based check.  Written over the whole table rather than a
    chosen list, so a parameter added later is covered on arrival.
    """
    cached, plain, table = rich
    base = table.decode(table.x0())
    paths = _paths(table)
    assert len(paths) > 40, f"fixture too thin to discriminate ({len(paths)})"

    for path in paths:
        for ip in range(len(cached.phases)):
            perturbed = dict(base)
            v = perturbed[path]
            perturbed[path] = v + (1e-4 * abs(v) if v else 1e-4)
            cached.phase_peaks(ip, base)          # prime at the base point
            got = cached.phase_peaks(ip, perturbed)
            want = plain.phase_peaks(ip, perturbed)
            assert _same(got, want), (
                f"stale memo for phase {ip} after perturbing {path!r} — some "
                f"block's key does not read it")


def test_a_repeated_call_returns_the_same_numbers(rich):
    """A hit must be a reuse, not a re-derivation: equal inputs give bit-equal
    outputs either way, which is what keeps the backend goldens identical."""
    cached, plain, table = rich
    values = table.decode(table.x0())
    first = cached.phase_peaks(0, values)
    second = cached.phase_peaks(0, values)
    assert _same(first, second)
    assert _same(first, plain.phase_peaks(0, values))


def test_a_whole_fit_is_bit_identical_with_the_memo_denied():
    """End to end, because the per-call check above cannot see an error that
    only compounds: a full staged refinement with the memo and without it must
    reach the same numbers, not merely close ones."""
    structure, ins, pattern = _rich_models()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile", ["instrument.profile.w", "instrument.profile.u"]),
        rx.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])

    def run(deny_memo: bool):
        import rietx.model.forward as fwd

        original = fwd.compile_model
        if deny_memo:
            def no_memo(*args, **kwargs):
                model = original(*args, **kwargs)
                for cp in model.phases:
                    cp.scalar_cache = None
                return model
            fwd.compile_model = no_memo
        try:
            s = structure.model_copy(deep=True)
            i = ins.model_copy(deep=True)
            return rx.Refinement(s, i).fit(pattern, plan=plan)
        finally:
            fwd.compile_model = original

    with_memo = run(False)
    without = run(True)
    assert with_memo.statistics.rwp == without.statistics.rwp
    for a, b in zip(with_memo.parameters, without.parameters, strict=True):
        assert a.path == b.path
        assert a.value == b.value, a.path
        assert a.stderr == b.stderr, a.path


def test_memoised_arrays_are_read_only(rich):
    """Before the memo every call allocated its own arrays, so a consumer
    writing into one hurt nobody.  Now the same array is shared across calls,
    ``phase_peaks`` is public, and an in-place write would poison every later
    evaluation of that phase without raising anything.  Freezing costs nothing
    per call and turns that into a ValueError naming the write."""
    cached, plain, table = rich
    values = table.decode(table.x0())
    pos, w1, w2, intensity = cached.phase_peaks(0, values)[0]
    for arr, name in ((pos, "position"), (w1, "w1"), (w2, "w2")):
        assert not arr.flags.writeable, name
        with pytest.raises(ValueError):
            arr[0] = 0.0
    # the intensity is rebuilt every call and carries no such constraint
    assert intensity.flags.writeable
    # and a model without the memo hands back ordinary writeable arrays
    assert plain.phase_peaks(0, values)[0][0].flags.writeable


# -- the key is a thunk, and why (WP-1109) --------------------------------

def test_the_memo_never_builds_its_key_off_the_numpy_path(rich, monkeypatch):
    """Every memo key is built by calling ``float()`` on decoded values, and
    under a trace those values are tracers where ``float()`` raises.  So the
    key must be computed **only** when the memo is live — which is why
    ``_memo`` takes a thunk rather than a tuple.

    Passing the key itself evaluated it at the call site, before the backend
    test inside ``_memo``, and took the entire jax matrix down (21 rows across
    ``test_backend_jax`` and ``test_cross_backend``) on a change whose numpy
    runs were green, because a ``[dev]``-only venv skips every jax row.  Pinned
    here on numpy so the contract cannot be tidied back into an eager tuple by
    someone who cannot run the jax rows either.
    """
    import rietx.model.forward as fwd

    cached, plain, _table = rich

    def exploding_key():
        raise AssertionError("memo key built off the numpy path")

    # (a) no cache allocated at all
    assert plain.phases[0].scalar_cache is None
    assert plain._memo(plain.phases[0], "cell", exploding_key,
                       lambda: "built") == "built"

    # (b) cache allocated, but the active backend is not numpy — the case that
    # broke, reached here without needing jax installed
    class _NotNumpy:
        name = "jax"

    monkeypatch.setattr(fwd, "get_backend", lambda: _NotNumpy())
    assert cached.phases[0].scalar_cache is not None
    assert cached._memo(cached.phases[0], "cell", exploding_key,
                        lambda: "built") == "built"


def test_the_memo_does_build_its_key_when_it_is_live(rich):
    """The other side of it: on numpy with a cache, the key is built and used,
    so the test above cannot pass by the memo simply never running."""
    cached, _plain, _table = rich
    built = []

    def counted_key():
        built.append(1)
        return (1.0, 2.0)

    assert cached._memo(cached.phases[0], "probe", counted_key,
                        lambda: "first") == "first"
    assert len(built) == 1
    # same key ⇒ a hit, and the thunk is consulted again to find that out
    assert cached._memo(cached.phases[0], "probe", counted_key,
                        lambda: "second") == "first"
    assert len(built) == 2


def test_an_alternation_between_two_states_stops_rebuilding(rich):
    """The WP-1121 shape: a Jacobian column asks for the expansion point, one
    perturbed state, the expansion point again, and so on.

    One key per slot turns that into a rebuild on *every* call — the memo
    answers nothing while still paying for its key — and it is not a corner
    case: the column seam hit 63.6 % of its lookups at depth 1 on the trigger
    cold fit, against 72.9 % for a cache with no bound at all.

    Reuse is asserted by **object identity**, not by value: a rebuilt block
    would carry the same numbers (every block here is a deterministic
    function of its key), so an equality check would pass for the cache that
    is not working, which is exactly the bug.
    """
    cached, _plain, table = rich
    base = table.decode(table.x0())
    other = dict(base)
    other["phases.0.cell.a"] = base["phases.0.cell.a"] * 1.001

    first_base = cached.phase_peaks(0, base)
    first_other = cached.phase_peaks(0, other)
    for _ in range(4):
        again_base = cached.phase_peaks(0, base)
        again_other = cached.phase_peaks(0, other)
        # position and both widths come straight out of memoised blocks
        for il in range(len(first_base)):
            for k in (0, 1, 2):
                assert again_base[il][k] is first_base[il][k], \
                    f"the base arm was rebuilt (line {il}, slot {k})"
                assert again_other[il][k] is first_other[il][k], \
                    f"the perturbed arm was rebuilt (line {il}, slot {k})"


def test_a_third_state_evicts_the_least_recently_used_arm(rich):
    """The bound is real, and that is the point of it.

    The keys are decoded θ, so an unbounded map grows an entry per parameter
    vector a fit visits — thousands — which is a leak, not a cache.  Depth is
    therefore 2, and this pins that a third state costs the older arm rather
    than joining it.  Measured justification for the number: depth 8 built
    exactly the same blocks as depth 2 on the trigger fit, to the call, so the
    lookups a deeper cache would catch are ones from an earlier Jacobian
    entirely (``CompiledModel._memo``).
    """
    from rietx.model.forward import _MEMO_DEPTH

    assert _MEMO_DEPTH == 2, "this test pins the shape that constant sets"
    cached, _plain, table = rich
    base = table.decode(table.x0())
    second = dict(base)
    second["phases.0.cell.a"] = base["phases.0.cell.a"] * 1.001
    third = dict(base)
    third["phases.0.cell.a"] = base["phases.0.cell.a"] * 1.002

    first_base = cached.phase_peaks(0, base)
    cached.phase_peaks(0, second)
    cached.phase_peaks(0, third)          # base is now the older of three
    assert len(cached.phases[0].scalar_cache["cell"]) == _MEMO_DEPTH
    back = cached.phase_peaks(0, base)
    assert back[0][0] is not first_base[0][0], \
        "a third state did not evict, so the cache is unbounded"
