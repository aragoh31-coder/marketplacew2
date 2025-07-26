import random
import hashlib
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from django.core.cache import cache
from django.utils.crypto import get_random_string
from django.utils import timezone

class VisualCaptcha:
    """Visual CAPTCHA system with missing slice detection"""
    
    def __init__(self, width=300, height=150):
        self.width = width
        self.height = height
        self.slice_width = 50
        self.slice_height = 50
        
    def generate_captcha(self):
        """Generate visual CAPTCHA with missing slice"""
        image = Image.new('RGB', (self.width, self.height), color='#2a2a2a')
        draw = ImageDraw.Draw(image)
        
        pattern_type = random.choice(['circles', 'rectangles', 'lines'])
        colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57', '#ff9ff3']
        
        if pattern_type == 'circles':
            for _ in range(15):
                x = random.randint(0, self.width)
                y = random.randint(0, self.height)
                radius = random.randint(10, 30)
                color = random.choice(colors)
                draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=color)
                
        elif pattern_type == 'rectangles':
            for _ in range(12):
                x1 = random.randint(0, self.width-40)
                y1 = random.randint(0, self.height-40)
                x2 = x1 + random.randint(20, 40)
                y2 = y1 + random.randint(20, 40)
                color = random.choice(colors)
                draw.rectangle([x1, y1, x2, y2], fill=color)
                
        elif pattern_type == 'lines':
            for _ in range(20):
                x1 = random.randint(0, self.width)
                y1 = random.randint(0, self.height)
                x2 = random.randint(0, self.width)
                y2 = random.randint(0, self.height)
                color = random.choice(colors)
                draw.line([x1, y1, x2, y2], fill=color, width=3)
        
        max_x = self.width - self.slice_width
        max_y = self.height - self.slice_height
        slice_x = random.randint(0, max_x)
        slice_y = random.randint(0, max_y)
        
        slice_image = image.crop((slice_x, slice_y, slice_x + self.slice_width, slice_y + self.slice_height))
        
        draw.rectangle([slice_x, slice_y, slice_x + self.slice_width, slice_y + self.slice_height], fill='#000000')
        
        draw.rectangle([slice_x-1, slice_y-1, slice_x + self.slice_width+1, slice_y + self.slice_height+1], outline='#ffffff', width=2)
        
        return image, slice_image, (slice_x, slice_y)
    
    def create_captcha_challenge(self):
        """Create complete CAPTCHA challenge"""
        main_image, slice_image, correct_position = self.generate_captcha()
        
        decoy_slices = []
        for _ in range(3):
            decoy_x = random.randint(0, self.width - self.slice_width)
            decoy_y = random.randint(0, self.height - self.slice_height)
            
            decoy = Image.new('RGB', (self.slice_width, self.slice_height), color='#1a1a1a')
            decoy_draw = ImageDraw.Draw(decoy)
            
            for _ in range(5):
                x = random.randint(0, self.slice_width)
                y = random.randint(0, self.slice_height)
                radius = random.randint(3, 8)
                color = random.choice(['#ff6b6b', '#4ecdc4', '#45b7d1'])
                decoy_draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=color)
            
            decoy_slices.append(decoy)
        
        all_slices = [slice_image] + decoy_slices
        random.shuffle(all_slices)
        correct_slice_index = all_slices.index(slice_image)
        
        return {
            'main_image': main_image,
            'slices': all_slices,
            'correct_slice_index': correct_slice_index,
            'correct_position': correct_position
        }
    
    def image_to_base64(self, image):
        """Convert PIL image to base64 string"""
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode()
    
    def generate_captcha_session(self):
        """Generate CAPTCHA and store in session"""
        challenge = self.create_captcha_challenge()
        
        session_id = get_random_string(32)
        session_data = {
            'correct_slice_index': challenge['correct_slice_index'],
            'correct_position': challenge['correct_position'],
            'created_at': timezone.now().isoformat()
        }
        
        cache.set(f'visual_captcha:{session_id}', session_data, 600)
        
        main_image_b64 = self.image_to_base64(challenge['main_image'])
        slice_images_b64 = [self.image_to_base64(slice_img) for slice_img in challenge['slices']]
        
        return {
            'session_id': session_id,
            'main_image': main_image_b64,
            'slice_images': slice_images_b64
        }
    
    def validate_captcha(self, session_id, selected_slice_index, drop_x, drop_y):
        """Validate CAPTCHA solution"""
        session_data = cache.get(f'visual_captcha:{session_id}')
        if not session_data:
            return False, "CAPTCHA expired"
        
        if selected_slice_index != session_data['correct_slice_index']:
            return False, "Wrong slice selected"
        
        correct_x, correct_y = session_data['correct_position']
        tolerance = 25  # pixels
        
        if (abs(drop_x - correct_x) <= tolerance and 
            abs(drop_y - correct_y) <= tolerance):
            cache.delete(f'visual_captcha:{session_id}')
            return True, "CAPTCHA solved correctly"
        
        return False, "Slice dropped in wrong position"

class CaptchaSessionManager:
    """Manage CAPTCHA sessions with proper encoding"""
    
    @staticmethod
    def store_captcha_data(request, captcha_data):
        """Store CAPTCHA data in session with proper encoding"""
        from django.utils import timezone
        session_data = {
            'session_id': str(captcha_data['session_id']),
            'main_image': str(captcha_data['main_image']),
            'slice_images': [str(img) for img in captcha_data['slice_images']],
            'timestamp': timezone.now().timestamp()
        }
        
        request.session['visual_captcha_data'] = session_data
        request.session.modified = True
        return session_data
    
    @staticmethod
    def get_captcha_data(request):
        """Retrieve CAPTCHA data from session"""
        return request.session.get('visual_captcha_data')
    
    @staticmethod
    def clear_captcha_data(request):
        """Clear CAPTCHA data from session"""
        if 'visual_captcha_data' in request.session:
            del request.session['visual_captcha_data']
            request.session.modified = True
    
    @staticmethod
    def is_captcha_expired(captcha_data, ttl_minutes=15):
        """Check if CAPTCHA data has expired"""
        if not captcha_data or 'timestamp' not in captcha_data:
            return True
        
        import time
        current_time = time.time()
        captcha_time = captcha_data['timestamp']
        
        return (current_time - captcha_time) > (ttl_minutes * 60)
