import numpy as np

from ...spec import OBS_SHAPE


def canvas():
    return np.zeros(OBS_SHAPE, dtype=np.float32)


def put(img, x, y, color):
    if 0 <= x < 16 and 0 <= y < 16:
        img[:, y, x] = color


def sign(v):
    return (v > 0) - (v < 0)
