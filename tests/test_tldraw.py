import json
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from bbb_dl.main import get_parser
from bbb_dl.tldraw import (
    SVG_NS,
    XHTML_NS,
    get_color,
    get_font_family,
    get_font_size,
    get_stroke_width,
    inject_tldraw_into_shapes,
    render_shape,
)


def test_tldraw_helpers():
    assert get_color("black") == "#1d1d1d"
    assert get_color("red") == "#ff2133"
    assert get_color("#123456") == "#123456"
    assert get_color("unknown_color") == "#1d1d1d"

    assert get_stroke_width("s") == 2
    assert get_stroke_width("xl") == 10

    assert get_font_size("m", 1.0) == 24
    assert get_font_size("s", 2.0) == 36

    assert "serif" in get_font_family("serif")


def test_render_text_shape():
    root = Element(f"{{{SVG_NS}}}svg")
    shape_data = {
        "type": "text",
        "x": 50,
        "y": 100,
        "rotation": 0,
        "props": {
            "text": "Hello Whiteboard\nLine 2",
            "size": "m",
            "font": "serif",
            "color": "black",
            "w": 500,
            "autoSize": True,
        },
    }
    render_shape(root, shape_data, slide_w=1920, slide_h=1080)
    fo = root.find(f".//{{{SVG_NS}}}foreignObject")
    assert fo is not None
    assert fo.get("x") == "50.00"
    assert fo.get("y") == "100.00"

    div = fo.find(f".//{{{XHTML_NS}}}div")
    assert div is not None
    assert div.text == "Hello Whiteboard\nLine 2"
    assert "Georgia" in div.get("style", "")


def test_render_draw_shape():
    root = Element(f"{{{SVG_NS}}}svg")
    shape_data = {
        "type": "draw",
        "x": 10,
        "y": 20,
        "props": {
            "color": "blue",
            "size": "s",
            "segments": [
                {
                    "type": "free",
                    "points": [{"x": 0, "y": 0}, {"x": 5, "y": 10}, {"x": 20, "y": 30}],
                }
            ],
        },
    }
    render_shape(root, shape_data, slide_w=1920, slide_h=1080)
    path = root.find(f".//{{{SVG_NS}}}path")
    assert path is not None
    assert "M 0.00 0.00 L 5.00 10.00 L 20.00 30.00" in path.get("d")
    assert path.get("stroke") == "#1c7ed6"


def test_render_geo_shapes():
    root = Element(f"{{{SVG_NS}}}svg")
    rect_data = {
        "type": "geo",
        "x": 100,
        "y": 100,
        "props": {"geo": "rectangle", "w": 200, "h": 150, "color": "green", "text": "Box label"},
    }
    render_shape(root, rect_data, slide_w=1920, slide_h=1080)
    rect = root.find(f".//{{{SVG_NS}}}rect")
    assert rect is not None
    assert rect.get("width") == "200.00"
    assert rect.get("height") == "150.00"

    fo = root.find(f".//{{{SVG_NS}}}foreignObject")
    assert fo is not None
    div = fo.find(f".//{{{XHTML_NS}}}div")
    assert div.text == "Box label"


def test_render_line_and_arrow():
    root = Element(f"{{{SVG_NS}}}svg")
    arrow_data = {
        "type": "arrow",
        "x": 0,
        "y": 0,
        "props": {
            "start": {"x": 10, "y": 10},
            "end": {"x": 100, "y": 100},
            "color": "red",
            "arrowheadEnd": "arrow",
        },
    }
    render_shape(root, arrow_data, slide_w=1920, slide_h=1080)
    line = root.find(f".//{{{SVG_NS}}}line")
    assert line is not None
    poly = root.find(f".//{{{SVG_NS}}}polygon")
    assert poly is not None


def test_inject_tldraw_into_shapes(tmp_path):
    shapes_svg_content = """<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" id="svgfile" viewBox="0 0 1920 1080">
      <image id="image1" class="slide" in="0.0" out="100.0" width="1920" height="1080" x="0" y="0" />
    </svg>"""
    shapes_path = str(tmp_path / "shapes.svg")
    with open(shapes_path, "w", encoding="utf-8") as f:
        f.write(shapes_svg_content)

    tldraw_data = {
        "bbb_version": "3.0.17",
        "1": {
            "shapes": [
                {
                    "id": 1,
                    "timestamp": 5.0,
                    "undo": -1.0,
                    "shape_data": {
                        "id": "shape:abc",
                        "type": "text",
                        "x": 60,
                        "y": 80,
                        "props": {"text": "Lecture Note", "size": "m", "w": 400, "autoSize": True},
                    },
                }
            ]
        },
    }
    tldraw_path = str(tmp_path / "tldraw.json")
    with open(tldraw_path, "w", encoding="utf-8") as f:
        json.dump(tldraw_data, f)

    root = ET.fromstring(shapes_svg_content)
    updated_root = inject_tldraw_into_shapes(shapes_path, tldraw_path, root)

    canvas1 = updated_root.find(f".//{{{SVG_NS}}}g[@id='canvas1']")
    assert canvas1 is not None

    shape_g = canvas1.find(f".//{{{SVG_NS}}}g[@id='tldraw_1_1']")
    assert shape_g is not None
    assert shape_g.get("shape") == "shape:abc"
    assert shape_g.get("timestamp") == "5.0"
    assert shape_g.get("undo") == "-1.0"
    assert shape_g.get("style") == "visibility:hidden"

    # Also verify file on disk was updated
    with open(shapes_path, "r", encoding="utf-8") as f:
        disk_content = f.read()
    assert "tldraw_1_1" in disk_content
    assert "Lecture Note" in disk_content


def test_audiocodec_default_is_aac():
    parser = get_parser()
    args = parser.parse_args(["https://example.com/playback/presentation/2.3/123-456"])
    assert args.audiocodec == "aac"
