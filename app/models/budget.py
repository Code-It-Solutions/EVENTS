"""
Budget Management Models
Upload budgets and track implementation with AI parsing
"""
from datetime import datetime
from app import db
import json


class Budget(db.Model):
    """Main Budget - uploaded by admin"""
    __tablename__ = 'budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    # Budget totals
    total_budgeted = db.Column(db.Float, default=0)
    total_spent = db.Column(db.Float, default=0)
    
    # File upload info
    original_filename = db.Column(db.String(255))
    file_type = db.Column(db.String(50))  # csv, xlsx, pdf
    raw_content = db.Column(db.Text)  # Store raw extracted text for reference
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, active, closed
    
    # Audit fields
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    items = db.relationship('BudgetItem', backref='budget', lazy='dynamic', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_budgets')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_budgets')
    event = db.relationship('Event', backref='budgets')
    
    def __repr__(self):
        return f'<Budget {self.name}>'
    
    def update_totals(self):
        """Recalculate budget totals"""
        self.total_budgeted = sum(item.budgeted_amount for item in self.items)
        self.total_spent = sum(item.actual_spent for item in self.items)
    
    @property
    def balance_remaining(self):
        return self.total_budgeted - self.total_spent
    
    @property
    def utilization_percentage(self):
        if self.total_budgeted == 0:
            return 0
        return (self.total_spent / self.total_budgeted) * 100
    
    @property
    def items_count(self):
        return self.items.count()
    
    @property
    def completed_items_count(self):
        return self.items.filter(BudgetItem.status == 'completed').count()


class BudgetItem(db.Model):
    """Individual budget line items"""
    __tablename__ = 'budget_items'
    
    # Categories for budget items
    CATEGORIES = [
        ('venue', 'Venue & Facilities'),
        ('transport', 'Transport & Logistics'),
        ('catering', 'Catering & Meals'),
        ('accommodation', 'Accommodation'),
        ('materials', 'Materials & Supplies'),
        ('equipment', 'Equipment & Rentals'),
        ('personnel', 'Personnel & Honoraria'),
        ('publicity', 'Publicity & Marketing'),
        ('administration', 'Administration'),
        ('contingency', 'Contingency'),
        ('other', 'Other')
    ]
    
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budgets.id'), nullable=False)
    
    # Item details
    item_number = db.Column(db.Integer)  # Sequential number within budget
    category = db.Column(db.String(50), default='other')
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Financial details
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(50))  # pieces, days, persons, etc.
    unit_cost = db.Column(db.Float, default=0)
    budgeted_amount = db.Column(db.Float, nullable=False, default=0)
    actual_spent = db.Column(db.Float, default=0)
    
    # Implementation tracking
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, cancelled
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    due_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Assignment
    assigned_to = db.Column(db.String(255))  # Name/role responsible
    vendor = db.Column(db.String(255))  # Vendor/supplier if applicable
    
    # Notes and tracking
    notes = db.Column(db.Text)
    implementation_notes = db.Column(db.Text)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    expenditures = db.relationship('BudgetExpenditure', backref='budget_item', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<BudgetItem {self.name}>'
    
    @property
    def variance(self):
        return self.budgeted_amount - self.actual_spent
    
    @property
    def variance_percentage(self):
        if self.budgeted_amount == 0:
            return 0
        return (self.variance / self.budgeted_amount) * 100
    
    @property
    def utilization_percentage(self):
        if self.budgeted_amount == 0:
            return 0
        return (self.actual_spent / self.budgeted_amount) * 100
    
    def update_actual_spent(self):
        """Recalculate actual spent from expenditures"""
        self.actual_spent = sum(exp.amount for exp in self.expenditures if exp.status == 'approved')
        # Also update parent budget totals
        if self.budget:
            self.budget.update_totals()


class BudgetExpenditure(db.Model):
    """Track actual expenditures against budget items"""
    __tablename__ = 'budget_expenditures'
    
    id = db.Column(db.Integer, primary_key=True)
    budget_item_id = db.Column(db.Integer, db.ForeignKey('budget_items.id'), nullable=False)
    
    # Expenditure details
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    
    # Payment details
    payment_method = db.Column(db.String(50))  # cash, mpesa, bank_transfer, cheque
    reference_number = db.Column(db.String(100))  # Receipt/transaction number
    vendor = db.Column(db.String(255))
    
    # Approval
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text)
    
    # Receipt/documentation
    receipt_file = db.Column(db.String(255))  # Path to uploaded receipt
    
    # Audit
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    recorder = db.relationship('User', foreign_keys=[recorded_by], backref='recorded_expenditures')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_expenditures')
    
    def __repr__(self):
        return f'<BudgetExpenditure {self.description} - {self.amount}>'


# Budget parsing utilities
class BudgetParser:
    """AI-powered budget parser"""
    
    # Common budget item keywords for categorization
    CATEGORY_KEYWORDS = {
        'venue': ['venue', 'hall', 'grounds', 'space', 'facility', 'room', 'tent', 'chairs', 'tables', 'decoration'],
        'transport': ['transport', 'fuel', 'vehicle', 'bus', 'travel', 'logistics', 'driver', 'car hire'],
        'catering': ['food', 'catering', 'meals', 'lunch', 'breakfast', 'dinner', 'tea', 'water', 'refreshments', 'snacks'],
        'accommodation': ['accommodation', 'hotel', 'lodging', 'room', 'boarding', 'guest house'],
        'materials': ['materials', 'supplies', 'stationery', 'printing', 'badges', 'certificates', 'banners', 'posters', 't-shirts'],
        'equipment': ['equipment', 'sound', 'PA', 'projector', 'screen', 'generator', 'lighting', 'rental'],
        'personnel': ['honoraria', 'allowance', 'speaker', 'facilitator', 'volunteer', 'staff', 'security', 'personnel'],
        'publicity': ['publicity', 'marketing', 'advertising', 'social media', 'promotion', 'media'],
        'administration': ['administration', 'admin', 'communication', 'airtime', 'internet', 'coordination'],
        'contingency': ['contingency', 'miscellaneous', 'emergency', 'unforeseen']
    }
    
    @classmethod
    def categorize_item(cls, item_name, item_description=''):
        """Auto-categorize a budget item based on keywords"""
        text = f"{item_name} {item_description}".lower()
        
        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return category
        return 'other'
    
    @classmethod
    def parse_csv(cls, content):
        """Parse CSV content into budget items"""
        import csv
        import io
        
        items = []
        reader = csv.reader(io.StringIO(content))
        headers = None
        
        for row_num, row in enumerate(reader):
            if row_num == 0:
                # Try to identify headers
                headers = [h.lower().strip() for h in row]
                continue
            
            if not any(row):  # Skip empty rows
                continue
            
            item = cls._parse_row(row, headers, row_num)
            if item:
                items.append(item)
        
        return items
    
    @classmethod
    def parse_excel(cls, file_content):
        """Parse Excel file content into budget items"""
        try:
            import openpyxl
            import io
            
            wb = openpyxl.load_workbook(io.BytesIO(file_content))
            ws = wb.active
            
            items = []
            headers = None
            
            for row_num, row in enumerate(ws.iter_rows(values_only=True), 1):
                if row_num == 1:
                    headers = [str(h).lower().strip() if h else '' for h in row]
                    continue
                
                if not any(row):  # Skip empty rows
                    continue
                
                item = cls._parse_row(list(row), headers, row_num)
                if item:
                    items.append(item)
            
            return items
        except ImportError:
            raise ValueError("Excel parsing requires openpyxl library")
    
    @classmethod
    def _parse_row(cls, row, headers, row_num):
        """Parse a single row into a budget item dict"""
        if not headers or len(row) < 2:
            return None
        
        item = {
            'item_number': row_num,
            'name': '',
            'description': '',
            'quantity': 1,
            'unit': '',
            'unit_cost': 0,
            'budgeted_amount': 0,
            'category': 'other'
        }
        
        # Map columns based on headers
        for i, header in enumerate(headers):
            if i >= len(row):
                break
            
            value = row[i]
            if value is None:
                continue
            
            # Item name/description
            if any(h in header for h in ['item', 'name', 'description', 'particular', 'activity']):
                if not item['name']:
                    item['name'] = str(value).strip()
                else:
                    item['description'] = str(value).strip()
            
            # Quantity
            elif any(h in header for h in ['qty', 'quantity', 'no', 'number', 'count']):
                try:
                    item['quantity'] = float(value)
                except:
                    pass
            
            # Unit
            elif any(h in header for h in ['unit', 'uom']):
                item['unit'] = str(value).strip()
            
            # Unit cost / rate
            elif any(h in header for h in ['rate', 'unit cost', 'unit price', 'price', 'cost per']):
                try:
                    item['unit_cost'] = float(str(value).replace(',', '').replace('KSh', '').replace('Ksh', '').strip())
                except:
                    pass
            
            # Total / Amount
            elif any(h in header for h in ['total', 'amount', 'budget', 'cost', 'value']):
                try:
                    item['budgeted_amount'] = float(str(value).replace(',', '').replace('KSh', '').replace('Ksh', '').strip())
                except:
                    pass
            
            # Category
            elif any(h in header for h in ['category', 'type', 'class']):
                item['category'] = str(value).lower().strip()
        
        # Calculate amount if not provided but we have quantity and unit_cost
        if item['budgeted_amount'] == 0 and item['quantity'] > 0 and item['unit_cost'] > 0:
            item['budgeted_amount'] = item['quantity'] * item['unit_cost']
        
        # Auto-categorize if category is still 'other' or unknown
        if item['category'] == 'other' or item['category'] not in [c[0] for c in BudgetItem.CATEGORIES]:
            item['category'] = cls.categorize_item(item['name'], item['description'])
        
        # Skip if no name or amount
        if not item['name'] or item['budgeted_amount'] <= 0:
            return None
        
        return item
    
    @classmethod
    def parse_text(cls, text):
        """Parse plain text or extracted PDF text into budget items"""
        import re
        
        items = []
        lines = text.strip().split('\n')
        
        item_num = 1
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to extract amount from line (look for numbers that could be currency)
            amounts = re.findall(r'[\d,]+(?:\.\d{2})?', line)
            
            if amounts:
                # Take the last/largest number as the amount
                try:
                    amount = max([float(a.replace(',', '')) for a in amounts])
                except:
                    continue
                
                if amount < 100:  # Likely not a budget amount
                    continue
                
                # Remove the amount from line to get description
                for a in amounts:
                    line = line.replace(a, '')
                
                # Clean up the description
                name = re.sub(r'[^\w\s-]', '', line).strip()
                name = ' '.join(name.split())  # Remove extra spaces
                
                if name and len(name) > 3:
                    item = {
                        'item_number': item_num,
                        'name': name[:255],
                        'description': '',
                        'quantity': 1,
                        'unit': '',
                        'unit_cost': amount,
                        'budgeted_amount': amount,
                        'category': cls.categorize_item(name)
                    }
                    items.append(item)
                    item_num += 1
        
        return items
