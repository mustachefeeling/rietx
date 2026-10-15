(guide-calibrate)=
# How to calibrate an instrument once and reuse it

Refine a line-profile standard with its certified cell held fixed, save the instrument, then load it for every sample measured on the same setup.

This is how you separate the instrument's peak widths from the sample's. The instrument and sample widths combine by the rule in {eq}`prof-caglioti-g`, so the fit can only tell them apart if the instrument half comes from another measurement.

## Calibrate on the standard

Use the `lab_calibrate` plan. It frees the scale, background, zero shift, specimen displacement, the five width terms, the emission-line weights, the two axial-divergence terms and the atoms' Biso. It never frees the cell.

<!-- api-doc: no-exec — it refines a standard and writes a file -->
```python
import rietx as rx

ref = rx.Refinement(standard, instrument)
ref.fit(standard_data, plan="lab_calibrate")
rx.save_instrument_profile(ref.fitted_instrument, "cu_ka_10mm.json")
```

:::{note}
`save_instrument_profile` drops what belongs to one specimen: the background, the specimen displacement and transparency, the surface roughness, the absorption and any extra components.
:::

## Refine each sample from the saved profile

`load_instrument_profile` returns an `Instrument` with every parameter fixed. The `lab_sample_refine` plan never frees the zero shift or the instrument widths.

<!-- api-doc: no-exec — it needs the profile written above -->
```python
instrument = rx.load_instrument_profile("cu_ka_10mm.json")
ref = rx.Refinement(structure, instrument)
ref.fit(data, plan="lab_sample_refine")
```

:::{warning}
Don't free the instrument widths again on a sample. That undoes the separation the standard gave you.
:::

The squared Gaussian width can't go below a floor of {const}`MIN_GAMMA_G2` deg². Read why in [](#sec-caglioti).
