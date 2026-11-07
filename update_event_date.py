"""
Update Event Start Date
Run this script to set the correct event start date to December 27, 2025
"""
from datetime import date
from app import create_app, db
from app.models.event import Event

app = create_app()

with app.app_context():
    # Get the active event
    event = Event.query.filter_by(is_active=True).first()
    
    if event:
        print(f"Current Event: {event.name}")
        print(f"Current Start Date: {event.start_date}")
        print(f"Current End Date: {event.end_date}")
        
        # Update dates - Event officially starts Dec 27, ends Dec 30
        event.start_date = date(2025, 12, 27)
        event.end_date = date(2025, 12, 30)
        event.venue = "Busiada Girls Secondary School"
        
        db.session.commit()
        
        print("\n✅ Event dates updated!")
        print(f"New Start Date: {event.start_date}")
        print(f"New End Date: {event.end_date}")
        print(f"Venue: {event.venue}")
    else:
        print("❌ No active event found!")
