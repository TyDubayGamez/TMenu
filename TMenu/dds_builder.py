"""
dds_builder.py
==============
Turns any image (PNG/JPG/BMP/whatever Pillow can open) into a DDS file that
matches the exact structure Skate 3 expects for the 256x128 graphic slots -
DXT5 compressed, the standard 128-byte header (no DX10 extension), and a
full 9-level mip chain down to 1x1. Used by the graphics side of EDIT
SKATER/PARK wherever a custom image gets written into the game.
"""

import numpy as np
from PIL import Image

from dxt5_encoder import encode_dxt5

TARGET_W = 256
TARGET_H = 128

# Fixed 128-byte DDS header - same for every file since W/H/format/mip
# count never change here, so it's just copied in as-is each time.
DDS_HEADER_TEMPLATE = bytes.fromhex(
    "444453207c00000007100a008000000000010000008000000100000009000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020000000040000004458543500000000000000000000000000000000000000000810400000000000000000000000000000000000"
)

FIT_STRETCH = "stretch"
FIT_LETTERBOX = "fit"     # preserve aspect, pad to fill canvas
FIT_COVER = "fill"        # preserve aspect, crop to fill canvas


def _to_rgba(img: Image.Image) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img


def fit_to_canvas(img: Image.Image, mode: str, pad_color=(0, 0, 0, 0)) -> Image.Image:
    """Resize/crop/pad `img` to exactly TARGET_W x TARGET_H per `mode`."""
    img = _to_rgba(img)

    if mode == FIT_STRETCH:
        return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)

    src_w, src_h = img.size
    src_aspect = src_w / src_h
    dst_aspect = TARGET_W / TARGET_H

    if mode == FIT_LETTERBOX:
        if src_aspect > dst_aspect:
            new_w = TARGET_W
            new_h = max(1, round(TARGET_W / src_aspect))
        else:
            new_h = TARGET_H
            new_w = max(1, round(TARGET_H * src_aspect))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (TARGET_W, TARGET_H), pad_color)
        offset = ((TARGET_W - new_w) // 2, (TARGET_H - new_h) // 2)
        canvas.paste(resized, offset, resized)
        return canvas

    if mode == FIT_COVER:
        if src_aspect > dst_aspect:
            new_h = TARGET_H
            new_w = max(1, round(TARGET_H * src_aspect))
        else:
            new_w = TARGET_W
            new_h = max(1, round(TARGET_W / src_aspect))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - TARGET_W) // 2
        top = (new_h - TARGET_H) // 2
        return resized.crop((left, top, left + TARGET_W, top + TARGET_H))

    raise ValueError(f"unknown fit mode: {mode}")


def apply_min_alpha(rgba: np.ndarray, min_alpha: int = 1) -> np.ndarray:
    """Clamp any alpha==0 pixel up to `min_alpha` (compatibility mode)."""
    out = rgba.copy()
    mask = out[:, :, 3] == 0
    out[mask, 3] = min_alpha
    return out


def generate_mip_chain(base_img: Image.Image):
    """Yields PIL images for each mip level from 256x128 down to 1x1,
    matching the reference file's 9-level chain."""
    w, h = base_img.size
    level = base_img
    yield level
    while not (w == 1 and h == 1):
        w = max(1, w // 2)
        h = max(1, h // 2)
        level = level.resize((w, h), Image.LANCZOS)
        yield level


def _pad_to_multiple_of_4(rgba: np.ndarray) -> np.ndarray:
    h, w = rgba.shape[0], rgba.shape[1]
    pad_h = (-h) % 4
    pad_w = (-w) % 4
    if pad_h == 0 and pad_w == 0:
        return rgba
    padded = np.zeros((h + pad_h, w + pad_w, 4), dtype=np.uint8)
    padded[:h, :w, :] = rgba
    # copy the edge pixels into the padding so odd mip sizes don't end up
    # with black/transparent smears along the edge once encoded
    if pad_h:
        padded[h:, :w, :] = rgba[-1:, :, :]
    if pad_w:
        padded[:h, w:, :] = rgba[:, -1:, :]
    if pad_h and pad_w:
        padded[h:, w:, :] = rgba[-1, -1, :]
    return padded


def build_dds(
    source_path: str,
    fit_mode: str = FIT_LETTERBOX,
    force_min_alpha: bool = False,
    min_alpha_value: int = 1,
    pad_color=(0, 0, 0, 0),
) -> bytes:
    """Full pipeline: load -> fit -> mip chain -> DXT5 encode -> assemble DDS."""
    img = Image.open(source_path)
    fitted = fit_to_canvas(img, fit_mode, pad_color=pad_color)

    payload = bytearray()
    for mip in generate_mip_chain(fitted):
        rgba = np.array(mip.convert("RGBA"), dtype=np.uint8)
        if force_min_alpha:
            rgba = apply_min_alpha(rgba, min_alpha_value)
        rgba_padded = _pad_to_multiple_of_4(rgba)
        payload += encode_dxt5(rgba_padded)

    return DDS_HEADER_TEMPLATE + bytes(payload)


def save_dds(source_path: str, dest_path: str, **kwargs) -> int:
    data = build_dds(source_path, **kwargs)
    with open(dest_path, "wb") as f:
        f.write(data)
    return len(data)
