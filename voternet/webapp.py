import web
import os
from models import Place
from forms import AddPeopleForm

urls = (
    "/", "index",
    "/(\w+)", "place",
    "/(\w+)/add-people", "add_people",
)

app = web.application(urls, globals())

def input_class(input):
    if input.note:
        return "has-error"
    else:
        return ""

tglobals = dict(input_class=input_class)

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path, base="site", globals=tglobals)

class index:
    def GET(self):
        raise web.redirect("/karnataka")

class place:
    def GET(self, code):
        place = Place.find(code=code)
        return render.place(place)
        
class add_people:
    def GET(self, code):
        place = Place.find(code=code)
        form = AddPeopleForm()
        return render.add_people(place, form)

    def POST(self, code):
        place = Place.find(code=code)
        i = web.input()
        print i
        form = AddPeopleForm()
        if form.validates(i):
            place.add_volunteer(i.name, i.email, i.phone)
            raise web.redirect("/" + place.code)
        else:
            print form.name.value
            return render.add_people(place, form)

if __name__ == "__main__":
    app.run()