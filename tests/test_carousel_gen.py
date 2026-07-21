import pytest
from PIL import Image

from src.generator.carousel_gen import (
    MAX_SLIDES,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    generate_carousel,
)


def test_generate_carousel_creates_expected_files(tmp_path):
    headlines = ["新NISAの仕組みをやさしく解説", "つみたて投資枠と成長投資枠の違い"]
    paths = generate_carousel(headlines, output_dir=tmp_path)

    assert len(paths) == 2
    for path in paths:
        assert path.exists()
        with Image.open(path) as img:
            assert img.size == (SLIDE_WIDTH, SLIDE_HEIGHT)


def test_generate_carousel_rejects_too_many_slides(tmp_path):
    headlines = ["見出し"] * (MAX_SLIDES + 1)
    with pytest.raises(ValueError):
        generate_carousel(headlines, output_dir=tmp_path)


def test_generate_carousel_rejects_empty_input(tmp_path):
    with pytest.raises(ValueError):
        generate_carousel([], output_dir=tmp_path)


def test_long_text_shrinks_font_and_still_fits(tmp_path):
    long_text = "シンガポール在住投資家が語る、日本・シンガポール・フィリピン3拠点の資産運用リアル体験談と失敗から学んだこと" * 2
    paths = generate_carousel([long_text], output_dir=tmp_path)

    with Image.open(paths[0]) as img:
        assert img.size == (SLIDE_WIDTH, SLIDE_HEIGHT)


def test_output_filenames_are_ordered(tmp_path):
    paths = generate_carousel(["一枚目", "二枚目", "三枚目"], output_dir=tmp_path)
    names = [p.name for p in paths]
    assert names == ["slide_01.png", "slide_02.png", "slide_03.png"]
