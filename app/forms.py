from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional, InputRequired
from app.models.user import User
from app.church_data import get_archdeaconries, get_parishes, CHURCH_DATA


class EmptyForm(FlaskForm):
    """Empty form for CSRF protection only (e.g., delete/cancel buttons)"""
    pass


def get_role_choices(include_admin=False, include_all=False):
    """Get role choices from database"""
    from app.models.audit import Role
    
    if include_all:
        # For admin form - show all roles
        roles = Role.query.order_by(Role.name).all()
        choices = [(role.name, role.name.replace('_', ' ').title()) for role in roles]
    elif include_admin:
        # Include admin roles
        roles = Role.query.filter(Role.name.in_(['chair', 'admin', 'data_clerk', 'registration_officer'])).all()
        choices = [(role.name, role.name.replace('_', ' ').title()) for role in roles]
    else:
        # For self-registration - only basic roles
        choices = [
            ('chair', 'Chair'),
        ]
    return choices


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class OTPVerificationForm(FlaskForm):
    """Form for OTP verification during login"""
    otp = StringField('Verification Code', validators=[
        DataRequired(message='Please enter the verification code'),
        Length(min=6, max=6, message='Verification code must be 6 digits')
    ], render_kw={"placeholder": "Enter 6-digit code", "maxlength": "6", "autocomplete": "one-time-code"})
    submit = SubmitField('Verify')


class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[Optional(), Length(min=10, max=15)])
    role = SelectField('Role', choices=[
        ('chair', 'Chair'),
    ], validators=[DataRequired()])
    local_church = StringField('Local Church', validators=[DataRequired(), Length(max=100)])
    archdeaconry = SelectField('Archdeaconry', validators=[DataRequired()])
    parish = SelectField('Parish', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')
    
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.archdeaconry.choices = get_archdeaconries()
        self.parish.choices = get_parishes()
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')
    
    def validate_phone(self, phone):
        if phone.data:
            user = User.query.filter_by(phone=phone.data).first()
            if user:
                raise ValidationError('Phone number already registered.')


class DelegateForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    local_church = StringField('Local Church', validators=[DataRequired(), Length(max=100)])
    archdeaconry = SelectField('Archdeaconry', validators=[DataRequired()])
    parish = SelectField('Parish', validators=[DataRequired()])
    phone_number = StringField('Phone Number (Optional)', validators=[Optional(), Length(max=15)])
    id_number = StringField('ID Number (Optional)', validators=[Optional(), Length(max=20)])
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female')
    ], validators=[DataRequired()])
    age_bracket = SelectField('Age Bracket', choices=[
        ('', '-- Select Age Bracket --'),
        ('15_below', '15 and Below'),
        ('15_19', '15-19'),
        ('20_24', '20-24'),
        ('25_29', '25-29'),
        ('30_above', '30 and Above')
    ], validators=[InputRequired(message='Age bracket is required')])
    category = SelectField('Category', choices=[
        ('delegate', 'Delegate'),
        ('counsellor', 'Counsellor'),
        ('archdeaconry_chair', 'Archdeaconry Chair'),
        ('nav', 'NAV (Worship Team)'),
        ('intercessor', 'Intercessor'),
        ('clergy', 'Clergy'),
        ('arise_band', 'Arise Band_Ke'),
        ('speaker', 'Speaker'),
        ('vip', 'VIP')
    ], validators=[DataRequired()])
    submit = SubmitField('Register Delegate')
    
    def __init__(self, *args, **kwargs):
        super(DelegateForm, self).__init__(*args, **kwargs)
        self.archdeaconry.choices = get_archdeaconries()
        self.parish.choices = get_parishes()


class PaymentForm(FlaskForm):
    payment_method = SelectField('Payment Method', choices=[
        ('mpesa', 'M-Pesa STK Push'),
        ('cash', 'Cash'),
        ('mpesa_paybill', 'M-Pesa Paybill (Manual)'),
        ('bank_transfer', 'Bank Transfer')
    ], default='mpesa')
    phone_number = StringField('M-Pesa Phone Number', validators=[
        Optional(), 
        Length(min=10, max=15)
    ])
    receipt_number = StringField('Receipt/Reference Number', validators=[
        Optional(),
        Length(max=50)
    ])
    submit = SubmitField('Process Payment')


class CashPaymentForm(FlaskForm):
    """Form for recording cash payments for delegates"""
    delegate_ids = StringField('Delegate IDs', validators=[DataRequired()])
    amount = StringField('Total Amount (KSh)', validators=[DataRequired()])
    receipt_number = StringField('Receipt Number', validators=[Optional(), Length(max=50)])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Confirm Cash Payment')


class AdminUserForm(FlaskForm):
    """Form for admin to create/edit users"""
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[Optional(), Length(min=10, max=15)])
    role = SelectField('Role', validators=[DataRequired()])
    local_church = StringField('Local Church', validators=[Optional(), Length(max=100)])
    archdeaconry = SelectField('Archdeaconry', validators=[Optional()])
    parish = SelectField('Parish', validators=[Optional()])
    password = PasswordField('Password (leave blank to keep current)', validators=[Optional(), Length(min=6)])
    submit = SubmitField('Save User')
    
    def __init__(self, *args, **kwargs):
        super(AdminUserForm, self).__init__(*args, **kwargs)
        self.archdeaconry.choices = get_archdeaconries()
        self.parish.choices = get_parishes()
        # Load roles from database
        self.role.choices = get_role_choices(include_all=True)


class BulkRegistrationForm(FlaskForm):
    """Form for bulk delegate registration via CSV upload"""
    csv_file = FileField('CSV File', validators=[
        DataRequired(),
        FileAllowed(['csv'], 'CSV files only!')
    ])
    submit = SubmitField('Upload & Register')


class SearchForm(FlaskForm):
    """Smart search form"""
    query = StringField('Search', validators=[Optional()], 
                       render_kw={"placeholder": "Search by name, phone, ID, ticket..."})
    archdeaconry = SelectField('Archdeaconry', validators=[Optional()])
    parish = SelectField('Parish', validators=[Optional()])
    gender = SelectField('Gender', choices=[
        ('', 'All Genders'),
        ('male', 'Male'),
        ('female', 'Female')
    ], validators=[Optional()])
    payment_status = SelectField('Payment Status', choices=[
        ('', 'All'),
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid')
    ], validators=[Optional()])
    category = SelectField('Category', choices=[
        ('', 'All Categories'),
        ('delegate', 'Delegate'),
        ('counsellor', 'Counsellor'),
        ('archdeaconry_chair', 'Archdeaconry Chair'),
        ('nav', 'NAV (Worship Team)'),
        ('intercessor', 'Intercessor'),
        ('clergy', 'Clergy'),
        ('arise_band', 'Arise Band_Ke'),
        ('speaker', 'Speaker'),
        ('vip', 'VIP')
    ], validators=[Optional()])
    submit = SubmitField('Search')
    
    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        self.archdeaconry.choices = [('', 'All Archdeaconries')] + get_archdeaconries()[1:]
        self.parish.choices = [('', 'All Parishes')] + get_parishes()[1:]


class CheckInForm(FlaskForm):
    """Form for scanning QR codes / ticket lookup"""
    ticket_number = StringField('Ticket Number', validators=[DataRequired()],
                               render_kw={"placeholder": "Scan or enter ticket number"})
    submit = SubmitField('Check In')


# ============== FUND MANAGEMENT FORMS ==============

class PledgeForm(FlaskForm):
    """Form for recording pledges from delegates, well-wishers, or fundraising"""
    source_type = SelectField('Source Type', choices=[
        ('delegate', 'Delegate'),
        ('well_wisher', 'Well Wisher'),
        ('fundraising', 'Fundraising')
    ], validators=[DataRequired()])
    source_name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    source_phone = StringField('Phone Number', validators=[Optional(), Length(max=15)])
    source_email = StringField('Email', validators=[Optional(), Email()])
    delegate_id = SelectField('Link to Delegate (Optional)', coerce=int, validators=[Optional()])
    amount_pledged = StringField('Amount Pledged (KSh)', validators=[DataRequired()])
    due_date = StringField('Due Date (Optional)', validators=[Optional()])
    local_church = StringField('Local Church', validators=[Optional(), Length(max=100)])
    archdeaconry = SelectField('Archdeaconry', validators=[Optional()], validate_choice=False)
    parish = SelectField('Parish', validators=[Optional()], validate_choice=False)
    description = TextAreaField('Description/Purpose', validators=[Optional()])
    submit = SubmitField('Record Pledge')
    
    def __init__(self, *args, **kwargs):
        super(PledgeForm, self).__init__(*args, **kwargs)
        self.archdeaconry.choices = [('', 'Select Archdeaconry')] + get_archdeaconries()[1:]
        self.parish.choices = [('', 'Select Parish')] + get_parishes()[1:]
        self.delegate_id.choices = [(0, 'Not linked to delegate')]


class PledgePaymentForm(FlaskForm):
    """Form for recording payments against a pledge"""
    amount = StringField('Amount (KSh)', validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=[
        ('mpesa', 'M-Pesa'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque')
    ], validators=[DataRequired()])
    reference = StringField('Transaction Reference', validators=[Optional(), Length(max=100)])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Record Payment')


class ScheduledPaymentForm(FlaskForm):
    """Form for creating scheduled/recurring payments"""
    source_type = SelectField('Source Type', choices=[
        ('delegate', 'Delegate'),
        ('well_wisher', 'Well Wisher'),
        ('fundraising', 'Fundraising')
    ], validators=[DataRequired()])
    source_name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    source_phone = StringField('Phone Number', validators=[Optional(), Length(max=15)])
    source_email = StringField('Email', validators=[Optional(), Email()])
    delegate_id = SelectField('Link to Delegate (Optional)', coerce=int, validators=[Optional()])
    amount = StringField('Amount per Payment (KSh)', validators=[DataRequired()])
    frequency = SelectField('Payment Frequency', choices=[
        ('once', 'One-time'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ], validators=[DataRequired()])
    start_date = StringField('Start Date', validators=[DataRequired()])
    end_date = StringField('End Date (Optional)', validators=[Optional()])
    local_church = StringField('Local Church', validators=[Optional(), Length(max=100)])
    archdeaconry = SelectField('Archdeaconry', validators=[Optional()], validate_choice=False)
    parish = SelectField('Parish', validators=[Optional()], validate_choice=False)
    description = TextAreaField('Description/Purpose', validators=[Optional()])
    submit = SubmitField('Create Schedule')
    
    def __init__(self, *args, **kwargs):
        super(ScheduledPaymentForm, self).__init__(*args, **kwargs)
        self.archdeaconry.choices = [('', 'Select Archdeaconry')] + get_archdeaconries()[1:]
        self.parish.choices = [('', 'Select Parish')] + get_parishes()[1:]
        self.delegate_id.choices = [(0, 'Not linked to delegate')]


class InstallmentPaymentForm(FlaskForm):
    """Form for recording installment payments"""
    amount_paid = StringField('Amount Paid (KSh)', validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=[
        ('mpesa', 'M-Pesa'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque')
    ], validators=[DataRequired()])
    reference = StringField('Transaction Reference', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Record Payment')


class FundTransferForm(FlaskForm):
    """Form for initiating fund transfers"""
    amount = StringField('Amount to Transfer (KSh)', validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash (Hand over to recipient)'),
        ('mpesa_paybill', 'M-Pesa Paybill (Direct to Finance)'),
        ('bank_transfer', 'Bank Transfer')
    ], validators=[DataRequired()])
    mpesa_reference = StringField('M-Pesa Transaction Code', validators=[Optional(), Length(max=100)])
    to_user_id = SelectField('Transfer To', coerce=int, validators=[DataRequired()])
    description = TextAreaField('Description/Notes', validators=[Optional()])
    submit = SubmitField('Initiate Transfer')
    
    def __init__(self, *args, **kwargs):
        super(FundTransferForm, self).__init__(*args, **kwargs)
        self.to_user_id.choices = [(0, 'Select Recipient')]


class FundTransferApprovalForm(FlaskForm):
    """Form for approving/rejecting fund transfers"""
    action = SelectField('Action', choices=[
        ('approve', 'Approve Transfer'),
        ('reject', 'Reject Transfer')
    ], validators=[DataRequired()])
    notes = TextAreaField('Notes/Reason', validators=[Optional()])
    submit = SubmitField('Submit')


class FundTransferCompleteForm(FlaskForm):
    """Form for marking fund transfer as completed"""
    notes = TextAreaField('Confirmation Notes', validators=[Optional()])
    submit = SubmitField('Confirm Receipt & Complete')


class PaymentConfirmationForm(FlaskForm):
    """Form for confirming payments"""
    action = SelectField('Action', choices=[
        ('confirm', 'Confirm Payment'),
        ('reject', 'Reject Payment')
    ], validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Submit')

