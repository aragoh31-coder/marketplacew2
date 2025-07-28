import io, base64, random, math
from PIL import Image, ImageDraw, ImageFilter

SIZE, R, SEGS = 200, 80, 12


def make_cut_circle():
    """
    Generates a base64‐encoded PNG of a circle with one missing segment.
    Returns: (img_b64, missing_index)
    """
    missing = random.randrange(SEGS)
    img = Image.new('RGBA', (SIZE, SIZE), (30, 30, 50, 240))
    draw = ImageDraw.Draw(img)
    cx, cy = SIZE//2, SIZE//2

    draw.ellipse(
        [cx-R, cy-R, cx+R, cy+R],
        fill=(40, 40, 60, 240),
        outline=(255,255,255,200),
        width=3
    )

    colors = [(255,120,120), (120,220,120), (120,120,255)]
    for i in range(SEGS):
        if i == missing:
            continue
        jitter = random.uniform(-2,2)
        start = i * 360/SEGS + jitter
        end   = (i+1) * 360/SEGS - jitter
        draw.pieslice(
            [cx-R, cy-R, cx+R, cy+R],
            start, end,
            fill=random.choice(colors),
            outline=(255,255,255,150),
            width=2
        )

    gloss = Image.new('RGBA', (SIZE, SIZE), (255,255,255,0))
    gd    = ImageDraw.Draw(gloss)
    gd.ellipse(
        [cx-R, cy-R-10, cx+R, cy+R-40],
        fill=(255,255,255,30)
    )
    img = Image.alpha_composite(img, gloss)
    img = img.filter(ImageFilter.GaussianBlur(0.5))

    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64, missing


def validate_click(click_x: int, click_y: int, missing: int) -> bool:
    """
    Validates that the user clicked inside the missing segment.
    """
    cx, cy = SIZE//2, SIZE//2
    dx, dy = click_x - cx, click_y - cy
    dist = math.hypot(dx, dy)
    if dist > R:
        return False

    angle = (math.degrees(math.atan2(dy, dx)) + 360) % 360
    seg = int(angle // (360/SEGS))
    return seg == missing
