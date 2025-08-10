from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def render_math_svg(text, font_size=20):
    t = str(conditional_escape(text or ""))
    try:
        fs = int(font_size)
    except Exception:
        fs = 20
    char_w = int(fs * 0.6)
    pad_x = 12
    width = max(80, pad_x * 2 + char_w * len(t))
    height = int(fs * 2)
    cx = width // 2
    cy = int(height * 0.68)
    svg = (
        f'<svg id="challenge-svg" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Solve this: {t}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" ry="8" '
        f'fill="none" stroke="#888" stroke-opacity="0.3" />'
        f'<text x="{cx}" y="{cy}" fill="currentColor" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace" '
        f'font-size="{fs}" text-anchor="middle">{t}</text>'
        f"</svg>"
    )
    return mark_safe(svg)
