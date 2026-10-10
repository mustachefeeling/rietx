# rietx-kernels

The compiled kernels of [rietx](https://github.com/yue-here/rietx), a
Rietveld refinement package for powder diffraction. Five compute the model's
peak profiles and their derivatives. From 1.1.0, two more draw the structure
figure. They are built for rietx and have no other public interface.

The package is one abi3 wheel per platform, built from Rust with PyO3. Its
major version is the kernel interface number, `rietx_kernels.KERNEL_ABI`.
A rietx that calls them pins that major version and checks the integer at
import.

The source lives in the rietx repository under `kernels/`. Build it with
`maturin develop --release -m kernels/Cargo.toml` from the repository root.
