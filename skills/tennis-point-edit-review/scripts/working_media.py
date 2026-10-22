"""Orientation-aware 1080p working-image budget, independent of final output."""
from fractions import Fraction


def within_budget(width, height):
    return min(width, height) <= 1080 and max(width, height) <= 1920


def require_budget(width, height, label='Working source'):
    if min(width, height) < 1 or not within_budget(width, height):
        raise ValueError(label + ' exceeds 1080p: use a capped working copy or a smaller native ROI')


def fit_size(width, height, even=False):
    if min(width, height) < 1:
        raise ValueError('Positive image dimensions required')
    scale = min(Fraction(1), Fraction(1920, max(width, height)), Fraction(1080, min(width, height)))
    result = [max(1, round(x * scale)) for x in (width, height)]
    if even: result = [max(2, x + x % 2) for x in result]
    require_budget(*result)
    return tuple(result)


def working_size(width, height, requested_width=None):
    if requested_width is None:
        return fit_size(width, height, even=True)
    if type(requested_width) is not int or requested_width < 2:
        raise ValueError('Working width must be an integer >= 2')
    w, h = requested_width, max(2, round(Fraction(height * requested_width, width)))
    w, h = w + w % 2, h + h % 2
    require_budget(w, h)
    return w, h


def bounded_image(pixels):
    """Navigation composites only; never resize native precision evidence."""
    import cv2
    height, width = pixels.shape[:2]
    size = fit_size(width, height)
    return pixels if size == (width, height) else cv2.resize(pixels, size, interpolation=cv2.INTER_AREA)
