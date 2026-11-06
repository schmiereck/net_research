"""Image classification tasks: geometric shapes and digit OCR."""
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..spec import COLORS, TaskSpec
from .base import SupervisedTask

DATA = Path(__file__).resolve().parents[2] / "data"


def colorize(masks: np.ndarray, rng, noise: float = 0.0) -> np.ndarray:
    """masks [B,16,16] in {0,1} -> [B,3,16,16] with a random colour per sample (+ pixel noise)."""
    B = masks.shape[0]
    cols = np.array(COLORS, dtype=np.float32)[rng.integers(len(COLORS), size=B)]   # [B,3]
    img = masks[:, None, :, :].astype(np.float32) * cols[:, :, None, None]
    if noise > 0:
        flip = rng.random(img.shape) < noise
        img = np.where(flip, 1.0 - img, img).astype(np.float32)
    return img


SHAPE_NAMES = ["square", "filled_square", "circle", "triangle", "plus", "x"]


def draw_shape(cls: int, rng) -> np.ndarray:
    s = int(rng.integers(6, 13))
    x0 = int(rng.integers(0, 16 - s + 1))
    y0 = int(rng.integers(0, 16 - s + 1))
    x1, y1 = x0 + s - 1, y0 + s - 1
    im = Image.new("L", (16, 16), 0)
    d = ImageDraw.Draw(im)
    if cls == 0:
        d.rectangle([x0, y0, x1, y1], outline=1)
    elif cls == 1:
        d.rectangle([x0, y0, x1, y1], fill=1)
    elif cls == 2:
        d.ellipse([x0, y0, x1, y1], outline=1)
    elif cls == 3:
        d.polygon([(x0 + (s - 1) / 2, y0), (x0, y1), (x1, y1)], fill=1)
    elif cls == 4:
        cx, cy = x0 + s // 2, y0 + s // 2
        d.line([x0, cy, x1, cy], fill=1)
        d.line([cx, y0, cx, y1], fill=1)
    else:
        d.line([x0, y0, x1, y1], fill=1)
        d.line([x0, y1, x1, y0], fill=1)
    return np.array(im, dtype=np.uint8)


class Shapes(SupervisedTask):
    def __init__(self):
        self.spec = TaskSpec("shapes", "image", "supervised", "class", len(SHAPE_NAMES), seq_len=1,
                             chance=1 / len(SHAPE_NAMES),
                             description="6 geometric shapes, random size/pos/colour, 2% pixel noise")

    def sample(self, batch, rng, split="train"):
        y = rng.integers(len(SHAPE_NAMES), size=batch)
        masks = np.stack([draw_shape(int(c), rng) for c in y])
        return {"obs": colorize(masks, rng, noise=0.02)[None], "target": y[None].astype(np.int64),
                "mask": np.ones((1, batch), np.float32)}


TEST_FONT_PREFIXES = ("georgia", "trebuc", "constan", "segoepr")
FONT_FAMILIES = ["arial", "times", "cour", "verdana", "georgia", "consola", "tahoma", "calibri", "cambria",
                 "segoeui", "trebuc", "comic", "impact", "lucon", "pala", "bahnschrift", "candara", "corbel",
                 "constan", "gadugi", "segoepr", "framd", "sylfaen", "ebrima", "micross"]


def _font_files():
    fdir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    if not fdir.exists():
        return []
    files = []
    for f in sorted(fdir.glob("*.tt[fc]")):
        stem = f.stem.lower()
        if any(stem.startswith(n) for n in FONT_FAMILIES) and "segoeuisl" not in stem:
            files.append(f)
    return files


def _render_digit(font_path, digit, rng):
    font = ImageFont.truetype(str(font_path), int(rng.integers(44, 62)))
    im = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(im).text((48, 48), str(digit), fill=255, font=font, anchor="mm")
    im = im.rotate(float(rng.uniform(-12, 12)), resample=Image.BILINEAR)
    bbox = im.getbbox()
    if bbox is None:
        return None
    crop = im.crop(bbox)
    h = int(rng.integers(11, 16))
    w = max(1, min(16, int(round(crop.width * h / crop.height))))
    arr = np.array(crop.resize((w, h), Image.BOX), dtype=np.float32) / 255.0
    m = (arr > rng.uniform(0.3, 0.5)).astype(np.uint8)
    out = np.zeros((16, 16), dtype=np.uint8)
    x, y = int(rng.integers(0, 16 - w + 1)), int(rng.integers(0, 16 - h + 1))
    out[y:y + h, x:x + w] = m
    return out


def build_digit_cache(path=DATA / "digits.npz", per_font_train=30, per_font_test=20, seed=0):
    rng = np.random.default_rng(seed)
    data = {"train": ([], []), "test": ([], [])}
    files = _font_files()
    if not files:
        raise RuntimeError("no system fonts found for the digits task")
    for f in files:
        split = "test" if f.stem.lower().startswith(TEST_FONT_PREFIXES) else "train"
        n = per_font_test if split == "test" else per_font_train
        for digit in range(10):
            for _ in range(n):
                m = _render_digit(f, digit, rng)
                if m is not None and m.sum() > 3:
                    data[split][0].append(m)
                    data[split][1].append(digit)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, xtr=np.stack(data["train"][0]), ytr=np.array(data["train"][1]),
                        xte=np.stack(data["test"][0]), yte=np.array(data["test"][1]),
                        fonts=np.array([f.name for f in files]))
    return path


class Digits(SupervisedTask):
    def __init__(self):
        self.spec = TaskSpec("digits", "image", "supervised", "class", 10, seq_len=1, chance=0.1,
                             description="digit OCR from system fonts; test fonts held out")
        path = DATA / "digits.npz"
        if not path.exists():
            build_digit_cache(path)
        z = np.load(path)
        self.x = {"train": z["xtr"], "test": z["xte"]}
        self.y = {"train": z["ytr"], "test": z["yte"]}

    def sample(self, batch, rng, split="train"):
        idx = rng.integers(len(self.y[split]), size=batch)
        return {"obs": colorize(self.x[split][idx], rng, noise=0.01)[None],
                "target": self.y[split][idx][None].astype(np.int64), "mask": np.ones((1, batch), np.float32)}
