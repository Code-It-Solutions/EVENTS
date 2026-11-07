"""
Script to add the Delegates Event Budget to the system
Based on handwritten budget document
"""
from app import create_app, db
from app.models.budget import Budget, BudgetItem
from app.models.user import User

def create_delegates_event_budget():
    """Create the delegates event budget with all items"""
    app = create_app()
    with app.app_context():
        # Find an admin user to be the creator
        admin = User.query.filter(User.role.in_(['admin', 'super_admin'])).first()
        if not admin:
            print("❌ No admin user found. Please create an admin first.")
            return
        
        print(f"Creating budget as user: {admin.name}")
        
        # Create the main budget
        budget = Budget(
            name="Delegates Conference Budget",
            description="Complete budget for Delegates Conference including catering, venue, and logistics",
            created_by=admin.id,
            status='draft'
        )
        db.session.add(budget)
        db.session.flush()  # Get the budget ID
        
        # Budget items extracted from the handwritten document
        budget_items = [
            # === DELEGATES BIRIANI (Main Food) - Total: 457,000 ===
            {
                'item_number': 1,
                'category': 'catering',
                'name': 'Rice',
                'description': '12 bags (4 bags × 3 days)',
                'quantity': 12,
                'unit': 'bags',
                'unit_cost': 5500,
                'budgeted_amount': 66000,
            },
            {
                'item_number': 2,
                'category': 'catering',
                'name': 'Sugar',
                'description': '64kg (16kg × 4)',
                'quantity': 64,
                'unit': 'kg',
                'unit_cost': 150,
                'budgeted_amount': 9600,
            },
            {
                'item_number': 3,
                'category': 'catering',
                'name': 'Milk',
                'description': '12 boxes × 4',
                'quantity': 48,
                'unit': 'boxes',
                'unit_cost': 625,  # Calculated: 30000/48
                'budgeted_amount': 30000,
            },
            {
                'item_number': 4,
                'category': 'catering',
                'name': 'Bread',
                'description': '1400 pieces (350 × 4)',
                'quantity': 1400,
                'unit': 'pieces',
                'unit_cost': 60,
                'budgeted_amount': 84000,
            },
            {
                'item_number': 5,
                'category': 'catering',
                'name': 'Meat',
                'description': 'Main meal meat (50000 × 3 days)',
                'quantity': 3,
                'unit': 'days',
                'unit_cost': 50000,
                'budgeted_amount': 150000,
            },
            {
                'item_number': 6,
                'category': 'catering',
                'name': 'Beans',
                'description': '50 goris × 3 days',
                'quantity': 150,
                'unit': 'goris',
                'unit_cost': 400,
                'budgeted_amount': 60000,
            },
            {
                'item_number': 7,
                'category': 'catering',
                'name': 'Cooking Oil',
                'description': '40 litres',
                'quantity': 40,
                'unit': 'litres',
                'unit_cost': 2500,
                'budgeted_amount': 100000,
            },
            {
                'item_number': 8,
                'category': 'catering',
                'name': 'Nyanya (Tomatoes)',
                'description': '3 crates',
                'quantity': 3,
                'unit': 'crates',
                'unit_cost': 4000,
                'budgeted_amount': 12000,
            },
            {
                'item_number': 9,
                'category': 'catering',
                'name': 'Vitunguu (Onions)',
                'description': '30kg',
                'quantity': 30,
                'unit': 'kg',
                'unit_cost': 150,
                'budgeted_amount': 4500,
            },
            {
                'item_number': 10,
                'category': 'catering',
                'name': 'Cabbage',
                'description': '90 pieces',
                'quantity': 90,
                'unit': 'pieces',
                'unit_cost': 100,
                'budgeted_amount': 9000,
            },
            {
                'item_number': 11,
                'category': 'catering',
                'name': 'Mayai (Eggs)',
                'description': '30 trays',
                'quantity': 30,
                'unit': 'trays',
                'unit_cost': 500,
                'budgeted_amount': 15000,
            },
            {
                'item_number': 12,
                'category': 'catering',
                'name': 'Salt',
                'description': '20kg',
                'quantity': 20,
                'unit': 'kg',
                'unit_cost': 50,
                'budgeted_amount': 1000,
            },
            {
                'item_number': 13,
                'category': 'catering',
                'name': 'Soap',
                'description': '2 bars (cleaning)',
                'quantity': 12,  # 2 bars likely per batch
                'unit': 'bars',
                'unit_cost': 150,
                'budgeted_amount': 1800,
            },
            
            # === 26-27th (Second Day Food) - Total: 10,500 ===
            {
                'item_number': 14,
                'category': 'catering',
                'name': 'Rice (Day 26-27)',
                'description': '25kg for second day',
                'quantity': 10,  # 25kg at 2700 per 10kg
                'unit': 'kg',
                'unit_cost': 2700,
                'budgeted_amount': 27000,
            },
            {
                'item_number': 15,
                'category': 'catering',
                'name': 'Sugar (Day 26-27)',
                'description': '3kg for second day',
                'quantity': 3,
                'unit': 'kg',
                'unit_cost': 200,
                'budgeted_amount': 650,
            },
            {
                'item_number': 16,
                'category': 'catering',
                'name': 'Milk (Day 26-27)',
                'description': '12 packets for second day',
                'quantity': 12,
                'unit': 'packets',
                'unit_cost': 50,
                'budgeted_amount': 600,
            },
            {
                'item_number': 17,
                'category': 'catering',
                'name': 'Bread (Day 26-27)',
                'description': '15 pieces for second day',
                'quantity': 15,
                'unit': 'pieces',
                'unit_cost': 65,
                'budgeted_amount': 1000,
            },
            {
                'item_number': 18,
                'category': 'catering',
                'name': 'Meat (Day 26-27)',
                'description': '6kg for second day',
                'quantity': 6,
                'unit': 'kg',
                'unit_cost': 600,
                'budgeted_amount': 3600,
            },
            {
                'item_number': 19,
                'category': 'catering',
                'name': 'Beans (Day 26-27)',
                'description': '5 goris for second day',
                'quantity': 5,
                'unit': 'goris',
                'unit_cost': 400,
                'budgeted_amount': 2000,
            },
            
            # === OTHER EXPENSES ===
            {
                'item_number': 20,
                'category': 'other',
                'name': 'Fumigation',
                'description': 'Venue fumigation/cleaning',
                'quantity': 1,
                'unit': 'service',
                'unit_cost': 12000,
                'budgeted_amount': 12000,
            },
            {
                'item_number': 21,
                'category': 'transport',
                'name': 'Transport',
                'description': 'Transport logistics',
                'quantity': 1,
                'unit': 'lumpsum',
                'unit_cost': 20000,
                'budgeted_amount': 20000,
            },
            {
                'item_number': 22,
                'category': 'transport',
                'name': 'Transport (Nimboye Butiole)',
                'description': 'Additional transport',
                'quantity': 1,
                'unit': 'lumpsum',
                'unit_cost': 10000,
                'budgeted_amount': 10000,
            },
            
            # === SITTING ARRANGEMENTS - Total: 137,000 ===
            {
                'item_number': 23,
                'category': 'equipment',
                'name': 'Tents',
                'description': '10-seater tents × 4 days',
                'quantity': 48,  # From calculation: 2000 × 4 × 12 = 96000
                'unit': 'tent-days',
                'unit_cost': 2000,
                'budgeted_amount': 96000,
            },
            {
                'item_number': 24,
                'category': 'equipment',
                'name': 'Chairs',
                'description': '500 chairs @ 10 × 4 days',
                'quantity': 500,
                'unit': 'chair-days',
                'unit_cost': 40,  # 10 per day × 4 days = 40
                'budgeted_amount': 20000,
            },
            {
                'item_number': 25,
                'category': 'equipment',
                'name': 'Lighting',
                'description': 'Venue lighting equipment',
                'quantity': 1,
                'unit': 'setup',
                'unit_cost': 10000,
                'budgeted_amount': 10000,
            },
            {
                'item_number': 26,
                'category': 'equipment',
                'name': 'Stage',
                'description': 'Stage setup and equipment',
                'quantity': 1,
                'unit': 'setup',
                'unit_cost': 5000,
                'budgeted_amount': 5000,
            },
            {
                'item_number': 27,
                'category': 'other',
                'name': 'Decoration',
                'description': 'Venue decoration',
                'quantity': 1,
                'unit': 'lumpsum',
                'unit_cost': 6000,
                'budgeted_amount': 6000,
            },
        ]
        
        # Add all budget items
        total = 0
        for item_data in budget_items:
            item = BudgetItem(
                budget_id=budget.id,
                **item_data
            )
            db.session.add(item)
            total += item_data['budgeted_amount']
        
        # Update budget totals
        budget.total_budgeted = total
        
        db.session.commit()
        
        print("\n" + "="*60)
        print("✅ DELEGATES CONFERENCE BUDGET CREATED SUCCESSFULLY!")
        print("="*60)
        print(f"\n📊 Budget Summary:")
        print(f"   Name: {budget.name}")
        print(f"   Total Items: {len(budget_items)}")
        print(f"   Total Budgeted: KES {total:,.2f}")
        print("\n📝 Category Breakdown:")
        
        # Calculate category totals
        categories = {}
        for item in budget_items:
            cat = item['category']
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += item['budgeted_amount']
        
        for cat, amount in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"   - {cat.title()}: KES {amount:,.2f}")
        
        print(f"\n🔗 View budget at: /budget/{budget.id}")
        print("="*60)

if __name__ == '__main__':
    create_delegates_event_budget()
