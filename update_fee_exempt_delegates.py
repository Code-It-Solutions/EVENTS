"""
Script to update existing worship team and arise band delegates to be marked as paid (fee-exempt)
"""
from app import create_app, db
from app.models.delegate import Delegate
from datetime import datetime

def update_fee_exempt_delegates():
    app = create_app()
    with app.app_context():
        print("Updating fee-exempt delegates (Worship Team and Arise Band)...")
        
        # Find all unpaid worship team and arise band delegates
        fee_exempt_delegates = Delegate.query.filter(
            Delegate.is_paid == False,
            Delegate.category.in_(['nav', 'arise_band'])
        ).all()
        
        print(f"Found {len(fee_exempt_delegates)} unpaid fee-exempt delegates")
        
        if not fee_exempt_delegates:
            print("No fee-exempt delegates to update.")
            return
        
        # Update each delegate
        for delegate in fee_exempt_delegates:
            delegate.is_paid = True
            delegate.amount_paid = 0
            delegate.payment_confirmed_at = datetime.utcnow()
            # Keep registered_by as payment_confirmed_by
            delegate.payment_confirmed_by = delegate.registered_by
            
            # Ensure they have a ticket number
            if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                from app.models.event import Event
                event = Event.query.get(delegate.event_id) if delegate.event_id else None
                delegate.ticket_number = Delegate.generate_ticket_number(event)
            
            print(f"  ✓ Updated: {delegate.name} ({delegate.category}) - Ticket: {delegate.ticket_number}")
        
        # Commit all changes
        db.session.commit()
        print(f"\n✅ Successfully updated {len(fee_exempt_delegates)} fee-exempt delegates!")
        
        # Summary by category
        nav_count = len([d for d in fee_exempt_delegates if d.category == 'nav'])
        arise_count = len([d for d in fee_exempt_delegates if d.category == 'arise_band'])
        print(f"   - Worship Team (NAV): {nav_count}")
        print(f"   - Arise Band: {arise_count}")

if __name__ == '__main__':
    update_fee_exempt_delegates()
