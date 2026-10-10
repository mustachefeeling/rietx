# rietx-kernels

The compiled model kernels of [rietx](https://github.com/yue-here/rietx), a
Rietveld refinement package for powder diffraction. They are built for
`rietx.model.compiled` and have no other public interface.

The package is one abi3 wheel per platform, built from Rust with PyO3. Its
major version is the kernel interface number, `rietx_kernels.KERNEL_ABI`.
A rietx that calls them pins that major version and checks the integer at
import.

The source lives in the rietx repository under `kernels/`. Build it with
`maturin develop --release -m kernels/Cargo.toml` from the repository root.
