(guide-path)=
# How to check a series for path dependence

Fit the series with `direction="both"` and look for `SEQUENTIAL_PATH_DEPENDENT`, and pass `verify_discontinuities=True` so that each step the series flags is refitted from cold on its two patterns alone.

Each fit in a series starts from its neighbour's answer.
An error in one pattern can therefore pass to every pattern after it and still draw a smooth curve.
These two checks separate a trend in the data from one the chain made.

## Run the chain both ways

This fits the seven synthetic LaB6 patterns of [How to fit a temperature series](series.md) from 300 K up to 900 K and again from 900 K down:

```{literalinclude} ../../../examples/guides/path.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/path.py -->
```text
['SEQUENTIAL_PERSISTENT_FINDING', 'SEQUENTIAL_PERSISTENT_FINDING']
largest forward-backward gap: 0.00 esd
```

`series.backward` is the downward chain's own `SeriesResult`, and the entries of `series` are the upward one's.
A `SEQUENTIAL_PATH_DEPENDENT` diagnostic names each parameter whose two values differ by more than their esds allow, and its message quotes both values.
Read the two values rather than the multiple of σ, because a parameter near zero with an esd near zero can report a gap of thousands of σ that has no physical size.

No such diagnostic fired here, and the largest gap in the cell edge is under 0.01 esd.
`SEQUENTIAL_PATH_CHECK_INCOMPLETE` is absent too, so the comparison ran on every pattern.
The two checks together mean the comparison was made and found nothing.
Without the second, an empty list can also mean the downward chain was stopped or raised before it finished.

The downward chain repeats the work of the upward one, so `direction="both"` takes about twice as long.

## Check a step against two independent fits

`SEQUENTIAL_DISCONTINUITY` flags a step much larger than the series' typical step.
Such a step is either in the data or made by the chain, and the diagnostic cannot tell which.
`verify_discontinuities=True` refits the step's two patterns from your starting model, each on its own, and reports the step they give.
This replaces the 700 K pattern with one whose cell is 1.5 % larger:

```{literalinclude} ../../../examples/guides/path.py
:language: python
:start-after: "# guide: jump start"
:end-before: "# guide: jump end"
```

<!-- output of examples/guides/path.py -->
```text
phases.0.cell.a steps by 0.06454 between p003 and p004 (T (K) 600 → 700), 31× its median step over the series. Refitted cold and independently, the two patterns step by 0.06454, 1.00× the chain's.
p000  cold
p001  warm
p002  warm
p003  warm
p004  warm_staged
p005  warm
p006  warm
```

The diagnostic's `value` is the cold step over the chain's.
Near 1 the step is in the data, as here.
Near 0 the chain made it, because the two patterns agree when nothing passes an error between them.
Near −1 the cold pair stepped the other way.
`series.discontinuities` holds the flagged pairs, with `SeriesStep.indices` and `SeriesStep.step`.

The check costs up to two full fits per flagged step, and nothing else in the result changes.
Here `cell.b` and `cell.c` are flagged at the same step as `cell.a`, because the cubic cell ties them to it, and the three flags share one pair of refits.

## Read where each fit started

The jump also broke a warm start, at the jumped pattern.
The 700 K fit, started from the 600 K answer, reached an Rwp over 0.9, far above the rest of the series.
The series fitted it again with the whole plan, still from the 600 K answer, and reached 0.04.
The 800 K fit, started from that answer, needed no second attempt.
`entry.rwp_warm` keeps the Rwp the first attempt reached.

A `cold` entry after the first pattern means no warm start could be rescued, and the pattern was fitted from your starting model.
Its values do not continue the chain, so read them as a separate measurement.

The full script is `examples/guides/path.py`.

## See also

- [How to fit a temperature series](series.md) runs the chain these checks test.
