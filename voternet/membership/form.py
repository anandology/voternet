import web
from wtforms import (
    Form,
    BooleanField, DateField, IntegerField,
    StringField, TextAreaField,
    SelectField, RadioField, SelectMultipleField,
    validators, widgets)

class MultiDict(web.storage):
    """wtforms expect the formdate to be a multi-dict instance with getall method.
    This is a hack to make it work with web.py apps.
    """
    def getall(self, name):
        if name in self:
            value = self[name]
            if not isinstance(value, list):
                value = [value]
            return value
        else:
            return []

class BaseForm(Form):
    def __init__(self, formdata=None, **kwargs):
        formdata = formdata and MultiDict(formdata) or None
        Form.__init__(self, formdata, **kwargs)


def radio_field(label, values, **kwargs):
    return RadioField(label, [validators.Required()], choices=[(v, v) for v in values], **kwargs)

def checkbox_field(label, values, validators=None):
    return SelectMultipleField(
        label,
        choices=[(v, v) for v in values],
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
        validators=validators or []
        )

class RegistrationForm(BaseForm):
    name = StringField('Name', [validators.Required()])
    father_name = StringField('Father Name', [validators.Required()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female')])
    date_of_birth = DateField('Date of Birth')
    mobile = StringField('Personal Mobile No.', [validators.Required()])
    mobile2 = StringField('Personal Mobile No. 2')
    email = StringField('Personal E-Mail ID', [validators.Required(), validators.Email()])

    emergency_contact = TextAreaField('EMERGENCY CONTACT NAME, RELATIONSHIP & MOBILE NUMBER', [validators.Required()])

    address = TextAreaField('Residential Address', [validators.Required()])
    pincode = StringField('PIN Code', [validators.Required()])

    employer = StringField('EMPLOYER NAME OR PROFESSION', [validators.Required()])

    livelihood = radio_field("Your Occupation", ['SALARIED EMPLOYEE', 'SELF EMPLOYED', 'RETIRED', 'STUDENT', 'OTHER'])
    choice_of_communication = checkbox_field("Your Preferred Choice of Communication",
        ['SMS', 'WHATSAPP', 'E-MAIL', 'FACEBOOK', 'TWITTER'],
        [validators.Required()])

    work_from = radio_field('WHERE YOU WOULD LIKE TO WORK FROM', ['HOME', 'OUTSIDE', 'BOTH'])
    internet_connection = radio_field("DO YOU HAVE INTERNET CONNECTION AT HOME", ['YES', 'NO'])

    how_much_time = radio_field("HOW MUCH TIME YOU CAN VOLUNTEER", [
        "FULL TIME",
        "2-4 HOURS DAILY",
        "1 HOUR/DAY ON WEEKDAYS",
        "ONLY WEEKEND"
        ])

    languages = checkbox_field("Languages That You Can Speak", [
        "KANNADA",
        "ENGLISH",
        "HINDI", 
        "OTHER SOUTH INDIAN LANGUAGE"
    ], [validators.Required()])

    skills = checkbox_field("Areas where you can volunteer for Central Team", [
        "Accounting/Finance",
        "Content Translators (Like Kannada News to Eng or Viceversa)",
        "Coordinators/ managers",
        "Creative (poets, musicians, artists, street theater)",
        "Data entry from Anywhere",
        "Designers on Photoshop / CorelDraw",
        "Doctor/ Healthcare",
        "Event Management",
        "FB / E-mail Content writing",
        "Following on FB / Twitter for Feeder service",
        "Fund Raising",
        "Graphic designing",
        "Handle Helpline calls from Home",
        "Joomal / Drupal / Webdesigning Expert",
        "Legal Service",
        "Logistic  Management",
        "Media / Journalism / Communication",
        "Office administration",
        "On the ground work",
        "Online Researchers",
        "Photographer/Videographer",
        "Public Speaking",
        "Publicity / Advertisement",
        "RTI Activist",
        "Social Media Moderator (FB / Twitter)",
        "Sourcing of News from online",
        "System administrator",
        "Technical support / Information Tech.",
        "Tele campaigning",
        "Trainers",
        "Video Editor / Film Maker",
        "Volunteer management",
    ], [validators.Required()])

    active_volunteer = radio_field("Have you volunteered for Aam Aadmi Party before?", ['YES', 'NO'])

    contributions = checkbox_field("What did you do?", [
            "On-ground activities in Karnataka",
            "Remote/back-office activities in Karnataka",
            "On-ground activities in Delhi",
            "Remote/back-office activities in Delhi",
        ])

    reporting_person_name = StringField("Name of the person that you've reported to")
    reporting_person_mobile = StringField("Mobile number of the person that you've reported to")

    is_voter_at_residence = radio_field("Is your Voter ID address same as your residential address?", ['YES', 'NO', "I don't have a valid Voter ID"])
    voterid = StringField("Personal Voter ID")
    proxy_voterid = StringField("Proxy Voter ID")
