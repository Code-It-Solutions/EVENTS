import io
import base64

# Optional PIL import
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None
    ImageDraw = None
    ImageFont = None

# Optional qrcode import
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


class BadgeDesigner:
    """Badge Designer for creating custom delegate badges"""
    
    # Default badge dimensions (in pixels, assuming 300 DPI)
    DEFAULT_WIDTH = 1050  # 3.5 inches
    DEFAULT_HEIGHT = 600  # 2 inches
    
    # Default colors
    DEFAULT_COLORS = {
        'background': '#FFFFFF',
        'primary': '#0d6efd',
        'secondary': '#6c757d',
        'text': '#212529',
        'accent': '#198754'
    }
    
    # Default fonts (fallback to default if not available)
    DEFAULT_FONTS = {
        'title': 'arial.ttf',
        'name': 'arialbd.ttf',
        'details': 'arial.ttf'
    }
    
    def __init__(self, width=None, height=None, colors=None):
        self.width = width or self.DEFAULT_WIDTH
        self.height = height or self.DEFAULT_HEIGHT
        self.colors = {**self.DEFAULT_COLORS, **(colors or {})}
    
    def create_badge(self, delegate, event=None, template='standard', include_qr=True):
        """
        Create a badge image for a delegate
        
        Args:
            delegate: Delegate object with name, category, etc.
            event: Optional Event object for event branding
            template: Badge template type ('standard', 'vip', 'minimal')
            include_qr: Whether to include QR code
        
        Returns:
            PIL Image object
        """
        # Create base image
        img = Image.new('RGB', (self.width, self.height), self.colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Get colors from event branding if available
        primary_color = event.primary_color if event and event.primary_color else self.colors['primary']
        secondary_color = event.secondary_color if event and event.secondary_color else self.colors['secondary']
        
        # Draw based on template
        if template == 'vip':
            self._draw_vip_template(draw, img, delegate, event, primary_color, secondary_color, include_qr)
        elif template == 'minimal':
            self._draw_minimal_template(draw, img, delegate, event, primary_color, secondary_color, include_qr)
        else:
            self._draw_standard_template(draw, img, delegate, event, primary_color, secondary_color, include_qr)
        
        return img
    
    def _get_font(self, font_type, size):
        """Get font, falling back to default if not available"""
        try:
            return ImageFont.truetype(self.DEFAULT_FONTS.get(font_type, 'arial.ttf'), size)
        except:
            return ImageFont.load_default()
    
    def _draw_standard_template(self, draw, img, delegate, event, primary_color, secondary_color, include_qr):
        """Draw standard badge template"""
        # Header bar
        draw.rectangle([(0, 0), (self.width, 100)], fill=primary_color)
        
        # Event name
        event_name = event.name if event else "KAYO Conference"
        title_font = self._get_font('title', 36)
        draw.text((30, 20), event_name, fill='white', font=title_font)
        
        # Diocese subtitle
        subtitle_font = self._get_font('details', 18)
        draw.text((30, 65), "ACK Diocese of Nambale", fill=(255, 255, 255, 204), font=subtitle_font)
        
        # Delegate name (large)
        name_font = self._get_font('name', 60)
        name_y = 140
        draw.text((30, name_y), delegate.name.upper(), fill=self.colors['text'], font=name_font)
        
        # Category badge
        category_y = 230
        category_font = self._get_font('details', 28)
        category_text = delegate.delegate_category or "DELEGATE"
        
        # Category background
        bbox = draw.textbbox((0, 0), category_text, font=category_font)
        cat_width = bbox[2] - bbox[0] + 30
        cat_height = bbox[3] - bbox[1] + 15
        
        # Color based on category
        cat_color = self._get_category_color(delegate.delegate_category)
        draw.rounded_rectangle(
            [(30, category_y), (30 + cat_width, category_y + cat_height)],
            radius=5,
            fill=cat_color
        )
        draw.text((45, category_y + 7), category_text, fill='white', font=category_font)
        
        # Details (parish, archdeaconry)
        details_font = self._get_font('details', 24)
        details_y = 300
        
        if delegate.parish:
            draw.text((30, details_y), f"Parish: {delegate.parish}", fill=secondary_color, font=details_font)
            details_y += 35
        
        if delegate.archdeaconry:
            draw.text((30, details_y), f"Archdeaconry: {delegate.archdeaconry}", fill=secondary_color, font=details_font)
        
        # Delegate number
        if delegate.delegate_number:
            num_font = self._get_font('title', 32)
            draw.text((30, self.height - 80), f"#{delegate.delegate_number}", fill=primary_color, font=num_font)
        
        # QR Code
        if include_qr:
            qr_size = 150
            qr_x = self.width - qr_size - 30
            qr_y = 130
            qr_img = self._generate_qr(delegate)
            qr_img = qr_img.resize((qr_size, qr_size))
            img.paste(qr_img, (qr_x, qr_y))
        
        # Footer line
        draw.rectangle([(0, self.height - 10), (self.width, self.height)], fill=primary_color)
    
    def _draw_vip_template(self, draw, img, delegate, event, primary_color, secondary_color, include_qr):
        """Draw VIP badge template with gold accents"""
        gold_color = '#FFD700'
        
        # Full header
        draw.rectangle([(0, 0), (self.width, 120)], fill='#1a1a2e')
        
        # Gold accent lines
        draw.rectangle([(0, 118), (self.width, 125)], fill=gold_color)
        
        # VIP label
        vip_font = self._get_font('title', 28)
        draw.text((self.width - 100, 20), "VIP", fill=gold_color, font=vip_font)
        
        # Event name
        event_name = event.name if event else "KAYO Conference"
        title_font = self._get_font('title', 36)
        draw.text((30, 40), event_name, fill='white', font=title_font)
        
        # Name with gold underline
        name_font = self._get_font('name', 56)
        name_y = 160
        draw.text((30, name_y), delegate.name.upper(), fill='#1a1a2e', font=name_font)
        
        bbox = draw.textbbox((30, name_y), delegate.name.upper(), font=name_font)
        draw.rectangle([(30, bbox[3] + 5), (bbox[2], bbox[3] + 10)], fill=gold_color)
        
        # Category
        category_y = 260
        category_font = self._get_font('details', 26)
        category_text = delegate.delegate_category or "VIP DELEGATE"
        draw.text((30, category_y), category_text, fill=secondary_color, font=category_font)
        
        # Details
        details_font = self._get_font('details', 22)
        if delegate.parish:
            draw.text((30, 310), delegate.parish, fill=secondary_color, font=details_font)
        
        # QR Code with gold border
        if include_qr:
            qr_size = 140
            qr_x = self.width - qr_size - 40
            qr_y = 150
            
            # Gold border
            draw.rectangle(
                [(qr_x - 5, qr_y - 5), (qr_x + qr_size + 5, qr_y + qr_size + 5)],
                fill=gold_color
            )
            
            qr_img = self._generate_qr(delegate)
            qr_img = qr_img.resize((qr_size, qr_size))
            img.paste(qr_img, (qr_x, qr_y))
        
        # Footer
        draw.rectangle([(0, self.height - 15), (self.width, self.height)], fill='#1a1a2e')
        draw.rectangle([(0, self.height - 20), (self.width, self.height - 15)], fill=gold_color)
    
    def _draw_minimal_template(self, draw, img, delegate, event, primary_color, secondary_color, include_qr):
        """Draw minimal/clean badge template"""
        # Simple top accent
        draw.rectangle([(0, 0), (self.width, 8)], fill=primary_color)
        
        # Large name centered
        name_font = self._get_font('name', 52)
        bbox = draw.textbbox((0, 0), delegate.name.upper(), font=name_font)
        name_width = bbox[2] - bbox[0]
        name_x = (self.width - name_width) // 2
        draw.text((name_x, 100), delegate.name.upper(), fill=self.colors['text'], font=name_font)
        
        # Category centered below
        category_font = self._get_font('details', 28)
        category_text = delegate.delegate_category or "DELEGATE"
        bbox = draw.textbbox((0, 0), category_text, font=category_font)
        cat_width = bbox[2] - bbox[0]
        cat_x = (self.width - cat_width) // 2
        draw.text((cat_x, 180), category_text, fill=primary_color, font=category_font)
        
        # Event name at bottom
        if event:
            event_font = self._get_font('details', 22)
            bbox = draw.textbbox((0, 0), event.name, font=event_font)
            event_width = bbox[2] - bbox[0]
            event_x = (self.width - event_width) // 2
            draw.text((event_x, self.height - 100), event.name, fill=secondary_color, font=event_font)
        
        # Small QR in corner
        if include_qr:
            qr_size = 100
            qr_img = self._generate_qr(delegate)
            qr_img = qr_img.resize((qr_size, qr_size))
            img.paste(qr_img, (self.width - qr_size - 20, self.height - qr_size - 20))
        
        # Bottom accent
        draw.rectangle([(0, self.height - 8), (self.width, self.height)], fill=primary_color)
    
    def _generate_qr(self, delegate):
        """Generate QR code for delegate"""
        if not HAS_QRCODE or not HAS_PIL:
            # Return a placeholder image if qrcode not available
            if HAS_PIL:
                placeholder = Image.new('RGB', (100, 100), '#CCCCCC')
                draw = ImageDraw.Draw(placeholder)
                draw.text((20, 40), "QR", fill='#666666')
                return placeholder
            return None
        
        # Use ticket_number directly (it already has the format KAYO-2025-XXXX)
        # Or fall back to delegate ID if no ticket number
        qr_data = delegate.ticket_number or f"DELEGATE-{delegate.id}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        return qr.make_image(fill_color="black", back_color="white")
    
    def _get_category_color(self, category):
        """Get color based on delegate category"""
        colors = {
            'Youth': '#0d6efd',
            'Clergy': '#6f42c1',
            'Choir': '#198754',
            'Leader': '#dc3545',
            'Guest': '#ffc107',
            'VIP': '#FFD700'
        }
        return colors.get(category, '#6c757d')
    
    def badge_to_base64(self, img, format='PNG'):
        """Convert badge image to base64 string"""
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode()
    
    def badge_to_bytes(self, img, format='PNG'):
        """Convert badge image to bytes"""
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def get_available_templates():
        """Get list of available badge templates"""
        return [
            {
                'id': 'standard',
                'name': 'Standard',
                'description': 'Classic badge with header bar and QR code'
            },
            {
                'id': 'vip',
                'name': 'VIP',
                'description': 'Premium badge with gold accents'
            },
            {
                'id': 'minimal',
                'name': 'Minimal',
                'description': 'Clean, centered design'
            }
        ]
