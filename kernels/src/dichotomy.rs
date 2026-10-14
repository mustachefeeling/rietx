//! The dichotomy indexer's box test (WP-1959).  Its oracle is
//! `rietx/indexing/dichotomy.py`: `box_test` is `_test_box` and `child_key`
//! is `_push_children`'s test of one child.  Its bar is the bit on every
//! platform, because it calls no library function but `sqrt`, which IEEE
//! rounds correctly.
//!
//! **The floating-point half is a transcription.**  `q_bounds_row` and
//! `af_interval` sum their at most six terms left to right, which is what
//! numpy's `.sum(axis=1)` does at that width.  `tests/test_indexing_kernels.py`
//! pins numpy to that order, so a numpy that changed it fails there first.
//! `det` copies `_det_interval` operation for operation, and its `min` and
//! `max` keep the *first* of equal values, as Python's do.
//!
//! **The hit matrix is not transcribed, and it need not be.**  numpy builds
//! the dense (lines × rows) boolean matrix and reduces it four ways.  Here
//! each row gets a `u64` with one bit per line it reaches, from two rank
//! lookups into the windows sorted by their low and by their high edge.  The
//! row reaches line `i` exactly when `lo[i] <= q_max` and `q_min <= hi[i]`,
//! and every comparison is the one numpy makes, so the masks are the
//! matrix's rows bit for bit.  Every count the prunes read is then integer
//! work on the masks.  This needs no assumption on the windows: they may
//! overlap or nest.  More than `MASK_LINES` lines, or a window with a NaN
//! edge, takes `Dense`, the numba twin's per-line loop.
//!
//! **The prunes that read no row run first**, as in `_test_box` since
//! WP-1959.  Every prune is a refusal with no side effect, so the order
//! changes only the cost.

use numpy::{Element, PyArray1, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;

use crate::{err, pl, sl};

/// Most lines the mask test holds, one bit each.
const MASK_LINES: usize = 64;

// --- the interval arithmetic of `_det_interval` --------------------------

/// `dichotomy._imul`: min and max of the four products, first of equals.
fn imul(x0: f64, x1: f64, y0: f64, y1: f64) -> (f64, f64) {
    let p = [x0 * y0, x0 * y1, x1 * y0, x1 * y1];
    let (mut lo, mut hi) = (p[0], p[0]);
    for &v in &p[1..] {
        if v < lo {
            lo = v;
        }
    }
    for &v in &p[1..] {
        if v > hi {
            hi = v;
        }
    }
    (lo, hi)
}

/// `dichotomy._isq`: 0 is the minimum when the interval straddles it.
fn isq(lo: f64, hi: f64) -> (f64, f64) {
    let (a, b) = (lo * lo, hi * hi);
    let top = if b > a { b } else { a };
    if lo <= 0.0 && 0.0 <= hi {
        return (0.0, top);
    }
    (if b < a { b } else { a }, top)
}

/// `dichotomy._rho_bounds`: the correlation over the box, unclipped, or
/// `None` where a diagonal partner's interval reaches zero.
fn rho_bounds(x_lo: f64, x_hi: f64, y0: f64, y1: f64, z0: f64, z1: f64) -> Option<(f64, f64)> {
    if y0 <= 0.0 || z0 <= 0.0 {
        return None;
    }
    let small = 2.0 * (y0 * z0).sqrt();
    let big = 2.0 * (y1 * z1).sqrt();
    let lo = if x_lo < 0.0 { x_lo / small } else { x_lo / big };
    let hi = if x_hi > 0.0 { x_hi / small } else { x_hi / big };
    Some((lo, hi))
}

/// `dichotomy._rho_interval`: `rho_bounds` clipped to the obliquity bound.
fn rho(x_lo: f64, x_hi: f64, y0: f64, y1: f64, z0: f64, z1: f64, c: f64) -> (f64, f64) {
    match rho_bounds(x_lo, x_hi, y0, y1, z0, z1) {
        None => (-c, c),
        Some((lo, hi)) => (if -c > lo { -c } else { lo }, if c < hi { c } else { hi }),
    }
}

/// `dichotomy._OFFDIAG_PARTNERS`: each off-diagonal A..F index and its two
/// diagonal partners.
const PARTNERS: [(usize, usize, usize); 3] = [(3, 1, 2), (4, 0, 2), (5, 0, 1)];

/// `dichotomy._outside_obliquity`: some reciprocal angle lies beyond the
/// bound everywhere in the box.
fn outside_obliquity(af_lo: &[f64; 6], af_hi: &[f64; 6], c: f64) -> bool {
    PARTNERS.iter().any(|&(p, i, j)| {
        matches!(rho_bounds(af_lo[p], af_hi[p], af_lo[i], af_hi[i], af_lo[j], af_hi[j]),
                 Some((lo, hi)) if lo > c || hi < -c)
    })
}

/// `dichotomy._det_interval`, operation for operation.
fn det(af_lo: &[f64; 6], af_hi: &[f64; 6], c: f64) -> (f64, f64) {
    let (a0, a1) = (af_lo[0], af_hi[0]);
    let (b0, b1) = (af_lo[1], af_hi[1]);
    let (c0, c1) = (af_lo[2], af_hi[2]);
    let (d23_0, d23_1) = (0.5 * af_lo[3], 0.5 * af_hi[3]);
    let (d13_0, d13_1) = (0.5 * af_lo[4], 0.5 * af_hi[4]);
    let (d12_0, d12_1) = (0.5 * af_lo[5], 0.5 * af_hi[5]);
    let (ab0, ab1) = imul(a0, a1, b0, b1);
    let (diag0, diag1) = imul(ab0, ab1, c0, c1);
    let (x0, x1) = imul(d12_0, d12_1, d13_0, d13_1);
    let (cd0, cd1) = imul(x0, x1, d23_0, d23_1);
    let (s0, s1) = isq(d23_0, d23_1);
    let (t3_0, t3_1) = imul(a0, a1, s0, s1);
    let (s0, s1) = isq(d13_0, d13_1);
    let (t4_0, t4_1) = imul(b0, b1, s0, s1);
    let (s0, s1) = isq(d12_0, d12_1);
    let (t5_0, t5_1) = imul(c0, c1, s0, s1);
    let lo = diag0 + 2.0 * cd0 - t3_1 - t4_1 - t5_1;
    let hi = diag1 + 2.0 * cd1 - t3_0 - t4_0 - t5_0;

    let (r23_0, r23_1) = rho(af_lo[3], af_hi[3], b0, b1, c0, c1, c);
    let (r13_0, r13_1) = rho(af_lo[4], af_hi[4], a0, a1, c0, c1, c);
    let (r12_0, r12_1) = rho(af_lo[5], af_hi[5], a0, a1, b0, b1, c);
    let (s23_0, s23_1) = isq(r23_0, r23_1);
    let (s13_0, s13_1) = isq(r13_0, r13_1);
    let (s12_0, s12_1) = isq(r12_0, r12_1);
    let (x0, x1) = imul(r12_0, r12_1, r13_0, r13_1);
    let (cr0, cr1) = imul(x0, x1, r23_0, r23_1);
    let dr0 = 1.0 + 2.0 * cr0 - s23_1 - s13_1 - s12_1;
    let dr1 = 1.0 + 2.0 * cr1 - s23_0 - s13_0 - s12_0;
    let (cl, ch) = imul(diag0, diag1, dr0, dr1);
    (if cl > lo { cl } else { lo }, if ch < hi { ch } else { hi })
}

// --- the corner sums -----------------------------------------------------

/// One linear form's [min, max] over the box: a positive coefficient takes
/// the low edge for the minimum, anything else the high edge, as
/// `np.where(m > 0, ...)` does; the terms are summed left to right.
#[inline(always)]
fn corner_sum(row: &[f64], lo: &[f64], hi: &[f64]) -> (f64, f64) {
    let v = row[0];
    let (mut q_min, mut q_max) = if v > 0.0 { (v * lo[0], v * hi[0]) } else { (v * hi[0], v * lo[0]) };
    for j in 1..row.len() {
        let v = row[j];
        let (a, b) = if v > 0.0 { (v * lo[j], v * hi[j]) } else { (v * hi[j], v * lo[j]) };
        q_min = q_min + a;
        q_max = q_max + b;
    }
    (q_min, q_max)
}

/// `dichotomy._af_interval`: `basis_t` is `basis.T`, six rows of `lo.len()`.
fn af_interval(basis_t: &[f64], lo: &[f64], hi: &[f64]) -> ([f64; 6], [f64; 6]) {
    let n = lo.len();
    let (mut af_lo, mut af_hi) = ([0.0; 6], [0.0; 6]);
    for i in 0..6 {
        (af_lo[i], af_hi[i]) = corner_sum(&basis_t[i * n..(i + 1) * n], lo, hi);
    }
    (af_lo, af_hi)
}

// --- which lines a row reaches -------------------------------------------

/// The search windows as rank tables, when they fit a mask.
struct Masks {
    lo_sorted: Vec<f64>,
    hi_sorted: Vec<f64>,
    /// `lo_prefix[k]`: the lines whose low edges are the `k` smallest
    lo_prefix: Vec<u64>,
    /// `hi_suffix[j]`: every line but those whose high edges are the `j`
    /// smallest
    hi_suffix: Vec<u64>,
}

impl Masks {
    fn new(lo_s: &[f64], hi_s: &[f64]) -> Option<Masks> {
        let n = lo_s.len();
        if n > MASK_LINES || lo_s.iter().chain(hi_s).any(|v| v.is_nan()) {
            return None;
        }
        let mut by_lo: Vec<usize> = (0..n).collect();
        by_lo.sort_by(|&a, &b| lo_s[a].total_cmp(&lo_s[b]));
        let mut by_hi: Vec<usize> = (0..n).collect();
        by_hi.sort_by(|&a, &b| hi_s[a].total_cmp(&hi_s[b]));
        let mut lo_prefix = vec![0u64; n + 1];
        for (k, &i) in by_lo.iter().enumerate() {
            lo_prefix[k + 1] = lo_prefix[k] | 1 << i;
        }
        let mut hi_suffix = vec![0u64; n + 1];
        for (j, &i) in by_hi.iter().enumerate().rev() {
            hi_suffix[j] = hi_suffix[j + 1] | 1 << i;
        }
        Some(Masks {
            lo_sorted: by_lo.iter().map(|&i| lo_s[i]).collect(),
            hi_sorted: by_hi.iter().map(|&i| hi_s[i]).collect(),
            lo_prefix,
            hi_suffix,
        })
    }

    /// The lines `[q_min, q_max]` reaches: `lo <= q_max` holds on a prefix of
    /// the low edges and `q_min <= hi` on a suffix of the high edges, a NaN
    /// bound holding on neither, as in numpy.  Both predicates are monotone
    /// over sorted edges, and `total_cmp` orders -0 and +0, which compare
    /// equal, next to each other.
    #[inline(always)]
    fn of(&self, q_min: f64, q_max: f64) -> u64 {
        let k = self.lo_sorted.partition_point(|&l| q_max >= l);
        let j = self.hi_sorted.partition_point(|&h| !(q_min <= h));
        self.lo_prefix[k] & self.hi_suffix[j]
    }
}

/// What one pass over a box's rows hands the prunes, either way it was
/// counted.
struct Tally {
    /// lines at least one row reaches
    reached: usize,
    /// some line has two or more rows
    shared: bool,
    /// the one row of each line exactly one row reaches, as its position
    forced_rows: Vec<usize>,
}

/// Per-line counts from masks: `once` and `twice` are the carry-save pair,
/// `first[i]` the position of the first row to reach line `i`.
struct MaskCount {
    once: u64,
    twice: u64,
    first: [usize; MASK_LINES],
}

impl MaskCount {
    fn new() -> MaskCount {
        MaskCount { once: 0, twice: 0, first: [0; MASK_LINES] }
    }

    #[inline(always)]
    fn add(&mut self, mask: u64, position: usize) {
        self.twice |= self.once & mask;
        let mut new = mask & !self.once;
        self.once |= mask;
        while new != 0 {
            self.first[new.trailing_zeros() as usize] = position;
            new &= new - 1;
        }
    }

    fn tally(&self) -> Tally {
        let mut forced = self.once & !self.twice;
        let mut forced_rows = Vec::new();
        while forced != 0 {
            forced_rows.push(self.first[forced.trailing_zeros() as usize]);
            forced &= forced - 1;
        }
        Tally { reached: self.once.count_ones() as usize, shared: self.twice != 0, forced_rows }
    }
}

/// The numba twin's per-line counts, for windows a mask cannot hold.
struct Dense<'a> {
    lo_s: &'a [f64],
    hi_s: &'a [f64],
    counts: Vec<u64>,
    first: Vec<usize>,
}

impl<'a> Dense<'a> {
    fn new(lo_s: &'a [f64], hi_s: &'a [f64]) -> Dense<'a> {
        Dense { lo_s, hi_s, counts: vec![0; lo_s.len()], first: vec![0; lo_s.len()] }
    }

    /// Count the row at `position` against every line; how many it reached.
    fn add(&mut self, q_min: f64, q_max: f64, position: usize) -> u32 {
        let mut n = 0;
        for i in 0..self.lo_s.len() {
            if q_min <= self.hi_s[i] && q_max >= self.lo_s[i] {
                if self.counts[i] == 0 {
                    self.first[i] = position;
                }
                self.counts[i] += 1;
                n += 1;
            }
        }
        n
    }

    fn tally(&self) -> Tally {
        Tally {
            reached: self.counts.iter().filter(|&&c| c > 0).count(),
            shared: self.counts.iter().any(|&c| c > 1),
            forced_rows: (0..self.counts.len()).filter(|&i| self.counts[i] == 1).map(|i| self.first[i]).collect(),
        }
    }
}

// --- the row index types -------------------------------------------------

/// A row index type `_row_index_type` can choose, or numpy's default int.
trait Id: Element + Copy + Send + Sync {
    fn at(self) -> Option<usize>;
}

macro_rules! unsigned_id {
    ($($t:ty),*) => {$(
        impl Id for $t {
            #[inline(always)]
            fn at(self) -> Option<usize> {
                usize::try_from(self).ok()
            }
        }
    )*};
}
unsigned_id!(u8, u16, u32, u64, i64);

// --- the box test ----------------------------------------------------------

/// The arguments every box of a unit shares.
struct Unit<'a> {
    m: &'a [f64],
    width: usize,
    basis_t: &'a [f64],
    q_hi: f64,
    band: (f64, f64),
    swaps: &'a [i64],
    lo_s: &'a [f64],
    hi_s: &'a [f64],
    masks: Option<Masks>,
    n_unindexed: i64,
    cos_max: f64,
}

/// A surviving box: its rows that reach a line, in their order, the widest
/// such row's Q interval, whether every line has at most one row, and (when
/// asked) each column's largest |m| over the surviving rows.
struct Kept<T> {
    ids: Vec<T>,
    width: f64,
    unique: bool,
    col_max: Option<Vec<f64>>,
}

/// `Err(id)` names a row outside `m`.
type Tested<T> = Result<Option<Kept<T>>, u64>;

/// The prunes that read no row: the metric cone, the obliquity bound, the
/// axis swaps and the volume band.  `true` keeps the box.
fn box_ok(u: &Unit, lo: &[f64], hi: &[f64]) -> bool {
    let (af_lo, af_hi) = af_interval(u.basis_t, lo, hi);
    if af_hi[0] <= 0.0 || af_hi[1] <= 0.0 || af_hi[2] <= 0.0 || outside_obliquity(&af_lo, &af_hi, u.cos_max) {
        return false;
    }
    for s in u.swaps.chunks_exact(2) {
        if af_hi[s[0] as usize] < af_lo[s[1] as usize] {
            return false;
        }
    }
    let (det_lo, det_hi) = det(&af_lo, &af_hi, u.cos_max);
    !(det_hi < u.band.0 || det_lo > u.band.1)
}

/// `np.max` over a running value: the first NaN wins, as numpy's does.
#[inline(always)]
fn running_max(best: f64, v: f64, first: bool) -> f64 {
    if first || (best == best && (v > best || v != v)) { v } else { best }
}

fn box_test_loop<T: Id>(u: &Unit, ids: &[T], lo: &[f64], hi: &[f64], want_col_max: bool) -> Tested<T> {
    if !box_ok(u, lo, hi) {
        return Ok(None);
    }
    let w = u.width;
    let n_rows = u.m.len() / w.max(1);
    let mut out: Vec<T> = Vec::new();
    let mut n_kept = 0usize;
    let mut width = 0.0;
    let mut col_max = vec![0.0; if want_col_max { w } else { 0 }];
    let mut mask_count = MaskCount::new();
    // the per-line counts are allocated only where a mask cannot hold them
    let mut dense = u.masks.is_none().then(|| Dense::new(u.lo_s, u.hi_s));
    for &id in ids {
        let r = match id.at() {
            Some(r) if r < n_rows => r,
            _ => return Err(id.at().map_or(u64::MAX, |r| r as u64)),
        };
        let row = &u.m[r * w..(r + 1) * w];
        let (q_min, q_max) = corner_sum(row, lo, hi);
        // the ``q_min <= q_hi`` filter, which drops a NaN too
        if !(q_min <= u.q_hi) {
            continue;
        }
        n_kept += 1;
        let position = out.len();
        let reached = match (&u.masks, &mut dense) {
            (Some(masks), _) => {
                let mask = masks.of(q_min, q_max);
                mask_count.add(mask, position);
                mask != 0
            }
            (None, Some(dense)) => dense.add(q_min, q_max, position) > 0,
            (None, None) => unreachable!("dense is built whenever masks is None"),
        };
        if reached {
            width = running_max(width, q_max - q_min, position == 0);
            if want_col_max {
                for j in 0..w {
                    col_max[j] = running_max(col_max[j], row[j].abs(), position == 0);
                }
            }
            out.push(id);
        }
    }
    if n_kept == 0 {
        return Ok(None);
    }
    let n_lines = u.lo_s.len() as i64;
    let tally = match &dense {
        Some(dense) => dense.tally(),
        None => mask_count.tally(),
    };
    if n_lines - tally.reached as i64 > u.n_unindexed {
        return Ok(None);
    }
    // ``_assignment_possible``: Hall's condition in its two free forms
    if (out.len() as i64) < n_lines - u.n_unindexed {
        return Ok(None);
    }
    let n_forced = tally.forced_rows.len() as i64;
    if n_forced > 1 {
        let mut rows = tally.forced_rows;
        rows.sort_unstable();
        rows.dedup();
        if (rows.len() as i64) < n_forced - u.n_unindexed {
            return Ok(None);
        }
    }
    let unique = n_lines > 0 && !tally.shared;
    Ok(Some(Kept { ids: out, width, unique, col_max: want_col_max.then_some(col_max) }))
}

/// `_push_children`'s test of one child: `(misses, pairs, rows reaching a
/// line)`, over every row, with no `q_hi` filter, as numpy's has none.
fn child_key_loop<T: Id>(u: &Unit, ids: &[T], lo: &[f64], hi: &[f64]) -> Result<(i64, i64, i64), u64> {
    let w = u.width;
    let n_rows = u.m.len() / w.max(1);
    let mut reached_lines = 0u64;
    let mut dense = u.masks.is_none().then(|| Dense::new(u.lo_s, u.hi_s));
    let (mut pairs, mut n_rows_hit) = (0i64, 0i64);
    for &id in ids {
        let r = match id.at() {
            Some(r) if r < n_rows => r,
            _ => return Err(id.at().map_or(u64::MAX, |r| r as u64)),
        };
        let (q_min, q_max) = corner_sum(&u.m[r * w..(r + 1) * w], lo, hi);
        let n = match (&u.masks, &mut dense) {
            (Some(masks), _) => {
                let mask = masks.of(q_min, q_max);
                reached_lines |= mask;
                mask.count_ones()
            }
            (None, Some(dense)) => dense.add(q_min, q_max, 0),
            (None, None) => unreachable!("dense is built whenever masks is None"),
        };
        pairs += n as i64;
        n_rows_hit += (n > 0) as i64;
    }
    let reached = match &dense {
        Some(dense) => dense.counts.iter().filter(|&&c| c > 0).count() as i64,
        None => reached_lines.count_ones() as i64,
    };
    Ok((u.lo_s.len() as i64 - reached, pairs, n_rows_hit))
}

// --- the bindings ----------------------------------------------------------

#[allow(clippy::too_many_arguments)]
fn unit<'a>(
    m: &'a PyReadonlyArray2<'_, f64>,
    basis_t: &'a PyReadonlyArray2<'_, f64>,
    lo: &[f64],
    hi: &[f64],
    q_hi: f64,
    band: (f64, f64),
    swaps: &'a [i64],
    lo_s: &'a PyReadonlyArray1<'_, f64>,
    hi_s: &'a PyReadonlyArray1<'_, f64>,
    n_unindexed: i64,
    cos_max: f64,
) -> PyResult<Unit<'a>> {
    let (m, [_, width]) = pl("m", m)?;
    let (basis_t, [six, bw]) = pl("basis_t", basis_t)?;
    let (lo_s, hi_s) = (sl(lo_s)?, sl(hi_s)?);
    if width == 0 || six != 6 || bw != width || lo.len() != width || hi.len() != width {
        return err(format!("basis_t is ({six}, {bw}), m is {width} wide, the box {} and {}",
                           lo.len(), hi.len()));
    }
    if swaps.len() % 2 != 0 || swaps.iter().any(|&s| !(0..6).contains(&s)) {
        return err("swaps must be pairs of A..F indices 0..6");
    }
    if lo_s.len() != hi_s.len() {
        return err(format!("{} low edges against {} high", lo_s.len(), hi_s.len()));
    }
    Ok(Unit { m, width, basis_t, q_hi, band, swaps, lo_s, hi_s, masks: Masks::new(lo_s, hi_s),
              n_unindexed, cos_max })
}

fn bad_row<T>(id: u64) -> PyResult<T> {
    err(format!("row {id} is outside m"))
}

/// Dispatch on the row index type: `$body` runs with `ids` a slice of it.
macro_rules! with_ids {
    ($any:expr, $ids:ident, $t:ident, $body:block) => {{
        let any = $any;
        if let Ok(a) = any.extract::<PyReadonlyArray1<'_, u16>>() {
            type $t = u16;
            let $ids = sl(&a)?;
            $body
        } else if let Ok(a) = any.extract::<PyReadonlyArray1<'_, u32>>() {
            type $t = u32;
            let $ids = sl(&a)?;
            $body
        } else if let Ok(a) = any.extract::<PyReadonlyArray1<'_, u8>>() {
            type $t = u8;
            let $ids = sl(&a)?;
            $body
        } else if let Ok(a) = any.extract::<PyReadonlyArray1<'_, u64>>() {
            type $t = u64;
            let $ids = sl(&a)?;
            $body
        } else if let Ok(a) = any.extract::<PyReadonlyArray1<'_, i64>>() {
            type $t = i64;
            let $ids = sl(&a)?;
            $body
        } else {
            err("ids must be a 1-D array of uint8, uint16, uint32, uint64 or int64")
        }
    }};
}

/// `_test_box(m[ids], lo, hi, ...)`: `None` for an impossible box, else
/// `(surviving ids, width, unique, col_max)`, the ids in `ids`'s own type
/// and `col_max` `None` unless asked for.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn dichotomy_box_test<'py>(
    py: Python<'py>,
    m: PyReadonlyArray2<'py, f64>,
    ids: &Bound<'py, PyAny>,
    lo: PyReadonlyArray1<'py, f64>,
    hi: PyReadonlyArray1<'py, f64>,
    basis_t: PyReadonlyArray2<'py, f64>,
    q_hi: f64,
    band_lo: f64,
    band_hi: f64,
    swaps: PyReadonlyArray1<'py, i64>,
    lo_s: PyReadonlyArray1<'py, f64>,
    hi_s: PyReadonlyArray1<'py, f64>,
    n_unindexed: i64,
    cos_max: f64,
    want_col_max: bool,
) -> PyResult<Option<(Bound<'py, PyAny>, f64, bool, Option<Bound<'py, PyArray1<f64>>>)>> {
    let (lo, hi, swaps) = (sl(&lo)?, sl(&hi)?, sl(&swaps)?);
    let u = unit(&m, &basis_t, lo, hi, q_hi, (band_lo, band_hi), swaps, &lo_s, &hi_s, n_unindexed,
                 cos_max)?;
    with_ids!(ids, ids, T, {
        let tested: Tested<T> = py.detach(|| box_test_loop(&u, ids, lo, hi, want_col_max));
        match tested {
            Err(id) => bad_row(id),
            Ok(None) => Ok(None),
            Ok(Some(k)) => Ok(Some((PyArray1::from_vec(py, k.ids).into_any(), k.width, k.unique,
                                    k.col_max.map(|c| PyArray1::from_vec(py, c))))),
        }
    })
}

/// `_push_children`'s test of one child: `(misses, pairs, rows reaching a
/// line)`; the caller applies `n_unindexed`.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
pub(crate) fn dichotomy_child_key<'py>(
    py: Python<'py>,
    m: PyReadonlyArray2<'py, f64>,
    ids: &Bound<'py, PyAny>,
    lo: PyReadonlyArray1<'py, f64>,
    hi: PyReadonlyArray1<'py, f64>,
    basis_t: PyReadonlyArray2<'py, f64>,
    lo_s: PyReadonlyArray1<'py, f64>,
    hi_s: PyReadonlyArray1<'py, f64>,
) -> PyResult<(i64, i64, i64)> {
    let (lo, hi) = (sl(&lo)?, sl(&hi)?);
    let u = unit(&m, &basis_t, lo, hi, f64::INFINITY, (0.0, 0.0), &[], &lo_s, &hi_s, 0, 0.0)?;
    with_ids!(ids, ids, T, {
        let keyed: Result<(i64, i64, i64), u64> = py.detach(|| child_key_loop::<T>(&u, ids, lo, hi));
        keyed.or_else(bad_row)
    })
}
