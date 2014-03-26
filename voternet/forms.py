import web
from wtforms import Form, PasswordField, StringField, SelectField, validators, ValidationError
import account
from models import Person

class MultiDict(web.storage):
    def getall(self, name):
        if name in self:
            return [self[name]]
        else:
            return []

class BaseForm(Form):
    def __init__(self, formdata=None, **kwargs):
        formdata = formdata and MultiDict(formdata) or None
        Form.__init__(self, formdata, **kwargs)

class AddPeopleForm(BaseForm):
    name = StringField('Name', [validators.Required()])
    phone = StringField('Phone Number', [
        validators.Required(), 
        validators.Regexp(r'[0-9 +-]{10,}', message="That doesn't like a valid phone number.")])
    email = StringField('Email Address', [validators.Email()])
    voterid = StringField('Voter ID')
    role = SelectField('Role', choices=[('volunteer', 'Volunteer'), ('pb_agent', 'Polling Booth Agent'), ('coordinator', 'Coordinator')])

class ChangePasswordForm(BaseForm):
    password = PasswordField('New Password', [
        validators.Required(),
        validators.EqualTo('password2', message='Passwords must match'),
        validators.Length(min=6, message="Please use a password of 6 characters or longer.")
    ])
    password2 = PasswordField('Repeat Password')

class LoginForm(BaseForm):
    email = StringField('E-Mail Address', [
        validators.Required(),
        validators.Email()])
    password = PasswordField("Password", [
        validators.Required()])

    def validate_email(self, field):
        p = Person.find(email=field.data)
        if not p:
            raise ValidationError("Unable to find an account with this email.")

    def validate_password(self, field):
        p = Person.find(email=self.email.data)
        if p and not account.check_salted_hash(field.data, p.get_encrypted_password()):
            raise ValidationError("That password seems incorrect. Please try again?")
