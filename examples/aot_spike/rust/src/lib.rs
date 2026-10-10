//! WP-1939 spike: `rietx/model/_kernels_numba.py` transcribed to Rust.
//!
//! Every expression copies the numba line it replaces, association for
//! association; that module's docstring is the contract.  Signatures are the
//! numba ones, positionally, so `compiled._KERNELS` can hold these instead.
//!
//! Two shapes are load-bearing, and both were measured (WP-1939's file):
//!
//! - **Outputs are raw pointers, not `PyReadwriteArray`.**  `compiled._spread`
//!   calls one kernel from several threads on the *same* output array with
//!   disjoint row ranges, and rust-numpy's borrow tracker refuses a second
//!   writable borrow of an array while the first is live.  Disjoint rows make
//!   the writes race-free; a pointer says so instead of handing two threads
//!   aliasing `&mut` slices.
//! - **Each loop is a free function taking its inputs as slice arguments and
//!   its outputs as pointers by value.**  Written as a closure over captured
//!   references, every store through an `f64` pointer could (Rust having no
//!   type-based alias analysis) have moved a captured slice's pointer, so LLVM
//!   reloaded them each iteration: the scatter ran at 0.59× numba that way.

use numpy::{PyArray1, PyArray2, PyArrayMethods, PyReadonlyArray1, PyReadonlyArray2, PyUntypedArrayMethods};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::f64::consts::{LN_2, PI};

const K4LN2: f64 = 4.0 * LN_2;

/// A raw output pointer that may cross into `Python::detach`.
#[derive(Clone, Copy)]
struct P(*mut f64);
unsafe impl Send for P {}
unsafe impl Sync for P {}
impl P {
    /// a method, so a closure captures the Send wrapper and not its field
    fn get(self) -> *mut f64 {
        self.0
    }
}

/// An output plane as a raw pointer, checked as numba and Cython check one:
/// C-contiguous, writeable, and the same shape as `x`.  The loops write
/// through the pointer at `x`'s indices, and `x`'s slices are bounds-checked,
/// so the shape check is what keeps every write inside the plane.
fn out2(a: &Bound<'_, PyArray2<f64>>, like: &[usize]) -> PyResult<P> {
    if !a.is_c_contiguous() {
        return Err(PyValueError::new_err("output plane must be C-contiguous"));
    }
    if unsafe { (*a.as_array_ptr()).flags } & numpy::npyffi::NPY_ARRAY_WRITEABLE == 0 {
        return Err(PyValueError::new_err("output plane must be writeable"));
    }
    if a.shape() != like {
        return Err(PyValueError::new_err("output plane must have x's shape"));
    }
    Ok(P(a.data()))
}

fn sl<'a, T: numpy::Element>(a: &'a PyReadonlyArray1<'_, T>) -> PyResult<&'a [T]> {
    a.as_slice().map_err(|e| PyValueError::new_err(e.to_string()))
}

/// A read-only plane as (slice, row stride).
fn pl<'a>(a: &'a PyReadonlyArray2<'_, f64>) -> PyResult<(&'a [f64], usize)> {
    let w = a.shape()[1];
    Ok((a.as_slice().map_err(|e| PyValueError::new_err(e.to_string()))?, w))
}

// --- the loops ---------------------------------------------------------

#[allow(clippy::too_many_arguments)]
fn accum_loop(y: &mut [f64], i0: &[i64], i1: &[i64], c0: &[f64], p0: &[f64], w0: usize,
              c1: &[f64], p1: &[f64], w1: usize, c2: &[f64], p2: &[f64], w2: usize,
              c3: &[f64], p3: &[f64], w3: usize, n_terms: i64) {
    for r in 0..i0.len() {
        let b = i0[r] as usize;
        let w = (i1[r] - i0[r]) as usize;
        let ys = &mut y[b..b + w];
        match n_terms {
            1 => {
                let a0 = c0[r];
                let q0 = &p0[r * w0..r * w0 + w];
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                }
            }
            2 => {
                let (a0, a1) = (c0[r], c1[r]);
                let (q0, q1) = (&p0[r * w0..r * w0 + w], &p1[r * w1..r * w1 + w]);
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                    ys[p] += a1 * q1[p];
                }
            }
            3 => {
                let (a0, a1, a2) = (c0[r], c1[r], c2[r]);
                let (q0, q1, q2) = (&p0[r * w0..r * w0 + w], &p1[r * w1..r * w1 + w],
                                    &p2[r * w2..r * w2 + w]);
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                    ys[p] += a1 * q1[p];
                    ys[p] += a2 * q2[p];
                }
            }
            _ => {
                let (a0, a1, a2, a3) = (c0[r], c1[r], c2[r], c3[r]);
                let (q0, q1, q2, q3) = (&p0[r * w0..r * w0 + w], &p1[r * w1..r * w1 + w],
                                        &p2[r * w2..r * w2 + w], &p3[r * w3..r * w3 + w]);
                for p in 0..w {
                    ys[p] += a0 * q0[p];
                    ys[p] += a1 * q1[p];
                    ys[p] += a2 * q2[p];
                    ys[p] += a3 * q3[p];
                }
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn omega_sym_loop(out: *mut f64, ow: usize, x: &[f64], xw: usize, rows: &[i64],
                         pos: &[f64], w1: &[f64], w2: &[f64], width: &[i64], spell: i64,
                         lo: usize, hi: usize) {
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e, p) = (w1[j], w2[j], pos[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let o = unsafe { out.add(j * ow) };
        for c in 0..n {
            let u = (xs[c] - p) / g;
            let uu = u * u;
            let ex = if spell == 0 { -K4LN2 * uu } else { (-K4LN2 * u) * u };
            let lor = (2.0 / (PI * g)) / (1.0 + 4.0 * uu);
            let gau = (2.0 / g) * srp * ex.exp();
            unsafe { *o.add(c) = e * lor + (1.0 - e) * gau };
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn omega_fcj_loop(out: *mut f64, ow: usize, x: &[f64], xw: usize, rows: &[i64],
                         w1: &[f64], w2: &[f64], width: &[i64], phi: &[f64], om: &[f64],
                         nn: usize, spell: i64, lo: usize, hi: usize) {
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e) = (w1[j], w2[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let (ph, wt) = (&phi[r * nn..r * nn + nn], &om[r * nn..r * nn + nn]);
        let o = unsafe { out.add(j * ow) };
        for c in 0..n {
            let xv = xs[c];
            let mut s = 0.0;
            for m in 0..nn {
                let u = (xv - ph[m]) / g;
                let uu = u * u;
                let ex = if spell == 0 { -K4LN2 * uu } else { (-K4LN2 * u) * u };
                let lor = (2.0 / (PI * g)) / (1.0 + 4.0 * uu);
                let gau = (2.0 / g) * srp * ex.exp();
                s += wt[m] * (e * lor + (1.0 - e) * gau);
            }
            unsafe { *o.add(c) = s };
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn bases_sym_loop(o_om: *mut f64, o_dp: *mut f64, o_dg: *mut f64, o_de: *mut f64,
                         ow: usize, x: &[f64], xw: usize, rows: &[i64], pos: &[f64],
                         w1: &[f64], w2: &[f64], width: &[i64], lo: usize, hi: usize) {
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e, p) = (w1[j], w2[j], pos[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let k = j * ow;
        for c in 0..n {
            let u = (xs[c] - p) / g;
            let den = 1.0 + 4.0 * u * u;
            let lor = (2.0 / (PI * g)) / den;
            let gau = (2.0 / g) * srp * ((-K4LN2 * u) * u).exp();
            let dl_dx = -lor * (8.0 * u / g) / den;
            let dg_dx = -gau * (2.0 * K4LN2 * u / g);
            let dl_dg = (lor / g) * (8.0 * u * u / den - 1.0);
            let dg_dg = (gau / g) * (2.0 * K4LN2 * u * u - 1.0);
            unsafe {
                *o_om.add(k + c) = e * lor + (1.0 - e) * gau;
                *o_dp.add(k + c) = -(e * dl_dx + (1.0 - e) * dg_dx);
                *o_dg.add(k + c) = e * dl_dg + (1.0 - e) * dg_dg;
                *o_de.add(k + c) = lor - gau;
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn bases_fcj_loop(o: [*mut f64; 6], ow: usize, x: &[f64], xw: usize, rows: &[i64],
                         w1: &[f64], w2: &[f64], width: &[i64], phi: &[f64], om: &[f64],
                         dphi: &[f64], dom: &[f64], dphi_sl: &[f64], dom_sl: &[f64],
                         dphi_hl: &[f64], dom_hl: &[f64], nn: usize, has_ax: bool,
                         lo: usize, hi: usize) {
    let [o_om, o_dp, o_dg, o_de, o_sl, o_hl] = o;
    let srp = (LN_2 / PI).sqrt();
    for r in lo..hi {
        let j = rows[r] as usize;
        let (g, e) = (w1[j], w2[j]);
        let n = width[j] as usize;
        let xs = &x[j * xw..j * xw + n];
        let b = r * nn;
        let (ph, wt, dph, dw) = (&phi[b..b + nn], &om[b..b + nn], &dphi[b..b + nn],
                                 &dom[b..b + nn]);
        let k = j * ow;
        for c in 0..n {
            let xv = xs[c];
            let (mut s_om, mut s_dg, mut s_de) = (0.0, 0.0, 0.0);
            let (mut a_pos, mut b_pos) = (0.0, 0.0);
            let (mut a_sl, mut b_sl, mut a_hl, mut b_hl) = (0.0, 0.0, 0.0, 0.0);
            for m in 0..nn {
                let u = (xv - ph[m]) / g;
                let den = 1.0 + 4.0 * u * u;
                let lor = (2.0 / (PI * g)) / den;
                let gau = (2.0 / g) * srp * ((-K4LN2 * u) * u).exp();
                let pv = e * lor + (1.0 - e) * gau;
                let dl_dx = -lor * (8.0 * u / g) / den;
                let dg_dx = -gau * (2.0 * K4LN2 * u / g);
                let ddx = e * dl_dx + (1.0 - e) * dg_dx;
                let dl_dg = (lor / g) * (8.0 * u * u / den - 1.0);
                let dg_dg = (gau / g) * (2.0 * K4LN2 * u * u - 1.0);
                let w = wt[m];
                s_om += w * pv;
                s_dg += w * (e * dl_dg + (1.0 - e) * dg_dg);
                s_de += w * (lor - gau);
                a_pos += dw[m] * pv;
                b_pos += (w * dph[m]) * ddx;
                if has_ax {
                    a_sl += dom_sl[b + m] * pv;
                    b_sl += (w * dphi_sl[b + m]) * ddx;
                    a_hl += dom_hl[b + m] * pv;
                    b_hl += (w * dphi_hl[b + m]) * ddx;
                }
            }
            unsafe {
                *o_om.add(k + c) = s_om;
                *o_dg.add(k + c) = s_dg;
                *o_de.add(k + c) = s_de;
                *o_dp.add(k + c) = a_pos - b_pos;
                if has_ax {
                    *o_sl.add(k + c) = a_sl - b_sl;
                    *o_hl.add(k + c) = a_hl - b_hl;
                }
            }
        }
    }
}

// --- the bindings ------------------------------------------------------

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn accum(
    py: Python<'_>,
    y: &Bound<'_, PyArray1<f64>>,
    i0: PyReadonlyArray1<'_, i64>,
    i1: PyReadonlyArray1<'_, i64>,
    c0: PyReadonlyArray1<'_, f64>,
    p0: PyReadonlyArray2<'_, f64>,
    c1: PyReadonlyArray1<'_, f64>,
    p1: PyReadonlyArray2<'_, f64>,
    c2: PyReadonlyArray1<'_, f64>,
    p2: PyReadonlyArray2<'_, f64>,
    c3: PyReadonlyArray1<'_, f64>,
    p3: PyReadonlyArray2<'_, f64>,
    n_terms: i64,
) -> PyResult<()> {
    // never split across threads (compiled.accumulate calls it once a part),
    // so the output can be an ordinary checked borrow
    let mut y = y.try_readwrite().map_err(|e| PyValueError::new_err(e.to_string()))?;
    let ys = y.as_slice_mut().map_err(|e| PyValueError::new_err(e.to_string()))?;
    let (i0, i1) = (sl(&i0)?, sl(&i1)?);
    let (c0, c1, c2, c3) = (sl(&c0)?, sl(&c1)?, sl(&c2)?, sl(&c3)?);
    let ((p0, w0), (p1, w1), (p2, w2), (p3, w3)) = (pl(&p0)?, pl(&p1)?, pl(&p2)?, pl(&p3)?);
    py.detach(|| accum_loop(ys, i0, i1, c0, p0, w0, c1, p1, w1, c2, p2, w2, c3, p3, w3, n_terms));
    Ok(())
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn omega_sym(
    py: Python<'_>,
    out: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    pos: PyReadonlyArray1<'_, f64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    spell: i64,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let o = out2(out, x.shape())?;
    let (x, xw) = pl(&x)?;
    let (rows, pos, w1, w2, width) = (sl(&rows)?, sl(&pos)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    py.detach(|| unsafe { omega_sym_loop(o.get(), xw, x, xw, rows, pos, w1, w2, width, spell, lo, hi) });
    Ok(())
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn omega_fcj(
    py: Python<'_>,
    out: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    phi: PyReadonlyArray2<'_, f64>,
    om: PyReadonlyArray2<'_, f64>,
    spell: i64,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let o = out2(out, x.shape())?;
    let (x, xw) = pl(&x)?;
    let (rows, w1, w2, width) = (sl(&rows)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    let ((phi, nn), (om, _)) = (pl(&phi)?, pl(&om)?);
    py.detach(|| unsafe {
        omega_fcj_loop(o.get(), xw, x, xw, rows, w1, w2, width, phi, om, nn, spell, lo, hi)
    });
    Ok(())
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn bases_sym(
    py: Python<'_>,
    omega: &Bound<'_, PyArray2<f64>>,
    d_pos: &Bound<'_, PyArray2<f64>>,
    d_gamma: &Bound<'_, PyArray2<f64>>,
    d_eta: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    pos: PyReadonlyArray1<'_, f64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let xs = x.shape();
    let (a, b, c, d) = (out2(omega, xs)?, out2(d_pos, xs)?, out2(d_gamma, xs)?, out2(d_eta, xs)?);
    let (x, xw) = pl(&x)?;
    let (rows, pos, w1, w2, width) = (sl(&rows)?, sl(&pos)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    py.detach(|| unsafe {
        bases_sym_loop(a.get(), b.get(), c.get(), d.get(), xw, x, xw, rows, pos, w1, w2, width, lo, hi)
    });
    Ok(())
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn bases_fcj(
    py: Python<'_>,
    omega: &Bound<'_, PyArray2<f64>>,
    d_pos: &Bound<'_, PyArray2<f64>>,
    d_gamma: &Bound<'_, PyArray2<f64>>,
    d_eta: &Bound<'_, PyArray2<f64>>,
    d_sl: &Bound<'_, PyArray2<f64>>,
    d_hl: &Bound<'_, PyArray2<f64>>,
    x: PyReadonlyArray2<'_, f64>,
    rows: PyReadonlyArray1<'_, i64>,
    w1: PyReadonlyArray1<'_, f64>,
    w2: PyReadonlyArray1<'_, f64>,
    width: PyReadonlyArray1<'_, i64>,
    phi: PyReadonlyArray2<'_, f64>,
    om: PyReadonlyArray2<'_, f64>,
    dphi: PyReadonlyArray2<'_, f64>,
    dom: PyReadonlyArray2<'_, f64>,
    dphi_sl: PyReadonlyArray2<'_, f64>,
    dom_sl: PyReadonlyArray2<'_, f64>,
    dphi_hl: PyReadonlyArray2<'_, f64>,
    dom_hl: PyReadonlyArray2<'_, f64>,
    has_ax: bool,
    lo: usize,
    hi: usize,
) -> PyResult<()> {
    let xs = x.shape();
    let (a, b, c, d) = (out2(omega, xs)?, out2(d_pos, xs)?, out2(d_gamma, xs)?, out2(d_eta, xs)?);
    // without axial columns the caller passes empty placeholders, never written
    let (s, h) = if has_ax {
        (out2(d_sl, xs)?, out2(d_hl, xs)?)
    } else {
        (P(std::ptr::null_mut()), P(std::ptr::null_mut()))
    };
    let (x, xw) = pl(&x)?;
    let (rows, w1, w2, width) = (sl(&rows)?, sl(&w1)?, sl(&w2)?, sl(&width)?);
    let ((phi, nn), (om, _), (dphi, _), (dom, _)) = (pl(&phi)?, pl(&om)?, pl(&dphi)?, pl(&dom)?);
    let ((dphi_sl, _), (dom_sl, _), (dphi_hl, _), (dom_hl, _)) =
        (pl(&dphi_sl)?, pl(&dom_sl)?, pl(&dphi_hl)?, pl(&dom_hl)?);
    py.detach(|| unsafe {
        bases_fcj_loop([a.get(), b.get(), c.get(), d.get(), s.get(), h.get()], xw, x, xw, rows, w1, w2, width, phi, om,
                       dphi, dom, dphi_sl, dom_sl, dphi_hl, dom_hl, nn, has_ax, lo, hi)
    });
    Ok(())
}

#[pymodule]
fn rietx_kernels_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(accum, m)?)?;
    m.add_function(wrap_pyfunction!(omega_sym, m)?)?;
    m.add_function(wrap_pyfunction!(omega_fcj, m)?)?;
    m.add_function(wrap_pyfunction!(bases_sym, m)?)?;
    m.add_function(wrap_pyfunction!(bases_fcj, m)?)?;
    Ok(())
}
