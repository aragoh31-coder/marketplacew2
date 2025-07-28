import io, base64, random, math
from PIL import Image, ImageDraw, ImageFilter

SIZE, R, SEGS = 200, 80, 12


def make_cut_circle():
    """
    Generates a base64‐encoded PNG with simple circles, one having a missing gap.
    Returns: (img_b64, circle_data_dict)
    """
    img = Image.new('RGBA', (SIZE, SIZE), (245, 245, 245, 255))
    draw = ImageDraw.Draw(img)
    
    num_circles = random.randint(6, 8)
    missing = random.randrange(num_circles)
    
    colors = [
        (255, 100, 100),  # Red
        (100, 255, 100),  # Green  
        (100, 100, 255),  # Blue
        (255, 200, 100),  # Orange
        (200, 100, 255),  # Purple
        (100, 255, 200),  # Cyan
    ]
    
    circle_data = []
    for i in range(num_circles):
        margin = 30
        x = random.randint(margin, SIZE - margin)
        y = random.randint(margin, SIZE - margin)
        radius = random.randint(15, 25)
        color = random.choice(colors)
        
        circle_data.append((x, y, radius, i == missing))
        
        if i == missing:
            gap_start = random.randint(0, 270)
            gap_size = random.randint(60, 90)
            
            draw.arc(
                [x-radius, y-radius, x+radius, y+radius],
                start=gap_start + gap_size,
                end=gap_start + 360,
                fill=color,
                width=4
            )
        else:
            draw.ellipse(
                [x-radius, y-radius, x+radius, y+radius],
                outline=color,
                width=4
            )
    
    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    
    return b64, {'circles': circle_data, 'missing_index': missing}


def validate_click(click_x: int, click_y: int, circle_data: dict) -> bool:
    """
    Validates that the user clicked inside the circle with the missing gap.
    """
    circles = circle_data.get('circles', [])
    missing_index = circle_data.get('missing_index', -1)
    
    for i, (x, y, radius, has_gap) in enumerate(circles):
        dx, dy = click_x - x, click_y - y
        dist = math.hypot(dx, dy)
        
        if dist <= radius + 5:  # Small tolerance
            return i == missing_index and has_gap
    
    return False
