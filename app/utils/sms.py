import requests
from datetime import datetime, timedelta
from app import db
from app.models.operations import Announcement


class SMSService:
    """SMS Service for sending messages via Africa's Talking API"""
    
    def __init__(self, api_key=None, username=None, sender_id=None):
        self.api_key = api_key or 'YOUR_AFRICASTALKING_API_KEY'
        self.username = username or 'sandbox'
        self.sender_id = sender_id or 'KAYO'
        self.base_url = 'https://api.africastalking.com/version1/messaging'
    
    def send_sms(self, phone_numbers, message):
        """
        Send SMS to one or multiple phone numbers
        
        Args:
            phone_numbers: List of phone numbers or single phone number
            message: Message content
        
        Returns:
            dict with status and details
        """
        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]
        
        # Format phone numbers to international format
        formatted_numbers = [self._format_phone(p) for p in phone_numbers]
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'apiKey': self.api_key
        }
        
        data = {
            'username': self.username,
            'to': ','.join(formatted_numbers),
            'message': message,
            'from': self.sender_id
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, data=data)
            result = response.json()
            
            return {
                'success': response.status_code == 201,
                'data': result,
                'recipients': len(formatted_numbers)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'recipients': 0
            }
    
    def _format_phone(self, phone):
        """Format phone number to international format (+254...)"""
        phone = str(phone).strip().replace(' ', '').replace('-', '')
        
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif phone.startswith('254'):
            phone = '+' + phone
        elif not phone.startswith('+'):
            phone = '+254' + phone
        
        return phone
    
    def send_bulk_sms(self, delegates, message_template, event=None):
        """
        Send personalized SMS to multiple delegates
        
        Args:
            delegates: List of Delegate objects
            message_template: Message with placeholders like {name}, {ticket_number}
            event: Optional Event object for event placeholders
        
        Returns:
            dict with success count and failures
        """
        results = {
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        for delegate in delegates:
            # Personalize message
            message = self._personalize_message(message_template, delegate, event)
            
            result = self.send_sms(delegate.phone, message)
            
            if result['success']:
                results['sent'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'delegate': delegate.name,
                    'error': result.get('error', 'Unknown error')
                })
        
        return results
    
    def _personalize_message(self, template, delegate, event=None):
        """Personalize message with delegate and event data"""
        replacements = {
            '{name}': delegate.name,
            '{first_name}': delegate.name.split()[0] if delegate.name else '',
            '{ticket_number}': delegate.ticket_number or 'N/A',
            '{delegate_number}': delegate.delegate_number or 'N/A',
            '{phone}': delegate.phone,
            '{payment_status}': delegate.payment_status,
            '{category}': delegate.delegate_category or 'Delegate',
            '{parish}': delegate.parish or '',
            '{archdeaconry}': delegate.archdeaconry or '',
        }
        
        if event:
            replacements.update({
                '{event_name}': event.name,
                '{event_date}': event.start_date.strftime('%B %d, %Y') if event.start_date else '',
                '{event_venue}': event.venue or '',
            })
        
        message = template
        for key, value in replacements.items():
            message = message.replace(key, str(value))
        
        return message


class WhatsAppService:
    """WhatsApp Service for sending messages via WhatsApp Business API"""
    
    def __init__(self, api_key=None, phone_number_id=None):
        # Meta WhatsApp Business API credentials
        self.api_key = api_key or 'YOUR_WHATSAPP_API_KEY'
        self.phone_number_id = phone_number_id or 'YOUR_PHONE_NUMBER_ID'
        self.base_url = f'https://graph.facebook.com/v18.0/{self.phone_number_id}/messages'
        
        # Alternative: Africa's Talking WhatsApp
        self.at_base_url = 'https://api.africastalking.com/version1/whatsapp/send'
    
    def send_whatsapp(self, phone_number, message, template_name=None, template_params=None):
        """
        Send WhatsApp message
        
        Args:
            phone_number: Recipient phone number
            message: Message content (for text messages)
            template_name: Optional template name for template messages
            template_params: Optional template parameters
        
        Returns:
            dict with status and details
        """
        formatted_phone = self._format_phone(phone_number)
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        if template_name:
            # Send template message
            data = {
                'messaging_product': 'whatsapp',
                'to': formatted_phone,
                'type': 'template',
                'template': {
                    'name': template_name,
                    'language': {'code': 'en'},
                    'components': []
                }
            }
            
            if template_params:
                data['template']['components'].append({
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': p} for p in template_params]
                })
        else:
            # Send text message
            data = {
                'messaging_product': 'whatsapp',
                'to': formatted_phone,
                'type': 'text',
                'text': {'body': message}
            }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data)
            result = response.json()
            
            return {
                'success': response.status_code in [200, 201],
                'data': result,
                'message_id': result.get('messages', [{}])[0].get('id')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_phone(self, phone):
        """Format phone number for WhatsApp (without + prefix)"""
        phone = str(phone).strip().replace(' ', '').replace('-', '').replace('+', '')
        
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif not phone.startswith('254'):
            phone = '254' + phone
        
        return phone
    
    def send_bulk_whatsapp(self, delegates, message_template, event=None):
        """Send personalized WhatsApp messages to multiple delegates"""
        sms_service = SMSService()
        results = {
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        for delegate in delegates:
            message = sms_service._personalize_message(message_template, delegate, event)
            result = self.send_whatsapp(delegate.phone, message)
            
            if result['success']:
                results['sent'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'delegate': delegate.name,
                    'error': result.get('error', 'Unknown error')
                })
        
        return results


class AnnouncementService:
    """Service for managing announcements"""
    
    @staticmethod
    def create_announcement(title, content, channels, target_group='all', 
                          event_id=None, created_by=None, scheduled_for=None,
                          message_type='general'):
        """
        Create a new announcement
        """
        announcement = Announcement(
            title=title,
            content=content,
            channels=channels,
            target_group=target_group,
            event_id=event_id,
            created_by=created_by,
            scheduled_for=scheduled_for,
            status='scheduled' if scheduled_for else 'draft'
        )
        
        db.session.add(announcement)
        db.session.commit()
        
        return announcement
    
    @staticmethod
    def send_announcement(announcement_id, sms_service=None, whatsapp_service=None):
        """Send an announcement to target recipients"""
        from app.models.delegate import Delegate
        
        announcement = Announcement.query.get(announcement_id)
        if not announcement:
            return {'success': False, 'error': 'Announcement not found'}
        
        query = Delegate.query
        
        if announcement.event_id:
            query = query.filter_by(event_id=announcement.event_id)
        
        if announcement.target_group == 'paid':
            query = query.filter_by(payment_status='paid')
        elif announcement.target_group == 'unpaid':
            query = query.filter(Delegate.payment_status.in_(['pending', 'partial']))
        elif announcement.target_group == 'checked_in':
            query = query.filter_by(checked_in=True)
        elif announcement.target_group == 'not_checked_in':
            query = query.filter_by(checked_in=False)
        
        delegates = query.all()
        
        results = {
            'total_recipients': len(delegates),
            'sms_sent': 0,
            'whatsapp_sent': 0,
            'email_sent': 0,
            'in_app_sent': 0,
            'errors': []
        }
        
        if 'sms' in announcement.channels:
            if not sms_service:
                sms_service = SMSService()
            sms_results = sms_service.send_bulk_sms(delegates, announcement.content)
            results['sms_sent'] = sms_results['sent']
            results['errors'].extend(sms_results['errors'])
        
        if 'whatsapp' in announcement.channels:
            if not whatsapp_service:
                whatsapp_service = WhatsAppService()
            wa_results = whatsapp_service.send_bulk_whatsapp(delegates, announcement.content)
            results['whatsapp_sent'] = wa_results['sent']
            results['errors'].extend(wa_results['errors'])
        
        if 'in_app' in announcement.channels:
            results['in_app_sent'] = len(delegates)
        
        announcement.status = 'sent'
        announcement.sent_at = datetime.utcnow()
        announcement.recipients_count = len(delegates)
        db.session.commit()
        
        return results
    
    @staticmethod
    def get_pending_announcements():
        """Get all scheduled announcements that are due"""
        return Announcement.query.filter(
            Announcement.status == 'scheduled',
            Announcement.scheduled_for <= datetime.utcnow()
        ).all()


class AutomatedReminderService:
    """Service for automated payment reminders"""
    
    REMINDER_TEMPLATES = {
        'first_reminder': {
            'title': 'Payment Reminder',
            'sms': "Hello {name}, this is a friendly reminder that your registration payment for {event_name} is still pending. Please complete your payment to confirm your attendance. Thank you!",
            'whatsapp': "👋 Hello {name}!\n\nThis is a friendly reminder that your registration payment for *{event_name}* is still pending.\n\n💳 Please complete your payment to confirm your attendance.\n\nThank you! 🙏"
        },
        'second_reminder': {
            'title': 'Urgent: Payment Due',
            'sms': "Dear {name}, your payment for {event_name} is overdue. Please make your payment soon to secure your spot. Contact us if you need assistance.",
            'whatsapp': "⚠️ Dear {name},\n\nYour payment for *{event_name}* is overdue.\n\nPlease make your payment soon to secure your spot. Contact us if you need assistance.\n\n📞 We're here to help!"
        },
        'final_reminder': {
            'title': 'Final Notice: Payment Required',
            'sms': "FINAL NOTICE: {name}, your {event_name} registration will be cancelled if payment is not received within 24 hours. Please act now!",
            'whatsapp': "🚨 *FINAL NOTICE*\n\nDear {name},\n\nYour registration for *{event_name}* will be cancelled if payment is not received within 24 hours.\n\n⏰ Please act now to secure your spot!"
        }
    }
    
    @staticmethod
    def get_reminder_templates():
        """Get available reminder templates"""
        return [
            {'id': key, 'title': value['title'], 'sms': value['sms'], 'whatsapp': value['whatsapp']}
            for key, value in AutomatedReminderService.REMINDER_TEMPLATES.items()
        ]
    
    @staticmethod
    def get_unpaid_delegates(event_id=None, days_registered=None):
        """Get delegates with pending payments"""
        from app.models.delegate import Delegate
        
        query = Delegate.query.filter(Delegate.payment_status.in_(['pending', 'partial']))
        
        if event_id:
            query = query.filter_by(event_id=event_id)
        
        if days_registered:
            cutoff_date = datetime.utcnow() - timedelta(days=days_registered)
            query = query.filter(Delegate.created_at <= cutoff_date)
        
        return query.all()
    
    @staticmethod
    def send_payment_reminders(event_id=None, reminder_type='first_reminder', 
                               channels=None, custom_message=None):
        """Send automated payment reminders"""
        from app.models.event import Event
        from app.models.operations import PaymentReminder
        
        if channels is None:
            channels = ['sms']
        
        delegates = AutomatedReminderService.get_unpaid_delegates(event_id)
        
        if not delegates:
            return {'success': True, 'sent': 0, 'message': 'No unpaid delegates found'}
        
        event = Event.query.get(event_id) if event_id else None
        template = AutomatedReminderService.REMINDER_TEMPLATES.get(
            reminder_type, AutomatedReminderService.REMINDER_TEMPLATES['first_reminder']
        )
        
        sms_service = SMSService()
        whatsapp_service = WhatsAppService()
        
        results = {'total': len(delegates), 'sms_sent': 0, 'whatsapp_sent': 0, 'skipped': 0, 'errors': []}
        
        for delegate in delegates:
            recent_reminder = PaymentReminder.query.filter(
                PaymentReminder.delegate_id == delegate.id,
                PaymentReminder.sent_at >= datetime.utcnow() - timedelta(hours=24)
            ).first()
            
            if recent_reminder:
                results['skipped'] += 1
                continue
            
            if 'sms' in channels:
                message = custom_message or template['sms']
                personalized = sms_service._personalize_message(message, delegate, event)
                sms_result = sms_service.send_sms(delegate.phone, personalized)
                
                if sms_result['success']:
                    results['sms_sent'] += 1
                    reminder = PaymentReminder(delegate_id=delegate.id, message=personalized, channel='sms', status='sent')
                    db.session.add(reminder)
                else:
                    results['errors'].append({'delegate': delegate.name, 'channel': 'sms', 'error': sms_result.get('error')})
            
            if 'whatsapp' in channels:
                message = custom_message or template['whatsapp']
                personalized = sms_service._personalize_message(message, delegate, event)
                wa_result = whatsapp_service.send_whatsapp(delegate.phone, personalized)
                
                if wa_result['success']:
                    results['whatsapp_sent'] += 1
                    reminder = PaymentReminder(delegate_id=delegate.id, message=personalized, channel='whatsapp', status='sent')
                    db.session.add(reminder)
                else:
                    results['errors'].append({'delegate': delegate.name, 'channel': 'whatsapp', 'error': wa_result.get('error')})
        
        db.session.commit()
        return results


class ThankYouService:
    """Service for post-event thank-you messages"""
    
    THANK_YOU_TEMPLATES = {
        'general': {
            'title': 'Thank You for Attending!',
            'sms': "Thank you {name} for attending {event_name}! We hope you had a wonderful experience. God bless you!",
            'whatsapp': "🎉 *Thank You, {name}!*\n\nThank you for attending *{event_name}*!\n\nWe hope you had a wonderful and blessed experience. Looking forward to seeing you again!\n\n🙏 God bless you!"
        },
        'with_certificate': {
            'title': 'Thank You - Certificate Available',
            'sms': "Thank you {name} for attending {event_name}! Your certificate of participation is ready. Visit our website to download it.",
            'whatsapp': "🎉 *Thank You, {name}!*\n\nThank you for attending *{event_name}*!\n\n📜 Your *Certificate of Participation* is now ready!\n\nVisit our website to download it.\n\n🙏 God bless you!"
        },
        'feedback_request': {
            'title': 'Thank You - Share Your Feedback',
            'sms': "Thank you {name} for attending {event_name}! We'd love your feedback. Please take a moment to share your thoughts with us.",
            'whatsapp': "🎉 *Thank You, {name}!*\n\nThank you for attending *{event_name}*!\n\n📝 We'd love to hear your feedback!\n\nPlease take a moment to share your thoughts and help us improve.\n\n🙏 God bless you!"
        },
        'next_event': {
            'title': 'Thank You - See You Next Time!',
            'sms': "Thank you {name} for attending {event_name}! Mark your calendar for our next event. We can't wait to see you again!",
            'whatsapp': "🎉 *Thank You, {name}!*\n\nThank you for attending *{event_name}*!\n\n📅 Mark your calendar for our next event!\n\nWe can't wait to see you again!\n\n🙏 God bless you!"
        }
    }
    
    @staticmethod
    def get_thank_you_templates():
        """Get available thank-you message templates"""
        return [
            {'id': key, 'title': value['title'], 'sms': value['sms'], 'whatsapp': value['whatsapp']}
            for key, value in ThankYouService.THANK_YOU_TEMPLATES.items()
        ]
    
    @staticmethod
    def send_thank_you_messages(event_id, template_type='general', channels=None,
                                 target_group='checked_in', custom_message=None):
        """Send post-event thank-you messages"""
        from app.models.delegate import Delegate
        from app.models.event import Event
        
        if channels is None:
            channels = ['sms']
        
        event = Event.query.get(event_id)
        if not event:
            return {'success': False, 'error': 'Event not found'}
        
        query = Delegate.query.filter_by(event_id=event_id)
        
        if target_group == 'checked_in':
            query = query.filter_by(checked_in=True)
        elif target_group == 'paid':
            query = query.filter_by(payment_status='paid')
        
        delegates = query.all()
        
        if not delegates:
            return {'success': True, 'sent': 0, 'message': 'No delegates found'}
        
        template = ThankYouService.THANK_YOU_TEMPLATES.get(
            template_type, ThankYouService.THANK_YOU_TEMPLATES['general']
        )
        
        sms_service = SMSService()
        whatsapp_service = WhatsAppService()
        
        results = {'total': len(delegates), 'sms_sent': 0, 'whatsapp_sent': 0, 'errors': []}
        
        for delegate in delegates:
            if 'sms' in channels:
                message = custom_message or template['sms']
                personalized = sms_service._personalize_message(message, delegate, event)
                sms_result = sms_service.send_sms(delegate.phone, personalized)
                
                if sms_result['success']:
                    results['sms_sent'] += 1
                else:
                    results['errors'].append({'delegate': delegate.name, 'channel': 'sms', 'error': sms_result.get('error')})
            
            if 'whatsapp' in channels:
                message = custom_message or template['whatsapp']
                personalized = sms_service._personalize_message(message, delegate, event)
                wa_result = whatsapp_service.send_whatsapp(delegate.phone, personalized)
                
                if wa_result['success']:
                    results['whatsapp_sent'] += 1
                else:
                    results['errors'].append({'delegate': delegate.name, 'channel': 'whatsapp', 'error': wa_result.get('error')})
        
        return results
