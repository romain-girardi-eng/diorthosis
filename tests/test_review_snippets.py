"""Review snippets must survive CropBox ≠ MediaBox.

The documented crash (docs/troubleshooting.md) is a coordinate-space bug,
not a bad edition: pdfminer reports line boxes in MediaBox space; pdfium
renders the CropBox. The numbers below are Segrave *Insolubles* page 40.
"""

from diorthosis.review import bitmap_crop_rect

# page 40 of insolubles.pdf, recorded 2026-08-05
MEDIA = (0.0, 0.0, 612.0, 792.0)
CROP = (84.96, 64.44, 527.04, 727.56)
SCALE = 2.2


def _image_size(crop=CROP, scale=SCALE) -> tuple[int, int]:
  return (int((crop[2] - crop[0]) * scale), int((crop[3] - crop[1]) * scale))


def test_cropbox_band_stays_inside_the_bitmap() -> None:
  """An apparatus band sitting on the cropped page used to crop outside it."""
  # a foot-band near the visible bottom (crop y0 = 64.44)
  boxes = [(120.0, 80.0, 480.0, 130.0)]
  width, height = _image_size()
  rect = bitmap_crop_rect(
    boxes, scale=SCALE, image_size=(width, height),
    cropbox=CROP, mediabox_height=MEDIA[3],
  )
  assert rect is not None
  left, top, right, bottom = rect
  assert 0 <= left < right <= width
  assert 0 <= top < bottom <= height


def test_mediabox_crop_without_translation_would_leave_the_image() -> None:
  """The old formula: ``(media_h - y) * scale`` on a CropBox-sized bitmap."""
  boxes = [(120.0, 70.0, 480.0, 100.0)]
  width, height = _image_size()
  naive_top = int((MEDIA[3] - 100.0) * SCALE)
  assert naive_top > height  # this is the crash
  rect = bitmap_crop_rect(
    boxes, scale=SCALE, image_size=(width, height),
    cropbox=CROP, mediabox_height=MEDIA[3],
  )
  assert rect is not None
  assert rect[1] < height


def test_identical_boxes_are_a_no_op_translate() -> None:
  """When CropBox == MediaBox the crop is the historical one, clamped."""
  boxes = [(100.0, 200.0, 300.0, 240.0)]
  media = (0.0, 0.0, 612.0, 792.0)
  size = (612, 792)
  with_box = bitmap_crop_rect(
    boxes, scale=1.0, image_size=size, cropbox=media, mediabox_height=792.0,
    pad=0.0,
  )
  without = bitmap_crop_rect(
    boxes, scale=1.0, image_size=size, cropbox=None, mediabox_height=792.0,
    pad=0.0,
  )
  assert with_box == without == (100, 792 - 240, 300, 792 - 200)


def test_empty_intersection_is_a_missing_snippet_not_a_crash() -> None:
  """A box wholly outside the crop is skipped, not cropped into an empty tile."""
  boxes = [(10.0, 10.0, 20.0, 20.0)]  # below and left of the crop
  rect = bitmap_crop_rect(
    boxes, scale=SCALE, image_size=_image_size(),
    cropbox=CROP, mediabox_height=MEDIA[3], pad=0.0,
  )
  assert rect is None


def test_no_boxes_is_none() -> None:
  assert bitmap_crop_rect(
    [], scale=1.0, image_size=(100, 100),
    cropbox=None, mediabox_height=792.0,
  ) is None
