import base64
import io
import math
import random

from django.utils.crypto import get_random_string
from PIL import Image, ImageDraw

SIZE = 200
RADIUS = 80
SEGMENTS = 12


def generate_cut_circle():
    """Generate cut-circle captcha image and answer index"""
    img = Image.new("RGBA", (SIZE, SIZE), (30, 30, 40, 255))
    draw = ImageDraw.Draw(img)
    center = (SIZE // 2, SIZE // 2)

    fill_color = (60, 90, 160, 255)
    outline_color = (255, 255, 255, 200)

    missing_index = random.randint(0, SEGMENTS - 1)

    angle_per_segment = 360 / SEGMENTS
    for i in range(SEGMENTS):
        if i == missing_index:
            continue
        start_angle = i * angle_per_segment
        end_angle = (i + 1) * angle_per_segment
        draw.pieslice(
            [
                center[0] - RADIUS,
                center[1] - RADIUS,
                center[0] + RADIUS,
                center[1] + RADIUS,
            ],
            start_angle,
            end_angle,
            fill=fill_color,
            outline=outline_color,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_img = base64.b64encode(buf.getvalue()).decode()

    return b64_img, missing_index


class OneClickCaptcha:
    def __init__(self, width=300, height=200, num_circles=6, circle_radius=25):
        self.width = width
        self.height = height
        self.num_circles = num_circles
        self.circle_radius = circle_radius
        self.bg_color = (240, 240, 240)
        self.circle_color = (100, 150, 200)
        self.cut_circle_color = (200, 100, 100)
        self.cut_size = 10

    def generate(self):
        """Generate captcha image with multiple circles, one with a cut/notch"""
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        circles = []
        cut_circle_index = random.randint(0, self.num_circles - 1)

        for i in range(self.num_circles):
            attempts = 0
            while attempts < 50:
                x = random.randint(
                    self.circle_radius + 10, self.width - self.circle_radius - 10
                )
                y = random.randint(
                    self.circle_radius + 10, self.height - self.circle_radius - 10
                )

                valid = True
                for existing_x, existing_y in circles:
                    distance = math.sqrt((x - existing_x) ** 2 + (y - existing_y) ** 2)
                    if distance < (self.circle_radius * 2 + 10):
                        valid = False
                        break

                if valid:
                    circles.append((x, y))
                    break
                attempts += 1

            if len(circles) <= i:
                x = (i % 3) * (self.width // 3) + self.width // 6
                y = (i // 3) * (self.height // 2) + self.height // 4
                circles.append((x, y))

        for i, (x, y) in enumerate(circles):
            if i == cut_circle_index:
                self.draw_cut_circle(draw, x, y)
            else:
                self.draw_normal_circle(draw, x, y)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        cut_x, cut_y = circles[cut_circle_index]
        return img_b64, cut_x, cut_y

    def draw_normal_circle(self, draw, x, y):
        """Draw a normal circle"""
        draw.ellipse(
            [
                (x - self.circle_radius, y - self.circle_radius),
                (x + self.circle_radius, y + self.circle_radius),
            ],
            outline=self.circle_color,
            width=3,
        )

    def draw_cut_circle(self, draw, x, y):
        """Draw a circle with a visible cut/notch"""
        draw.ellipse(
            [
                (x - self.circle_radius, y - self.circle_radius),
                (x + self.circle_radius, y + self.circle_radius),
            ],
            outline=self.cut_circle_color,
            width=3,
        )

        cut_angle = random.uniform(0, 2 * math.pi)
        cut_x = x + int((self.circle_radius - 3) * math.cos(cut_angle))
        cut_y = y + int((self.circle_radius - 3) * math.sin(cut_angle))

        draw.rectangle(
            [
                (cut_x - self.cut_size, cut_y - self.cut_size),
                (cut_x + self.cut_size, cut_y + self.cut_size),
            ],
            fill=self.bg_color,
        )


def init_captcha_session(request):
    """Generate captcha and store cut circle coordinates in session"""
    captcha = OneClickCaptcha()
    img_b64, circle_x, circle_y = captcha.generate()
    captcha_id = get_random_string(12)
    request.session["captcha"] = {
        "id": captcha_id,
        "circle_x": circle_x,
        "circle_y": circle_y,
        "radius": captcha.circle_radius,
        "actual_width": captcha.width,
        "actual_height": captcha.height,
    }
    return img_b64


def validate_captcha(request, click_x, click_y):
    """Validate captcha by checking if click is within cut circle with coordinate transformation"""
    stored = request.session.get("captcha")
    if not stored:
        print(f"DEBUG: No captcha data in session", flush=True)
        return False

    try:
        browser_x = int(float(click_x))
        browser_y = int(float(click_y))
        circle_x = stored.get("circle_x")
        circle_y = stored.get("circle_y")
        radius = stored.get("radius", 25)

        print(f"DEBUG: Browser click at ({browser_x}, {browser_y})", flush=True)
        print(
            f"DEBUG: Stored circle at ({circle_x}, {circle_y}) with radius {radius}",
            flush=True,
        )

        actual_width = stored.get("actual_width", 300)
        actual_height = stored.get("actual_height", 200)
        print(f"DEBUG: Image dimensions {actual_width}x{actual_height}", flush=True)

        scaling_factors = [1.0, 0.6, 0.75, 1.33, 1.5, 2.0, 2.5, 3.0]

        for scale in scaling_factors:
            image_x = browser_x / scale
            image_y = browser_y / scale

            if 0 <= image_x <= actual_width and 0 <= image_y <= actual_height:
                distance = math.sqrt(
                    (image_x - circle_x) ** 2 + (image_y - circle_y) ** 2
                )
                print(
                    f"DEBUG: Scale {scale}: transformed ({image_x:.1f}, {image_y:.1f}), distance {distance:.1f}",
                    flush=True,
                )

                if distance <= radius * 3.0:
                    print(
                        f"DEBUG: MATCH! Scale {scale} with distance {distance:.1f} <= {radius * 3.0}",
                        flush=True,
                    )
                    request.session.pop("captcha", None)
                    return True

        distance = math.sqrt((browser_x - circle_x) ** 2 + (browser_y - circle_y) ** 2)
        print(
            f"DEBUG: Direct distance check: {distance:.1f} <= {radius * 3.0}",
            flush=True,
        )
        if distance <= radius * 3.0:
            print(f"DEBUG: DIRECT MATCH!", flush=True)
            request.session.pop("captcha", None)
            return True

        print(f"DEBUG: No matches found, validation failed", flush=True)
        return False
    except (ValueError, TypeError) as e:
        print(f"DEBUG: Exception in validation: {e}", flush=True)
        return False


def validate_captcha_with_transform(request, browser_x, browser_y):
    """Validate captcha with coordinate transformation from browser to image space"""
    stored = request.session.get("captcha")
    if not stored:
        return False

    try:
        circle_x = stored.get("circle_x")
        circle_y = stored.get("circle_y")
        radius = stored.get("radius", 25)

        captcha = OneClickCaptcha()

        img_b64, temp_cut_x, temp_cut_y = captcha.generate()

        scaling_factors = [1.0, 1.33, 1.5, 2.0]  # Common browser scaling

        for scale in scaling_factors:
            image_x = browser_x / scale
            image_y = browser_y / scale

            distance = math.sqrt((image_x - circle_x) ** 2 + (image_y - circle_y) ** 2)

            if distance <= radius * 1.5:  # More lenient radius
                request.session.pop("captcha", None)
                return True

        for scale in scaling_factors:
            image_x = browser_x / scale
            image_y = browser_y / scale

            if 0 <= image_x <= 300 and 0 <= image_y <= 200:
                distance = math.sqrt(
                    (image_x - circle_x) ** 2 + (image_y - circle_y) ** 2
                )
                if distance <= radius * 2:  # Very lenient
                    request.session.pop("captcha", None)
                    return True

        return False
    except (ValueError, TypeError):
        return False
