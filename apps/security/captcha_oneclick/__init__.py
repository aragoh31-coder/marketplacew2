
import io, base64, random, math
from PIL import Image, ImageDraw, ImageFilter

SIZE, R = 200, 80
SEGS = 12

def make_cut_circle(missing):
    img = Image.new('RGBA', (SIZE, SIZE), (30,30,50,240))
    d   = ImageDraw.Draw(img)
    cx, cy = SIZE//2, SIZE//2

    d.ellipse([cx-R,cy-R, cx+R,cy+R], fill=(40,40,60,240), outline=(255,255,255,200), width=3)

    colors = [(255,120,120), (120,220,120), (120,120,255)]
    for i in range(SEGS):
        if i==missing: continue
        jitter = random.uniform(-2,2)
        start = (i*360/SEGS) + jitter
        end   = ((i+1)*360/SEGS) - jitter
        d.pieslice([cx-R,cy-R, cx+R,cy+R], start, end, fill=random.choice(colors), outline=(255,255,255,150), width=2)

    gloss = Image.new('RGBA', (SIZE,SIZE), (255,255,255,0))
    gd   = ImageDraw.Draw(gloss)
    gd.ellipse([cx-R, cy-R-10, cx+R, cy+R-40], fill=(255,255,255,30))
    img = Image.alpha_composite(img, gloss)
    img = img.filter(ImageFilter.GaussianBlur(0.5))

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode(), missing
