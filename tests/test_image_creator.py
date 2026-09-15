from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
import pytest

from src import image_creator


def _wide_fixture() -> Image.Image:
    image = Image.new("RGB", (1920, 1080), "#2468a8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 1915, 1075), outline="#f7d154", width=8)
    draw.rectangle((60, 270, 300, 810), fill="#e85d75", outline="white", width=6)
    draw.ellipse((100, 320, 260, 480), fill="#f2c29b", outline="white", width=5)
    draw.rectangle((125, 475, 235, 730), fill="#18283f", outline="white", width=5)
    return image


def test_16x9_source_is_contained_without_crop_or_distortion(tmp_path):
    source = _wide_fixture()
    contained = image_creator._fit_contain(source, 1080, 1072)

    assert contained.size == (1080, 1072)
    assert contained.getpixel((0, 232)) != image_creator.NAVY
    assert contained.getpixel((1079, 232)) != image_creator.NAVY

    output_path = Path(tmp_path) / "facebook-post.jpg"
    with patch.object(image_creator, "fetch_story_image", return_value=source):
        output = image_creator.create_post_image(
            title="16:9 FULL FRAME TEST",
            brief_text="A wide test image with edge content.",
            category="International",
            story={"title": "", "description": ""},
            page_name="TEST PAGE",
        )
    image_creator.save_image(output, output_path)

    with Image.open(output_path) as saved:
        saved.load()
        assert saved.size == (1080, 1350)
        assert saved.format == "JPEG"
        assert saved.mode == "RGB"


@pytest.mark.parametrize("size", [(1920, 1080), (1080, 1920), (1000, 1000),
                                   (900, 100), (100, 900)])
def test_extreme_source_ratios_remain_contained(size):
    source = Image.new("RGB", size, "#2468a8")
    draw = ImageDraw.Draw(source)
    draw.point((0, 0), fill="white")
    draw.point((size[0] - 1, size[1] - 1), fill="white")

    target = image_creator._fit_contain(source, 1080, 1072)
    scale = min(1080 / size[0], 1072 / size[1])
    expected_size = (round(size[0] * scale), round(size[1] * scale))
    assert target.size == (1080, 1072)
    assert expected_size[0] <= 1080 and expected_size[1] <= 1072
    assert expected_size[0] / expected_size[1] == pytest.approx(size[0] / size[1], rel=0.01)


def test_side_fade_starts_at_two_to_one_portrait_threshold():
    source = Image.new("RGB", (1080, 1072), "#2468a8")
    threshold = image_creator._scrim(
        source, fade_sides=True, content_left=272, content_width=536)
    normal = image_creator._scrim(
        source, fade_sides=False, content_left=238, content_width=604)

    assert sum(threshold.getpixel((272, 500))) < sum(threshold.getpixel((540, 500)))
    assert normal.getpixel((238, 500)) == normal.getpixel((540, 500))
