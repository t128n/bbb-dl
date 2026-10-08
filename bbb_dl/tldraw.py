import json
import math
import os
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

from bbb_dl.utils import Log

SVG_NS = "http://www.w3.org/2000/svg"
XHTML_NS = "http://www.w3.org/1999/xhtml"

TLDRAW_COLORS = {
    'black': '#1d1d1d',
    'grey': '#788492',
    'gray': '#788492',
    'light-violet': '#eebefa',
    'violet': '#7746f1',
    'blue': '#1c7ed6',
    'light-blue': '#70baff',
    'yellow': '#ffc936',
    'orange': '#ff9433',
    'green': '#36b24d',
    'light-green': '#6fcf97',
    'light-red': '#ff7070',
    'red': '#ff2133',
    'white': '#ffffff',
}

TLDRAW_FONT_SIZES = {
    's': 18,
    'm': 24,
    'l': 36,
    'xl': 44,
}

TLDRAW_STROKE_SIZES = {
    's': 2,
    'm': 3.5,
    'l': 5,
    'xl': 10,
}

TLDRAW_FONTS = {
    'sans': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    'serif': 'Georgia, "Times New Roman", serif',
    'mono': '"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
    'draw': '"Caveat", "Comic Sans MS", "Chalkboard SE", cursive, sans-serif',
}


def get_color(name_or_hex: str, default: str = '#1d1d1d') -> str:
    if not name_or_hex:
        return default
    if name_or_hex in TLDRAW_COLORS:
        return TLDRAW_COLORS[name_or_hex]
    if name_or_hex.startswith('#') or name_or_hex.startswith('rgb'):
        return name_or_hex
    return default


def get_fill_color(color_name: str, fill_style: str) -> str:
    if not fill_style or fill_style == 'none':
        return 'none'
    color = get_color(color_name)
    if fill_style == 'solid':
        return color
    # semi or pattern fill
    return color + '26'


def get_stroke_width(size_name: str, default: float = 3.5) -> float:
    return TLDRAW_STROKE_SIZES.get(size_name, default)


def get_font_size(size_name: str, scale: float = 1.0) -> float:
    return TLDRAW_FONT_SIZES.get(size_name, 24) * (scale or 1.0)


def get_font_family(font_name: str) -> str:
    return TLDRAW_FONTS.get(font_name, TLDRAW_FONTS['sans'])


def get_dasharray(dash_style: str, stroke_width: float) -> Optional[str]:
    if dash_style == 'dashed':
        return f'{stroke_width * 3},{stroke_width * 3}'
    if dash_style == 'dotted':
        return f'{stroke_width},{stroke_width * 2}'
    return None


def add_rotation_transform(attrs: Dict[str, str], rotation: float, cx: float = 0.0, cy: float = 0.0):
    if rotation and abs(rotation) > 1e-4:
        deg = math.degrees(rotation)
        if cx != 0.0 or cy != 0.0:
            attrs['transform'] = f'rotate({deg:.2f} {cx:.2f} {cy:.2f})'
        else:
            attrs['transform'] = f'rotate({deg:.2f})'


def render_text_shape(parent: Element, shape_data: Dict[str, Any], slide_w: int, slide_h: int):
    props = shape_data.get('props', {})
    text = props.get('text', '')
    if not text:
        return

    x = float(shape_data.get('x', 0))
    y = float(shape_data.get('y', 0))
    rotation = float(shape_data.get('rotation', 0))
    scale = float(props.get('scale', 1.0))
    font_size = get_font_size(props.get('size', 'm'), scale)
    font_family = get_font_family(props.get('font', 'sans'))
    color = get_color(props.get('color', 'black'))
    align = props.get('align', 'start')
    auto_size = props.get('autoSize', True)
    w = float(props.get('w', 0))

    text_align = 'left'
    if align == 'middle':
        text_align = 'center'
    elif align == 'end':
        text_align = 'right'

    fo_w = max(w + 100, float(slide_w - x)) if auto_size else (w if w > 0 else float(slide_w - x))
    fo_h = max(200.0, float(slide_h - y))

    fo_attrs = {
        'x': f'{x:.2f}',
        'y': f'{y:.2f}',
        'width': f'{fo_w:.2f}',
        'height': f'{fo_h:.2f}',
    }
    add_rotation_transform(fo_attrs, rotation, cx=x, cy=y)

    fo = ET.SubElement(parent, f'{{{SVG_NS}}}foreignObject', fo_attrs)

    div_style = (
        f'font-family: {font_family}; '
        f'font-size: {font_size:.1f}px; '
        f'color: {color}; '
        f'text-align: {text_align}; '
        'white-space: pre-wrap; '
        'word-break: break-word; '
        'line-height: 1.35; '
    )
    if auto_size:
        div_style += 'width: max-content; '
    elif w > 0:
        div_style += f'width: {w:.2f}px; '

    div = ET.SubElement(fo, f'{{{XHTML_NS}}}div', {'style': div_style})
    div.text = text


def render_draw_shape(parent: Element, shape_data: Dict[str, Any], is_highlight: bool = False):
    props = shape_data.get('props', {})
    segments = props.get('segments', [])
    if not segments:
        return

    x = float(shape_data.get('x', 0))
    y = float(shape_data.get('y', 0))
    rotation = float(shape_data.get('rotation', 0))
    color = get_color(props.get('color', 'black'))
    stroke_width = get_stroke_width(props.get('size', 'm'))
    fill_style = props.get('fill', 'none')
    fill_color = get_fill_color(props.get('color', 'black'), fill_style)
    is_closed = props.get('isClosed', False)

    g_attrs = {'transform': f'translate({x:.2f}, {y:.2f})'}
    add_rotation_transform(g_attrs, rotation)
    group = ET.SubElement(parent, f'{{{SVG_NS}}}g', g_attrs)

    for seg in segments:
        points = seg.get('points', [])
        if not points:
            continue
        if len(points) == 1:
            pt = points[0]
            r = (stroke_width * 2) if is_highlight else (stroke_width / 2)
            c_attrs = {
                'cx': f"{pt.get('x', 0):.2f}",
                'cy': f"{pt.get('y', 0):.2f}",
                'r': f'{r:.2f}',
                'fill': color,
            }
            if is_highlight:
                c_attrs['opacity'] = '0.35'
            ET.SubElement(group, f'{{{SVG_NS}}}circle', c_attrs)
        else:
            d_parts = []
            for i, pt in enumerate(points):
                cmd = 'M' if i == 0 else 'L'
                d_parts.append(f"{cmd} {pt.get('x', 0):.2f} {pt.get('y', 0):.2f}")
            if is_closed:
                d_parts.append('Z')
            d = ' '.join(d_parts)

            p_attrs = {
                'd': d,
                'stroke': color,
                'fill': fill_color if is_closed else 'none',
                'stroke-linejoin': 'round',
            }
            if is_highlight:
                p_attrs['stroke-width'] = f'{(stroke_width * 4):.2f}'
                p_attrs['stroke-linecap'] = 'square'
                p_attrs['opacity'] = '0.35'
            else:
                p_attrs['stroke-width'] = f'{stroke_width:.2f}'
                p_attrs['stroke-linecap'] = 'round'

            ET.SubElement(group, f'{{{SVG_NS}}}path', p_attrs)


def render_geo_shape(parent: Element, shape_data: Dict[str, Any]):
    props = shape_data.get('props', {})
    geo = props.get('geo', 'rectangle')
    w = float(props.get('w', 100))
    h = float(props.get('h', 100))
    x = float(shape_data.get('x', 0))
    y = float(shape_data.get('y', 0))
    rotation = float(shape_data.get('rotation', 0))
    color = get_color(props.get('color', 'black'))
    stroke_width = get_stroke_width(props.get('size', 'm'))
    fill_color = get_fill_color(props.get('color', 'black'), props.get('fill', 'none'))
    dash = props.get('dash', 'draw')

    g_attrs = {'transform': f'translate({x:.2f}, {y:.2f})'}
    add_rotation_transform(g_attrs, rotation)
    group = ET.SubElement(parent, f'{{{SVG_NS}}}g', g_attrs)

    common_attrs = {
        'stroke': color,
        'stroke-width': f'{stroke_width:.2f}',
        'fill': fill_color,
    }
    dasharray = get_dasharray(dash, stroke_width)
    if dasharray:
        common_attrs['stroke-dasharray'] = dasharray

    if geo == 'rectangle':
        rect_attrs = dict(common_attrs, x='0', y='0', width=f'{w:.2f}', height=f'{h:.2f}', rx='4', ry='4')
        ET.SubElement(group, f'{{{SVG_NS}}}rect', rect_attrs)
    elif geo in ('ellipse', 'oval'):
        ellipse_attrs = dict(
            common_attrs,
            cx=f'{(w / 2):.2f}',
            cy=f'{(h / 2):.2f}',
            rx=f'{(w / 2):.2f}',
            ry=f'{(h / 2):.2f}',
        )
        ET.SubElement(group, f'{{{SVG_NS}}}ellipse', ellipse_attrs)
    elif geo == 'triangle':
        poly_attrs = dict(
            common_attrs,
            points=f'{(w / 2):.2f},0 {w:.2f},{h:.2f} 0,{h:.2f}',
        )
        ET.SubElement(group, f'{{{SVG_NS}}}polygon', poly_attrs)
    elif geo == 'diamond':
        poly_attrs = dict(
            common_attrs,
            points=f'{(w / 2):.2f},0 {w:.2f},{(h / 2):.2f} {(w / 2):.2f},{h:.2f} 0,{(h / 2):.2f}',
        )
        ET.SubElement(group, f'{{{SVG_NS}}}polygon', poly_attrs)
    else:
        rect_attrs = dict(common_attrs, x='0', y='0', width=f'{w:.2f}', height=f'{h:.2f}', rx='4', ry='4')
        ET.SubElement(group, f'{{{SVG_NS}}}rect', rect_attrs)

    geo_text = props.get('text', '')
    if geo_text:
        fo = ET.SubElement(
            group,
            f'{{{SVG_NS}}}foreignObject',
            {
                'x': '0',
                'y': '0',
                'width': f'{w:.2f}',
                'height': f'{h:.2f}',
            },
        )
        font_size = get_font_size(props.get('size', 'm'))
        div_style = (
            'display: flex; align-items: center; justify-content: center; '
            f'width: 100%; height: 100%; text-align: center; color: {color}; '
            f'font-size: {font_size:.1f}px; white-space: pre-wrap;'
        )
        div = ET.SubElement(fo, f'{{{XHTML_NS}}}div', {'style': div_style})
        div.text = geo_text


def render_line_shape(parent: Element, shape_data: Dict[str, Any]):
    props = shape_data.get('props', {})
    handles = props.get('handles', {})
    start = handles.get('start', {'x': 0, 'y': 0})
    end = handles.get('end', {'x': 0, 'y': 0})

    x = float(shape_data.get('x', 0))
    y = float(shape_data.get('y', 0))
    rotation = float(shape_data.get('rotation', 0))
    color = get_color(props.get('color', 'black'))
    stroke_width = get_stroke_width(props.get('size', 'm'))

    g_attrs = {'transform': f'translate({x:.2f}, {y:.2f})'}
    add_rotation_transform(g_attrs, rotation)
    group = ET.SubElement(parent, f'{{{SVG_NS}}}g', g_attrs)

    line_attrs = {
        'x1': f"{start.get('x', 0):.2f}",
        'y1': f"{start.get('y', 0):.2f}",
        'x2': f"{end.get('x', 0):.2f}",
        'y2': f"{end.get('y', 0):.2f}",
        'stroke': color,
        'stroke-width': f'{stroke_width:.2f}',
        'stroke-linecap': 'round',
    }
    dasharray = get_dasharray(props.get('dash', 'draw'), stroke_width)
    if dasharray:
        line_attrs['stroke-dasharray'] = dasharray

    ET.SubElement(group, f'{{{SVG_NS}}}line', line_attrs)


def render_arrow_shape(parent: Element, shape_data: Dict[str, Any]):
    props = shape_data.get('props', {})
    start = props.get('start', {'x': 0, 'y': 0})
    end = props.get('end', {'x': 0, 'y': 0})

    x = float(shape_data.get('x', 0))
    y = float(shape_data.get('y', 0))
    rotation = float(shape_data.get('rotation', 0))
    color = get_color(props.get('color', 'black'))
    stroke_width = get_stroke_width(props.get('size', 'm'))

    g_attrs = {'transform': f'translate({x:.2f}, {y:.2f})'}
    add_rotation_transform(g_attrs, rotation)
    group = ET.SubElement(parent, f'{{{SVG_NS}}}g', g_attrs)

    x1 = float(start.get('x', 0))
    y1 = float(start.get('y', 0))
    x2 = float(end.get('x', 0))
    y2 = float(end.get('y', 0))

    line_attrs = {
        'x1': f'{x1:.2f}',
        'y1': f'{y1:.2f}',
        'x2': f'{x2:.2f}',
        'y2': f'{y2:.2f}',
        'stroke': color,
        'stroke-width': f'{stroke_width:.2f}',
        'stroke-linecap': 'round',
    }
    ET.SubElement(group, f'{{{SVG_NS}}}line', line_attrs)

    # Arrowhead at end if requested
    arrowhead_end = props.get('arrowheadEnd', 'arrow')
    if arrowhead_end != 'none':
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_len = stroke_width * 4
        arrow_angle = math.pi / 6
        p1_x = x2 - arrow_len * math.cos(angle - arrow_angle)
        p1_y = y2 - arrow_len * math.sin(angle - arrow_angle)
        p2_x = x2 - arrow_len * math.cos(angle + arrow_angle)
        p2_y = y2 - arrow_len * math.sin(angle + arrow_angle)

        poly_attrs = {
            'points': f'{x2:.2f},{y2:.2f} {p1_x:.2f},{p1_y:.2f} {p2_x:.2f},{p2_y:.2f}',
            'fill': color,
            'stroke': color,
            'stroke-width': '1',
        }
        ET.SubElement(group, f'{{{SVG_NS}}}polygon', poly_attrs)


def render_note_shape(parent: Element, shape_data: Dict[str, Any]):
    props = shape_data.get('props', {})
    text = props.get('text', '')
    x = float(shape_data.get('x', 0))
    y = float(shape_data.get('y', 0))
    rotation = float(shape_data.get('rotation', 0))
    w = 200.0
    h = 200.0

    color = props.get('color', 'yellow')
    bg_color = get_color(color, '#ffc936')

    g_attrs = {'transform': f'translate({x:.2f}, {y:.2f})'}
    add_rotation_transform(g_attrs, rotation)
    group = ET.SubElement(parent, f'{{{SVG_NS}}}g', g_attrs)

    ET.SubElement(
        group,
        f'{{{SVG_NS}}}rect',
        {
            'x': '0',
            'y': '0',
            'width': f'{w:.2f}',
            'height': f'{h:.2f}',
            'rx': '8',
            'ry': '8',
            'fill': bg_color,
            'stroke': '#1d1d1d20',
            'stroke-width': '1',
        },
    )

    if text:
        fo = ET.SubElement(
            group,
            f'{{{SVG_NS}}}foreignObject',
            {
                'x': '10',
                'y': '10',
                'width': f'{(w - 20):.2f}',
                'height': f'{(h - 20):.2f}',
            },
        )
        font_size = get_font_size(props.get('size', 's'))
        div_style = (
            f'font-size: {font_size:.1f}px; color: #1d1d1d; '
            'white-space: pre-wrap; word-break: break-word;'
        )
        div = ET.SubElement(fo, f'{{{XHTML_NS}}}div', {'style': div_style})
        div.text = text


def render_shape(parent: Element, shape_data: Dict[str, Any], slide_w: int, slide_h: int):
    shape_type = shape_data.get('type')
    if shape_type == 'text':
        render_text_shape(parent, shape_data, slide_w, slide_h)
    elif shape_type == 'draw':
        render_draw_shape(parent, shape_data, is_highlight=False)
    elif shape_type == 'highlight':
        render_draw_shape(parent, shape_data, is_highlight=True)
    elif shape_type == 'geo':
        render_geo_shape(parent, shape_data)
    elif shape_type == 'line':
        render_line_shape(parent, shape_data)
    elif shape_type == 'arrow':
        render_arrow_shape(parent, shape_data)
    elif shape_type == 'note':
        render_note_shape(parent, shape_data)


def inject_tldraw_into_shapes(shapes_path: str, tldraw_path: str, loaded_shapes: Element) -> Element:
    """Parses tldraw.json and injects converted whiteboard elements into shapes.svg and loaded_shapes."""
    if not os.path.isfile(tldraw_path):
        return loaded_shapes

    try:
        with open(tldraw_path, 'r', encoding='utf-8') as f:
            tldraw_data = json.load(f)
    except Exception as err:
        Log.warning(f"Could not load tldraw.json: {err}")
        return loaded_shapes

    # Find canvas slide dimensions from images in loaded_shapes
    slide_w = 1920
    slide_h = 1080
    slides = loaded_shapes.findall(f".//{{{SVG_NS}}}image[@class='slide']")
    if not slides:
        slides = loaded_shapes.findall(".//image[@class='slide']")
    if slides:
        try:
            slide_w = int(float(slides[0].get('width', '1920')))
            slide_h = int(float(slides[0].get('height', '1080')))
        except Exception:
            pass

    # Extract pages / shapes mapping
    # Format 1: {"bbb_version": "...", "1": {"shapes": [...]}, "2": {"shapes": [...]}}
    # Format 2: {"shapes": [...]}
    # Format 3: [{"shapes": [...]}, ...] or list of shapes
    pages_shapes: Dict[str, List[Dict[str, Any]]] = {}
    if isinstance(tldraw_data, dict):
        if 'shapes' in tldraw_data:
            pages_shapes['1'] = tldraw_data['shapes']
        else:
            for k, v in tldraw_data.items():
                if isinstance(v, dict) and 'shapes' in v:
                    # Clean slide number if prefixed
                    slide_num = k
                    if not slide_num.isdigit():
                        digits = [c for c in slide_num if c.isdigit()]
                        slide_num = "".join(digits) if digits else "1"
                    pages_shapes[slide_num] = v['shapes']
    elif isinstance(tldraw_data, list):
        pages_shapes['1'] = tldraw_data

    total_injected = 0
    for slide_num, shapes in pages_shapes.items():
        if not shapes:
            continue

        # Look for existing canvas element in loaded_shapes
        canvas = None
        for child in loaded_shapes:
            if child.get('id') == f'canvas{slide_num}':
                canvas = child
                break
        if canvas is None:
            canvas = ET.SubElement(
                loaded_shapes,
                f'{{{SVG_NS}}}g',
                {
                    'id': f'canvas{slide_num}',
                    'display': 'none',
                },
            )

        for idx, entry in enumerate(shapes):
            entry_id = entry.get('id', idx)
            ts = float(entry.get('timestamp', 0.0))
            undo = float(entry.get('undo', -1.0))
            shape_data = entry.get('shape_data', {})
            shape_id = shape_data.get('id', f'shape_{idx}')

            g_drawing = ET.SubElement(
                canvas,
                f'{{{SVG_NS}}}g',
                {
                    'id': f'tldraw_{slide_num}_{entry_id}',
                    'shape': str(shape_id),
                    'timestamp': str(ts),
                    'undo': str(undo),
                    'style': 'visibility:hidden',
                },
            )

            render_shape(g_drawing, shape_data, slide_w, slide_h)
            total_injected += 1

    if total_injected > 0:
        Log.info(f"Injected {total_injected} whiteboard annotations from tldraw.json into shapes.svg")

        # Register namespaces for clean SVG XML output
        ET.register_namespace('', SVG_NS)
        ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
        ET.register_namespace('xhtml', XHTML_NS)

        try:
            xml_bytes = ET.tostring(loaded_shapes, encoding='utf-8')
            with open(shapes_path, 'wb') as f:
                f.write(xml_bytes)
        except Exception as err:
            Log.warning(f"Unable to write modified shapes.svg: {err}")

    return loaded_shapes
