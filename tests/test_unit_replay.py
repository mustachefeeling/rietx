"""The unit replay WP-1519 holds its bar with (``tests/unit_replay.py``)."""

import pickle

from rietx.indexing import engines
from tests import unit_replay
from tests.test_indexing_engines import assert_same_lattice, spec_for, synthetic_peaks


def test_a_replay_is_the_captured_units_finished_search(tmp_path, monkeypatch):
    peaks, cell = synthetic_peaks("cubic")
    monkeypatch.setitem(unit_replay.DATASETS, "cubic",
                        lambda: {"peaks": peaks, "spec": spec_for("cubic")})
    registry = dict(engines._REGISTRY)
    keys = unit_replay.capture(tmp_path, ["cubic"])
    assert engines._REGISTRY == registry, "capture left a recorder registered"
    assert keys == [f"cubic.{name}.cubic" for name in engines.engine_names()]

    out = unit_replay.replay(tmp_path, "cubic.dichotomy.cubic", save=True, count=True)
    assert out["complete"] and out["candidates"] > 0
    saved = pickle.loads((tmp_path / "cubic.dichotomy.cubic.result.pkl").read_bytes())
    assert out["digest"] == unit_replay.digest(saved.candidates)
    assert_same_lattice(saved.candidates[0].cell, cell)

    rest = [unit_replay.replay(tmp_path, key, save=True, count=False)
            for key in keys if key != "cubic.dichotomy.cubic"]
    pooled = unit_replay.pool(tmp_path, "cubic", count=False)
    assert pooled["candidates"] == sum(r["candidates"] for r in [out, *rest])
    assert 0 < pooled["groups"] <= pooled["candidates"]
