"""
dxt5_encoder.py
===============
A small, plain DXT5 (BC3) block encoder - not the fastest or the highest
quality possible, but correct and dependency-free (just numpy), which is
all the small 256x128 UI/logo-style textures dds_builder.py needs this for.
"""

import numpy as np
import struct


def _pack_565(r: int, g: int, b: int) -> int:
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    return (r5 << 11) | (g6 << 5) | b5


def _unpack_565(v: int):
    r5 = (v >> 11) & 0x1F
    g6 = (v >> 5) & 0x3F
    b5 = v & 0x1F
    r = (r5 << 3) | (r5 >> 2)
    g = (g6 << 2) | (g6 >> 4)
    b = (b5 << 3) | (b5 >> 2)
    return r, g, b


def _encode_color_block(pixels_rgb: np.ndarray) -> bytes:
    """pixels_rgb: (16,3) uint8 array for one 4x4 block."""
    px = pixels_rgb.astype(np.float32)

    if np.all(px == px[0]):
        # solid color block
        r, g, b = px[0].astype(np.uint8)
        c = _pack_565(int(r), int(g), int(b))
        c0, c1 = (c, c - 1) if c > 0 else (1, 0)
        indices = np.zeros(16, dtype=np.uint8)
    else:
        mean = px.mean(axis=0)
        centered = px - mean
        cov = centered.T @ centered
        # find the block's dominant color direction (a few passes is enough
        # for a 3x3 matrix like this)
        axis = np.array([1.0, 1.0, 1.0])
        for _ in range(8):
            axis = cov @ axis
            norm = np.linalg.norm(axis)
            if norm < 1e-6:
                axis = np.array([1.0, 0.0, 0.0])
                break
            axis /= norm

        proj = centered @ axis
        i_max = int(np.argmax(proj))
        i_min = int(np.argmin(proj))
        c_max = px[i_max]
        c_min = px[i_min]

        c0v = _pack_565(int(c_max[0]), int(c_max[1]), int(c_max[2]))
        c1v = _pack_565(int(c_min[0]), int(c_min[1]), int(c_min[2]))

        if c0v == c1v:
            if c0v > 0:
                c1v -= 1
            else:
                c0v += 1
        if c0v < c1v:
            c0v, c1v = c1v, c0v

        c0, c1 = c0v, c1v

        r0, g0, b0 = _unpack_565(c0)
        r1, g1, b1 = _unpack_565(c1)
        palette = np.array([
            [r0, g0, b0],
            [r1, g1, b1],
            [(2 * r0 + r1) / 3, (2 * g0 + g1) / 3, (2 * b0 + b1) / 3],
            [(r0 + 2 * r1) / 3, (g0 + 2 * g1) / 3, (b0 + 2 * b1) / 3],
        ], dtype=np.float32)

        dists = ((px[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
        indices = np.argmin(dists, axis=1).astype(np.uint8)

    packed_indices = 0
    for i in range(16):
        packed_indices |= int(indices[i]) << (2 * i)

    return struct.pack("<HHI", c0, c1, packed_indices)


def _encode_alpha_block(alphas: np.ndarray) -> bytes:
    """alphas: (16,) uint8 array for one 4x4 block."""
    a_max = int(alphas.max())
    a_min = int(alphas.min())

    if a_max == a_min:
        a0, a1 = a_max, a_min
        indices = np.zeros(16, dtype=np.uint8)
    else:
        a0, a1 = a_max, a_min  # a0 > a1 selects the 8-alpha interpolation mode
        levels = np.array([
            a0,
            a1,
            (6 * a0 + 1 * a1) / 7,
            (5 * a0 + 2 * a1) / 7,
            (4 * a0 + 3 * a1) / 7,
            (3 * a0 + 4 * a1) / 7,
            (2 * a0 + 5 * a1) / 7,
            (1 * a0 + 6 * a1) / 7,
        ], dtype=np.float32)
        dists = (alphas.astype(np.float32)[:, None] - levels[None, :]) ** 2
        indices = np.argmin(dists, axis=1).astype(np.uint8)

    packed = 0
    for i in range(16):
        packed |= int(indices[i]) << (3 * i)

    idx_bytes = packed.to_bytes(6, "little")
    return struct.pack("<BB", a0, a1) + idx_bytes


def encode_dxt5(rgba: np.ndarray) -> bytes:
    """
    rgba: (H, W, 4) uint8 array. H and W must each be multiples of 4
    (pad beforehand if not).
    Returns raw DXT5-compressed bytes (no DDS header).
    """
    h, w = rgba.shape[0], rgba.shape[1]
    assert h % 4 == 0 and w % 4 == 0, "dimensions must be multiples of 4"

    out = bytearray()
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            block = rgba[by:by + 4, bx:bx + 4, :]
            rgb = block[:, :, :3].reshape(16, 3)
            alpha = block[:, :, 3].reshape(16)
            out += _encode_alpha_block(alpha)
            out += _encode_color_block(rgb)
    return bytes(out)
