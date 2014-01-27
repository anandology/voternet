import web
import os
from models import Place

urls = (
    "/", "index",
    "/(\w+)", "place",
    "/(\w+)/edit", "place_edit",
)

app = web.application(urls, globals())

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path, base="site")

class index:
    def GET(self):
        raise web.redirect("/karnataka")

class place:
    def GET(self, code):
        place = Place.find(code=code)
        return render.place(place)

if __name__ == "__main__":
    app.run()