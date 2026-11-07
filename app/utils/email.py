"""Email utility functions for OTP and notifications"""
from flask import current_app, render_template_string

# Import mail only if available
try:
    from app import mail
except ImportError:
    mail = None


def send_otp_email(user, otp_code):
    """Send OTP verification email to user"""
    # Check if mail is configured
    if mail is None or not current_app.config.get('MAIL_USERNAME'):
        current_app.logger.warning(f"Email not configured. OTP for {user.email}: {otp_code}")
        return False, "Email service not configured"
    
    try:
        from flask_mail import Message
        subject = "KAYO Login Verification Code"
        
        html_body = render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #1a5f2a, #0d4a1c); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { background: #f9f9f9; padding: 30px; border: 1px solid #ddd; }
        .otp-box { background: #1a5f2a; color: white; font-size: 32px; font-weight: bold; letter-spacing: 8px; padding: 20px 40px; text-align: center; border-radius: 8px; margin: 20px 0; }
        .footer { background: #333; color: #999; padding: 20px; text-align: center; font-size: 12px; border-radius: 0 0 10px 10px; }
        .warning { color: #856404; background: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 KAYO Login Verification</h1>
        </div>
        <div class="content">
            <p>Hello <strong>{{ user.name }}</strong>,</p>
            <p>You are attempting to log in to your KAYO account. Please use the following One-Time Password (OTP) to complete your login:</p>
            
            <div class="otp-box">{{ otp_code }}</div>
            
            <p><strong>This code will expire in 10 minutes.</strong></p>
            
            <div class="warning">
                ⚠️ <strong>Security Notice:</strong> If you did not attempt to log in, please ignore this email and ensure your password is secure.
            </div>
        </div>
        <div class="footer">
            <p>KAYO - Diocese of Nambale</p>
            <p>This is an automated message. Please do not reply.</p>
        </div>
    </div>
</body>
</html>
        ''', user=user, otp_code=otp_code)
        
        text_body = f'''
Hello {user.name},

Your KAYO Login Verification Code is: {otp_code}

This code will expire in 10 minutes.

If you did not attempt to log in, please ignore this email.

KAYO - Diocese of Nambale
        '''
        
        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=text_body,
            html=html_body
        )
        
        mail.send(msg)
        return True, "OTP sent successfully"
        
    except Exception as e:
        current_app.logger.error(f"Failed to send OTP email to {user.email}: {str(e)}")
        return False, str(e)


def send_email(to, subject, body, html_body=None):
    """Generic email sending function"""
    if mail is None or not current_app.config.get('MAIL_USERNAME'):
        current_app.logger.warning("Email service not configured")
        return False, "Email service not configured"
    
    try:
        from flask_mail import Message
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            body=body,
            html=html_body
        )
        mail.send(msg)
        return True, "Email sent successfully"
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False, str(e)
