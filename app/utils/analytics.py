"""
Analytics and Forecasting Module
Provides revenue forecasting, demographic insights, and payment behavior analytics
"""

from datetime import datetime, timedelta
from sqlalchemy import func, case, extract
from app import db
from app.models.delegate import Delegate
from app.models.payment import Payment
from app.models.event import Event, PricingTier


class Analytics:
    """Analytics helper class for generating insights"""
    
    @staticmethod
    def get_revenue_forecast(event_id=None, days_ahead=30):
        """
        Predict expected revenue based on current trends
        Returns: dict with expected_revenue, expected_delegates, confidence
        """
        # Get historical registration rate (delegates per day)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=14)  # Last 2 weeks
        
        query = db.session.query(
            func.date(Delegate.registered_at).label('date'),
            func.count(Delegate.id).label('count')
        ).filter(Delegate.registered_at >= start_date)
        
        if event_id:
            query = query.filter(Delegate.event_id == event_id)
        
        daily_registrations = query.group_by(func.date(Delegate.registered_at)).all()
        
        if not daily_registrations:
            return {
                'expected_delegates': 0,
                'expected_revenue': 0,
                'current_delegates': 0,
                'current_revenue': 0,
                'daily_rate': 0,
                'payment_rate': 0,
                'confidence': 'low'
            }
        
        # Calculate average daily registration rate
        total_days = len(daily_registrations)
        total_registrations = sum(d.count for d in daily_registrations)
        daily_rate = total_registrations / max(total_days, 1)
        
        # Get current totals
        current_query = Delegate.query
        if event_id:
            current_query = current_query.filter_by(event_id=event_id)
        
        current_delegates = current_query.count()
        paid_delegates = current_query.filter_by(is_paid=True).count()
        payment_rate = paid_delegates / max(current_delegates, 1)
        
        # Get average ticket price
        if event_id:
            event = Event.query.get(event_id)
            current_tier = event.get_current_price() if event else None
            avg_price = current_tier.price if current_tier else 3000
        else:
            avg_price = 3000  # Default price
        
        # Calculate current revenue
        current_revenue = Payment.query.filter_by(status='completed')
        if event_id:
            # Join with delegates to filter by event
            current_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.status == 'completed'
            ).scalar() or 0
        else:
            current_revenue = Payment.get_total_collected()
        
        # Forecast
        expected_new_delegates = int(daily_rate * days_ahead)
        expected_total_delegates = current_delegates + expected_new_delegates
        expected_paying = int(expected_total_delegates * payment_rate)
        expected_revenue = expected_paying * avg_price
        
        # Confidence based on data quality
        if total_days >= 10 and current_delegates >= 50:
            confidence = 'high'
        elif total_days >= 5 and current_delegates >= 20:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'expected_delegates': expected_total_delegates,
            'expected_new_delegates': expected_new_delegates,
            'expected_revenue': expected_revenue,
            'current_delegates': current_delegates,
            'current_revenue': current_revenue,
            'daily_rate': round(daily_rate, 1),
            'payment_rate': round(payment_rate * 100, 1),
            'avg_price': avg_price,
            'confidence': confidence,
            'forecast_days': days_ahead
        }
    
    @staticmethod
    def get_regional_performance(event_id=None):
        """
        Analyze performance by archdeaconry/region
        Returns regions with their stats and performance indicators
        """
        query = db.session.query(
            Delegate.archdeaconry,
            func.count(Delegate.id).label('total'),
            func.sum(case((Delegate.is_paid == True, 1), else_=0)).label('paid'),
            func.sum(case((Delegate.checked_in == True, 1), else_=0)).label('checked_in')
        )
        
        if event_id:
            query = query.filter(Delegate.event_id == event_id)
        
        results = query.group_by(Delegate.archdeaconry).all()
        
        if not results:
            return []
        
        # Calculate averages for comparison
        total_all = sum(r.total for r in results)
        avg_per_region = total_all / len(results) if results else 0
        
        regions = []
        for r in results:
            payment_rate = (r.paid / r.total * 100) if r.total > 0 else 0
            
            # Determine performance status
            if r.total < avg_per_region * 0.5:
                status = 'underperforming'
                status_class = 'danger'
            elif r.total < avg_per_region * 0.8:
                status = 'below_average'
                status_class = 'warning'
            elif r.total > avg_per_region * 1.2:
                status = 'exceeding'
                status_class = 'success'
            else:
                status = 'on_track'
                status_class = 'primary'
            
            regions.append({
                'name': r.archdeaconry,
                'total': r.total,
                'paid': r.paid,
                'unpaid': r.total - r.paid,
                'checked_in': r.checked_in,
                'payment_rate': round(payment_rate, 1),
                'status': status,
                'status_class': status_class,
                'vs_average': round((r.total / avg_per_region - 1) * 100, 1) if avg_per_region > 0 else 0
            })
        
        # Sort by total descending
        regions.sort(key=lambda x: x['total'], reverse=True)
        return regions
    
    @staticmethod
    def get_demographic_insights(event_id=None):
        """
        Get demographic breakdown: gender, age brackets, category distribution
        """
        base_query = Delegate.query
        if event_id:
            base_query = base_query.filter_by(event_id=event_id)
        
        # Gender distribution
        gender_stats = db.session.query(
            Delegate.gender,
            func.count(Delegate.id).label('count')
        )
        if event_id:
            gender_stats = gender_stats.filter(Delegate.event_id == event_id)
        gender_stats = gender_stats.group_by(Delegate.gender).all()
        
        # Age bracket distribution
        age_stats = db.session.query(
            Delegate.age_bracket,
            func.count(Delegate.id).label('count')
        )
        if event_id:
            age_stats = age_stats.filter(Delegate.event_id == event_id)
        age_stats = age_stats.group_by(Delegate.age_bracket).all()
        
        # Map age bracket codes to display labels
        age_bracket_labels = {
            '15_below': '15 and Below',
            '15_19': '15-19',
            '20_24': '20-24',
            '25_29': '25-29',
            '30_above': '30 and Above'
        }
        
        # Category distribution
        category_stats = db.session.query(
            Delegate.category,
            func.count(Delegate.id).label('count')
        )
        if event_id:
            category_stats = category_stats.filter(Delegate.event_id == event_id)
        category_stats = category_stats.group_by(Delegate.category).all()
        
        # Parish distribution (top 10)
        parish_stats = db.session.query(
            Delegate.parish,
            Delegate.archdeaconry,
            func.count(Delegate.id).label('count')
        )
        if event_id:
            parish_stats = parish_stats.filter(Delegate.event_id == event_id)
        parish_stats = parish_stats.group_by(
            Delegate.parish, Delegate.archdeaconry
        ).order_by(func.count(Delegate.id).desc()).limit(10).all()
        
        total = base_query.count()
        
        return {
            'total': total,
            'gender': [{'label': g.gender or 'Unknown', 'count': g.count, 
                       'percent': round(g.count / total * 100, 1) if total > 0 else 0} 
                      for g in gender_stats],
            'age_brackets': [{'label': age_bracket_labels.get(a.age_bracket, a.age_bracket or 'Unknown'), 
                             'code': a.age_bracket or 'unknown',
                             'count': a.count,
                             'percent': round(a.count / total * 100, 1) if total > 0 else 0}
                            for a in age_stats],
            'categories': [{'label': c.category or 'Delegate', 'count': c.count,
                           'percent': round(c.count / total * 100, 1) if total > 0 else 0}
                          for c in category_stats],
            'top_parishes': [{'parish': p.parish, 'archdeaconry': p.archdeaconry, 
                             'count': p.count} for p in parish_stats]
        }
    
    @staticmethod
    def get_payment_behavior(event_id=None, days=30):
        """
        Analyze payment patterns: peak hours, time to payment, etc.
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Payment by hour of day
        hourly_query = db.session.query(
            extract('hour', Payment.completed_at).label('hour'),
            func.count(Payment.id).label('count')
        ).filter(
            Payment.status == 'completed',
            Payment.completed_at >= start_date,
            Payment.completed_at != None
        ).group_by(extract('hour', Payment.completed_at)).all()
        
        # Payment by day of week
        daily_query = db.session.query(
            extract('dow', Payment.completed_at).label('day'),
            func.count(Payment.id).label('count')
        ).filter(
            Payment.status == 'completed',
            Payment.completed_at >= start_date,
            Payment.completed_at != None
        ).group_by(extract('dow', Payment.completed_at)).all()
        
        # Average time from registration to payment
        # This is a simplified version - ideally would join delegate and payment
        
        # Payment status breakdown
        status_query = db.session.query(
            Payment.status,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('total')
        ).filter(Payment.created_at >= start_date).group_by(Payment.status).all()
        
        # Find peak hour
        peak_hour = max(hourly_query, key=lambda x: x.count) if hourly_query else None
        
        # Day names
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        peak_day = max(daily_query, key=lambda x: x.count) if daily_query else None
        
        return {
            'hourly_distribution': [{'hour': int(h.hour), 'count': h.count} for h in hourly_query],
            'daily_distribution': [{'day': int(d.day), 'day_name': day_names[int(d.day)], 
                                   'count': d.count} for d in daily_query],
            'peak_hour': int(peak_hour.hour) if peak_hour else None,
            'peak_hour_formatted': f"{int(peak_hour.hour):02d}:00" if peak_hour else 'N/A',
            'peak_day': day_names[int(peak_day.day)] if peak_day else 'N/A',
            'status_breakdown': [{'status': s.status, 'count': s.count, 
                                 'total': float(s.total or 0)} for s in status_query]
        }
    
    @staticmethod
    def get_registration_trend(event_id=None, days=30):
        """Get registration trend over time"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.session.query(
            func.date(Delegate.registered_at).label('date'),
            func.count(Delegate.id).label('total'),
            func.sum(case((Delegate.is_paid == True, 1), else_=0)).label('paid')
        ).filter(Delegate.registered_at >= start_date)
        
        if event_id:
            query = query.filter(Delegate.event_id == event_id)
        
        results = query.group_by(func.date(Delegate.registered_at)).order_by(
            func.date(Delegate.registered_at)
        ).all()
        
        # Fill in missing dates
        date_dict = {r.date: {'total': r.total, 'paid': r.paid} for r in results}
        all_dates = []
        current = start_date.date()
        end = datetime.utcnow().date()
        
        cumulative_total = 0
        cumulative_paid = 0
        
        while current <= end:
            data = date_dict.get(current, {'total': 0, 'paid': 0})
            cumulative_total += data['total']
            cumulative_paid += data['paid']
            
            all_dates.append({
                'date': current.isoformat(),
                'daily_total': data['total'],
                'daily_paid': data['paid'],
                'cumulative_total': cumulative_total,
                'cumulative_paid': cumulative_paid
            })
            current += timedelta(days=1)
        
        return all_dates
