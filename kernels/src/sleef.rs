// Ported from SLEEF 3.5.1:
//   Copyright Naoki Shibata and contributors 2010 - 2020.
// Distributed under the Boost Software License, Version 1.0.
//    (See accompanying file sleef.LICENSE or copy at
//          http://www.boost.org/LICENSE_1_0.txt)

//! The exponential the FCJ kernels call on x86-64 (WP-1940 § The relaxed
//! rule), from 1.2.0; `fcj.rs` says why only there.  It is SLEEF 3.5.1's `xexp` in its non-FMA form, ported from
//! `src/libm/sleefsimddp.c`, `src/libm/estrin.h` and `src/common/misc.h`
//! (Boost Software License 1.0, `sleef.LICENSE` beside this file and
//! `ATTRIBUTION.md`).  SLEEF documents it at 1.0 ulp; that is the bound
//! `tests/test_compiled_kernels.py` asserts on every wheel.
//!
//! **Why this one.**  It has no table, so a loop over it vectorises without
//! gathers, and its non-FMA branch was written for unfused multiply-adds.
//! rustc never fuses one, so the same source gives the same bits on every
//! x86-64 OS and at every vector width, where the C library's `exp` differs
//! between Windows, glibc and macOS.  ARM's optimized-routines vector `exp`
//! was the other candidate: 2.4 ulp, a 128-entry table, a bound that assumes
//! a fused multiply-add, and a scalar fallback below -708, where these
//! kernels' Gaussian exponent lands on every wide window.
//!
//! **What differs from SLEEF, and why each is the same function.**
//! - `rint` is the shift trick: `(y + 1.5·2⁵²) - 1.5·2⁵²` rounds to nearest,
//!   ties to even, exactly as `rint` does under the default rounding mode,
//!   for |y| < 2⁵¹.  It vectorises where `rint` needs SSE4.1.  The integer
//!   comes from the sum's low bits.
//! - The argument is clamped to [-1100, 710] first, so that the shift trick
//!   holds and the exponent arithmetic cannot wrap.  Outside [-1000, 709.78]
//!   SLEEF's own selects decide the answer (0 and +∞), and they read the
//!   unclamped argument, so the clamp changes no output.  A NaN fails both
//!   comparisons, passes through and comes out NaN.

/// 1/ln 2, and ln 2 split so that `q·L2U` is exact for every `q` the clamp
/// allows (`misc.h`).
const R_LN2: f64 = 1.442695040888963407359924681001892137426645954152985934135449406931;
const L2U: f64 = 0.69314718055966295651160180568695068359375;
const L2L: f64 = 0.28235290563031577122588448175013436025525412068e-12;

/// 1.5·2⁵²: added and subtracted, it rounds to an integer.
const SHIFT: f64 = 6755399441055744.0;

/// `vmla_vd_vd_vd_vd` without FMA: a multiply, rounded, then an add.
#[inline(always)]
fn mla(x: f64, y: f64, z: f64) -> f64 {
    x * y + z
}

/// `estrin.h`'s POLY2, POLY4, POLY8 and POLY10, by hand.
#[inline(always)]
fn poly2(x: f64, c1: f64, c0: f64) -> f64 {
    mla(x, c1, c0)
}

#[inline(always)]
fn poly4(x: f64, x2: f64, c3: f64, c2: f64, c1: f64, c0: f64) -> f64 {
    mla(x2, mla(x, c3, c2), mla(x, c1, c0))
}

/// 2^q for the exponents `ldexp2` hands it, |q| ≤ 1022 (`vpow2i_vd_vi`).
#[inline(always)]
fn pow2i(q: i64) -> f64 {
    f64::from_bits(((q + 0x3ff) as u64) << 52)
}

/// e^d to SLEEF's documented 1.0 ulp.
#[inline(always)]
pub(crate) fn exp(d: f64) -> f64 {
    let c = if d < -1100.0 { -1100.0 } else if d > 710.0 { 710.0 } else { d };
    let t = c * R_LN2 + SHIFT;
    let u = t - SHIFT;
    let q = (t.to_bits() as i64).wrapping_sub(SHIFT.to_bits() as i64);

    let mut s = mla(u, -L2U, c);
    s = mla(u, -L2L, s);

    let s2 = s * s;
    let s4 = s2 * s2;
    let s8 = s4 * s4;
    let mut p = mla(
        s8,
        poly2(s, 2.08860621107283687536341e-09, 2.51112930892876518610661e-08),
        mla(
            s4,
            poly4(s, s2, 2.75573911234900471893338e-07, 2.75572362911928827629423e-06,
                  2.4801587159235472998791e-05, 0.000198412698960509205564975),
            poly4(s, s2, 0.00138888888889774492207962, 0.00833333333331652721664984,
                  0.0416666666666665047591422, 0.166666666666666851703837),
        ),
    );
    p = mla(p, s, 0.5);
    p = 1.0 + mla(s * s, p, s);

    // vldexp2_vd_vd_vi: two halves, so a subnormal result rounds once
    let h = q >> 1;
    p = p * pow2i(h) * pow2i(q - h);

    if d > 709.78271114955742909217217426 {
        p = f64::INFINITY;
    }
    if d < -1000.0 {
        p = 0.0;
    }
    p
}
