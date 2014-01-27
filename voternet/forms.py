import web
from web import form
import re

class PhoneValidator(form.Validator):
    regexp = re.compile("[0-9 -]+")

    def __init__(self):
        form.Validator.__init__(self, "Invalid Phone number", self.valid)

    def valid(self, value):
        return self.regexp.match(value) and len(web.numify(value)) == 10

AddPeopleForm = form.Form(
    form.Textbox("name", form.notnull),
    form.Textbox("email"),
    form.Textbox("phone", form.notnull, PhoneValidator()),
)

