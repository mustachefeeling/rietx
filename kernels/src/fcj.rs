//! The two FCJ kernels' loops, `omega_fcj` and `bases_fcj`, in one of two
//! shapes chosen by the target architecture (WP-1940, from 1.2.0).
//!
//! **On x86-64 the node loop runs outside the window loop and the exponential
//! is SLEEF's** (`sleef.rs`), and each loop is built twice, for AVX2 and for
//! the baseline, chosen at run time.  The inner loop then runs across window
//! points and vectorises four wide.  Measured on GitHub's runners on a
//! trigger-sized call (494 rows, 151 points, 8 nodes), `omega_fcj` went from
//! 8.97 to 3.88 ns per point and node on Linux (EPYC 7763), 8.04 to 3.30 on
//! Windows and 14.3 to 4.9 on macOS (i7-8700B).
//!
//! **Elsewhere, on arm64, they are 1.1.0's loops and call the C library's
//! `exp`.**  Apple's and glibc's are faster there than SLEEF's two-wide port,
//! so that shape lost 50-57 % on darwin/arm64 and Linux aarch64 (Neoverse-N2),
//! and no blocking of it or fused variant gained over 8 %.
//!
//! Both shapes sum each point's nodes in order from 0.0, so the interchange
//! moved no bit (measured on the C library's `exp` against 1.1.0, on every
//! plane of the trigger fit).  SLEEF's `exp` does move bits, by at most its
//! 1.0 ulp, under WP-1940's relaxed rule.  So an arm64 wheel gives 1.1.0's
//! bits, and the x86-64 wheels give one another's.  No fused operation enters
//! either build, which is why AVX2 and the baseline agree.

use crate::K4LN2;
use std::f64::consts::{LN_2, PI};

#[cfg(target_arch = "x86_64")]
mod shape {
    use super::*;

    /// SLEEF's, to 1.0 ulp (`sleef.rs`).
    #[inline(always)]
    pub(crate) fn exp(x: f64) -> f64 {
        crate::sleef::exp(x)
    }

    /// One node's term added to each window point's sum: the loop the compiler
    /// vectorises.  `BASIS` is `spell == 1`.
    #[inline(always)]
    fn omega_node<const BASIS: bool>(acc: &mut [f64], xs: &[f64], ph: f64, wt: f64, g: f64, e: f64,
                                     srp: f64) {
        for (a, &xv) in acc.iter_mut().zip(xs) {
            let u = (xv - ph) / g;
            let uu = u * u;
            let ex = if BASIS { (-K4LN2 * u) * u } else { -K4LN2 * uu };
            let lor = (2.0 / (PI * g)) / (1.0 + 4.0 * uu);
            let gau = (2.0 / g) * srp * exp(ex);
            *a += wt * (e * lor + (1.0 - e) * gau);
        }
    }

    /// The node loop outside the window loop, so the inner loop runs across
    /// window points.  Each point still sums its nodes in order from 0.0, so the
    /// interchange moves no bit.  Inlined into both of `omega_fcj_loop`'s builds.
    #[allow(clippy::too_many_arguments)]
    #[inline(always)]
    unsafe fn omega_any(out: *mut f64, ow: usize, x: &[f64], xw: usize, rows: &[i64],
                             w1: &[f64], w2: &[f64], width: &[i64], phi: &[f64], om: &[f64],
                             nn: usize, spell: i64, lo: usize, hi: usize) {
        let srp = (LN_2 / PI).sqrt();
        let mut buf = vec![0.0; xw];
        for r in lo..hi {
            let j = rows[r] as usize;
            let (g, e) = (w1[j], w2[j]);
            let n = width[j] as usize;
            let xs = &x[j * xw..j * xw + n];
            let (ph, wt) = (&phi[r * nn..r * nn + nn], &om[r * nn..r * nn + nn]);
            let acc = &mut buf[..n];
            acc.fill(0.0);
            for m in 0..nn {
                if spell == 0 {
                    omega_node::<false>(acc, xs, ph[m], wt[m], g, e, srp);
                } else {
                    omega_node::<true>(acc, xs, ph[m], wt[m], g, e, srp);
                }
            }
            unsafe { std::ptr::copy_nonoverlapping(acc.as_ptr(), out.add(j * ow), n) };
        }
    }


    /// One node's weights for `bases_node`: the node's weight `w`, its position
    /// weight `dw`, and `w` times its position's derivative, then the same pair
    /// for each axial parameter.  `w * dph` is the product the per-point loop
    /// formed, formed once.
    #[derive(Clone, Copy)]
    struct Node {
        ph: f64,
        w: f64,
        dw: f64,
        wdph: f64,
        dw_sl: f64,
        wdph_sl: f64,
        dw_hl: f64,
        wdph_hl: f64,
    }

    /// A row's running sums, one slice per sum, each the window's width.
    struct Sums<'a> {
        om: &'a mut [f64],
        dg: &'a mut [f64],
        de: &'a mut [f64],
        a_pos: &'a mut [f64],
        b_pos: &'a mut [f64],
        a_sl: &'a mut [f64],
        b_sl: &'a mut [f64],
        a_hl: &'a mut [f64],
        b_hl: &'a mut [f64],
    }

    /// One node's terms added to each window point's sums, as `omega_node`.
    #[inline(always)]
    fn bases_node<const AX: bool>(s: &mut Sums<'_>, xs: &[f64], nd: Node, g: f64, e: f64, srp: f64) {
        let n = xs.len();
        let (om, dg, de) = (&mut s.om[..n], &mut s.dg[..n], &mut s.de[..n]);
        let (a_pos, b_pos) = (&mut s.a_pos[..n], &mut s.b_pos[..n]);
        let (a_sl, b_sl) = (&mut s.a_sl[..n], &mut s.b_sl[..n]);
        let (a_hl, b_hl) = (&mut s.a_hl[..n], &mut s.b_hl[..n]);
        for c in 0..n {
            let u = (xs[c] - nd.ph) / g;
            let den = 1.0 + 4.0 * u * u;
            let lor = (2.0 / (PI * g)) / den;
            let gau = (2.0 / g) * srp * exp((-K4LN2 * u) * u);
            let pv = e * lor + (1.0 - e) * gau;
            let dl_dx = -lor * (8.0 * u / g) / den;
            let dg_dx = -gau * (2.0 * K4LN2 * u / g);
            let ddx = e * dl_dx + (1.0 - e) * dg_dx;
            let dl_dg = (lor / g) * (8.0 * u * u / den - 1.0);
            let dg_dg = (gau / g) * (2.0 * K4LN2 * u * u - 1.0);
            om[c] += nd.w * pv;
            dg[c] += nd.w * (e * dl_dg + (1.0 - e) * dg_dg);
            de[c] += nd.w * (lor - gau);
            a_pos[c] += nd.dw * pv;
            b_pos[c] += nd.wdph * ddx;
            if AX {
                a_sl[c] += nd.dw_sl * pv;
                b_sl[c] += nd.wdph_sl * ddx;
                a_hl[c] += nd.dw_hl * pv;
                b_hl[c] += nd.wdph_hl * ddx;
            }
        }
    }

    /// `omega_any`'s interchange, nine sums a point.
    #[allow(clippy::too_many_arguments)]
    #[inline(always)]
    unsafe fn bases_any(o: [*mut f64; 6], ow: usize, x: &[f64], xw: usize, rows: &[i64],
                             w1: &[f64], w2: &[f64], width: &[i64], phi: &[f64], om: &[f64],
                             dphi: &[f64], dom: &[f64], dphi_sl: &[f64], dom_sl: &[f64],
                             dphi_hl: &[f64], dom_hl: &[f64], nn: usize, has_ax: bool,
                             lo: usize, hi: usize) {
        let [o_om, o_dp, o_dg, o_de, o_sl, o_hl] = o;
        let srp = (LN_2 / PI).sqrt();
        let mut buf = vec![0.0; 9 * xw];
        for r in lo..hi {
            let j = rows[r] as usize;
            let (g, e) = (w1[j], w2[j]);
            let n = width[j] as usize;
            let xs = &x[j * xw..j * xw + n];
            let b = r * nn;
            let (ph, wt, dph, dw) = (&phi[b..b + nn], &om[b..b + nn], &dphi[b..b + nn],
                                     &dom[b..b + nn]);
            let mut parts = buf.chunks_exact_mut(xw).map(|p| &mut p[..n]);
            let mut next = || parts.next().unwrap();
            let mut s = Sums { om: next(), dg: next(), de: next(), a_pos: next(), b_pos: next(),
                               a_sl: next(), b_sl: next(), a_hl: next(), b_hl: next() };
            for p in [&mut s.om, &mut s.dg, &mut s.de, &mut s.a_pos, &mut s.b_pos] {
                p.fill(0.0);
            }
            if has_ax {
                for p in [&mut s.a_sl, &mut s.b_sl, &mut s.a_hl, &mut s.b_hl] {
                    p.fill(0.0);
                }
            }
            for m in 0..nn {
                let w = wt[m];
                let mut nd = Node { ph: ph[m], w, dw: dw[m], wdph: w * dph[m], dw_sl: 0.0,
                                    wdph_sl: 0.0, dw_hl: 0.0, wdph_hl: 0.0 };
                if has_ax {
                    nd.dw_sl = dom_sl[b + m];
                    nd.wdph_sl = w * dphi_sl[b + m];
                    nd.dw_hl = dom_hl[b + m];
                    nd.wdph_hl = w * dphi_hl[b + m];
                    bases_node::<true>(&mut s, xs, nd, g, e, srp);
                } else {
                    bases_node::<false>(&mut s, xs, nd, g, e, srp);
                }
            }
            let k = j * ow;
            for c in 0..n {
                unsafe {
                    *o_om.add(k + c) = s.om[c];
                    *o_dg.add(k + c) = s.dg[c];
                    *o_de.add(k + c) = s.de[c];
                    *o_dp.add(k + c) = s.a_pos[c] - s.b_pos[c];
                    if has_ax {
                        *o_sl.add(k + c) = s.a_sl[c] - s.b_sl[c];
                        *o_hl.add(k + c) = s.a_hl[c] - s.b_hl[c];
                    }
                }
            }
        }
    }


    /// `omega_any`, built twice: for AVX2 where the CPU has it, else for the
    /// baseline.  Both builds perform the same operations, so they give the
    /// same bits.
    #[allow(clippy::too_many_arguments)]
    pub(crate) unsafe fn omega_fcj_loop(out: *mut f64, ow: usize, x: &[f64], xw: usize,
                                    rows: &[i64], w1: &[f64], w2: &[f64], width: &[i64],
                                    phi: &[f64], om: &[f64], nn: usize, spell: i64, lo: usize,
                                    hi: usize) {
        if std::arch::is_x86_feature_detected!("avx2") {
            unsafe { omega_avx2(out, ow, x, xw, rows, w1, w2, width, phi, om, nn, spell, lo, hi) }
        } else {
            unsafe { omega_any(out, ow, x, xw, rows, w1, w2, width, phi, om, nn, spell, lo, hi) }
        }
    }

    #[allow(clippy::too_many_arguments)]
    #[target_feature(enable = "avx2")]
    unsafe fn omega_avx2(out: *mut f64, ow: usize, x: &[f64], xw: usize,
                                    rows: &[i64], w1: &[f64], w2: &[f64], width: &[i64],
                                    phi: &[f64], om: &[f64], nn: usize, spell: i64, lo: usize,
                                    hi: usize) {
        unsafe { omega_any(out, ow, x, xw, rows, w1, w2, width, phi, om, nn, spell, lo, hi) }
    }

    /// `bases_any`, built twice, as `omega_fcj_loop`.
    #[allow(clippy::too_many_arguments)]
    pub(crate) unsafe fn bases_fcj_loop(o: [*mut f64; 6], ow: usize, x: &[f64], xw: usize,
                                    rows: &[i64], w1: &[f64], w2: &[f64], width: &[i64],
                                    phi: &[f64], om: &[f64], dphi: &[f64], dom: &[f64],
                                    dphi_sl: &[f64], dom_sl: &[f64], dphi_hl: &[f64],
                                    dom_hl: &[f64], nn: usize, has_ax: bool, lo: usize,
                                    hi: usize) {
        if std::arch::is_x86_feature_detected!("avx2") {
            unsafe { bases_avx2(o, ow, x, xw, rows, w1, w2, width, phi, om, dphi, dom, dphi_sl, dom_sl,
                       dphi_hl, dom_hl, nn, has_ax, lo, hi) }
        } else {
            unsafe { bases_any(o, ow, x, xw, rows, w1, w2, width, phi, om, dphi, dom, dphi_sl, dom_sl,
                       dphi_hl, dom_hl, nn, has_ax, lo, hi) }
        }
    }

    #[allow(clippy::too_many_arguments)]
    #[target_feature(enable = "avx2")]
    unsafe fn bases_avx2(o: [*mut f64; 6], ow: usize, x: &[f64], xw: usize,
                                    rows: &[i64], w1: &[f64], w2: &[f64], width: &[i64],
                                    phi: &[f64], om: &[f64], dphi: &[f64], dom: &[f64],
                                    dphi_sl: &[f64], dom_sl: &[f64], dphi_hl: &[f64],
                                    dom_hl: &[f64], nn: usize, has_ax: bool, lo: usize,
                                    hi: usize) {
        unsafe { bases_any(o, ow, x, xw, rows, w1, w2, width, phi, om, dphi, dom, dphi_sl, dom_sl,
                       dphi_hl, dom_hl, nn, has_ax, lo, hi) }
    }
}

#[cfg(not(target_arch = "x86_64"))]
mod shape {
    use super::*;

    /// The platform C library's, through Rust's `f64::exp`.
    #[inline(always)]
    pub(crate) fn exp(x: f64) -> f64 {
        x.exp()
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) unsafe fn omega_fcj_loop(out: *mut f64, ow: usize, x: &[f64], xw: usize, rows: &[i64],
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
    pub(crate) unsafe fn bases_fcj_loop(o: [*mut f64; 6], ow: usize, x: &[f64], xw: usize, rows: &[i64],
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
}

pub(crate) use shape::{bases_fcj_loop, exp, omega_fcj_loop};
