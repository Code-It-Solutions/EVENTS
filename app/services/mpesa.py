import requests
import base64
from datetime import datetime
from flask import current_app


class MpesaAPI:
    """M-Pesa Daraja API Integration"""
    
    SANDBOX_URL = "https://sandbox.safaricom.co.ke"
    PRODUCTION_URL = "https://api.safaricom.co.ke"
    
    def __init__(self):
        self.consumer_key = current_app.config['MPESA_CONSUMER_KEY']
        self.consumer_secret = current_app.config['MPESA_CONSUMER_SECRET']
        self.shortcode = current_app.config['MPESA_SHORTCODE']
        self.passkey = current_app.config['MPESA_PASSKEY']
        self.callback_url = current_app.config['MPESA_CALLBACK_URL']
        self.env = current_app.config.get('MPESA_ENV', 'sandbox')
        
        self.base_url = self.PRODUCTION_URL if self.env == 'production' else self.SANDBOX_URL
    
    def get_access_token(self):
        """Get OAuth access token from M-Pesa API"""
        # Check if credentials are configured
        if not self.consumer_key or not self.consumer_secret:
            current_app.logger.error("M-Pesa credentials not configured! Set MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET")
            return None
        
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        
        # Create basic auth header
        credentials = f"{self.consumer_key}:{self.consumer_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 400:
                current_app.logger.error(f"M-Pesa auth failed: Invalid Consumer Key or Secret. Status: {response.status_code}")
                current_app.logger.error(f"Consumer Key starts with: {self.consumer_key[:8] if self.consumer_key else 'NOT SET'}...")
                return None
            elif response.status_code == 401:
                current_app.logger.error("M-Pesa auth failed: Unauthorized - credentials may be expired or revoked")
                return None
            
            response.raise_for_status()
            return response.json().get('access_token')
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"M-Pesa auth error: {str(e)}")
            return None
    
    def generate_password(self):
        """Generate password for STK Push"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_string = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        return password, timestamp
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """
        Initiate STK Push to customer's phone
        
        Args:
            phone_number: Customer phone (format: 254XXXXXXXXX)
            amount: Amount to charge
            account_reference: Your reference for the transaction
            transaction_desc: Description of the transaction
        
        Returns:
            dict with response from M-Pesa or error
        """
        access_token = self.get_access_token()
        if not access_token:
            current_app.logger.error("M-Pesa: Failed to get access token - check Consumer Key/Secret")
            return {"error": "Failed to get access token. Check M-Pesa credentials."}
        
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        
        password, timestamp = self.generate_password()
        
        # Format phone number (remove leading 0 or + and ensure 254 prefix)
        phone = str(phone_number).strip().replace(' ', '').replace('-', '')
        if phone.startswith('+'):
            phone = phone[1:]
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        if not phone.startswith('254'):
            phone = '254' + phone
        
        # Validate phone number length (should be 12 digits: 254XXXXXXXXX)
        if len(phone) != 12 or not phone.isdigit():
            current_app.logger.error(f"M-Pesa: Invalid phone number format: {phone}")
            return {"error": f"Invalid phone number format: {phone}. Expected format: 254XXXXXXXXX"}
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference[:12],  # Max 12 chars
            "TransactionDesc": transaction_desc[:13]  # Max 13 chars
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        current_app.logger.info(f"M-Pesa STK Push: Phone={phone}, Amount={amount}, Ref={account_reference}")
        current_app.logger.debug(f"M-Pesa Request URL: {url}")
        current_app.logger.debug(f"M-Pesa Callback URL: {self.callback_url}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response_data = response.json()
            
            current_app.logger.info(f"M-Pesa Response: {response.status_code} - {response_data}")
            
            # Check for M-Pesa error response
            if response.status_code != 200:
                error_msg = response_data.get('errorMessage', response_data.get('ResultDesc', 'Unknown error'))
                current_app.logger.error(f"M-Pesa API Error: {error_msg}")
                return {"error": error_msg}
            
            # Check ResponseCode in successful response
            response_code = response_data.get('ResponseCode')
            if response_code and response_code != '0':
                error_msg = response_data.get('ResponseDescription', 'Transaction failed')
                current_app.logger.error(f"M-Pesa Response Error: {error_msg}")
                return {"error": error_msg}
            
            return response_data
            
        except requests.exceptions.Timeout:
            current_app.logger.error("M-Pesa STK push timeout")
            return {"error": "Request timeout. Please try again."}
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"M-Pesa STK push error: {str(e)}")
            return {"error": f"Connection error: {str(e)}"}
    
    def query_stk_status(self, checkout_request_id):
        """Query the status of an STK Push transaction"""
        access_token = self.get_access_token()
        if not access_token:
            return {"error": "Failed to get access token"}
        
        url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
        
        password, timestamp = self.generate_password()
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"M-Pesa query error: {str(e)}")
            return {"error": str(e)}
