import os
import web
from models import Voter
from webapp import check_config

urls = (
    "/", "voterid_search"
)
app = web.application(urls, globals())

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path)

class voterid_search:
    def GET(self):
        i = web.input(voterid="")
        if i.voterid:
            voter = Voter.find(i.voterid)
            return render.voter(voter, query=i.voterid)
        else:
            return render.voter()

def main():
    check_config()
    app.run()

if __name__ == '__main__':
    main()