import web
import os
from models import Place
from forms import AddPeopleForm
import markdown

urls = (
    "/", "index",
    "/([\w/]+)/edit", "edit_place",
    "/([\w/]+)/info", "place_info",
    "/([\w/]+)/add-people", "add_people",
    "/([\w/]+)", "place",
)

app = web.application(urls, globals())

def input_class(input):
    if input.note:
        return "has-error"
    else:
        return ""

def plural(name):
    if name.endswith("y"):
        return name[:-1] + "ies"
    else:
        return name + 's'

tglobals = {
    "input_class": input_class, 
    "plural": plural,
    "markdown": markdown.markdown,
    "sum": sum,
}

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path, base="site", globals=tglobals)

class index:
    def GET(self):
        raise web.redirect("/karnataka")

class place:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        return render.place(place)

class edit_place:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        return render.edit_place(place)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        i = web.input(places="")
        place.add_places(i.places)
        raise web.seeother(place.url)

class place_info:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        i = web.input(m=None)
        if i.m == "edit":
            return render.edit_info(place)
        else:
            return render.place_info(place)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        i = web.input(info="")
        place.update_info(i.info)
        raise web.seeother(place.url + "/info")

class add_people:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        form = AddPeopleForm()
        return render.add_people(place, form)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        i = web.input()
        form = AddPeopleForm()
        if form.validates(i):
            place.add_volunteer(i.name, i.email, i.phone)
            raise web.redirect(place.url)
        else:
            return render.add_people(place, form)

if __name__ == "__main__":
    app.run()