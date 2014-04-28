import os
import web
from models import Voter
from webapp import check_config
import logging
import json

logger = logging.getLogger(__name__)

urls = (
    "/", "voterid_search"
)
app = web.application(urls, globals())

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path)

class voterid_search:
    def GET(self):
        i = web.input(voterid="", format="html")
        if i.format == "json":
            return self.GET_json(i)
        else:
            return self.GET_html(i)

    def GET_html(self, i):
        if i.voterid:
            logger.info("request for %s", i.voterid)
            voter = self.find_voter(i.voterid)
            return render.voter(voter, query=i.voterid)
        else:
            return render.voter()

    def GET_json(self, i):
        web.header("content-type", "application/json")        
        if not i.voterid:
            d = {
                "status": "error", 
                "errcode": "voterid-missing", 
                "message": "Please provide voterid as query parameter."
            }
        else:
            voter = self.find_voter(i.voterid)
            if voter:
                d = dict(voter, status="ok")
            else:
                d = dict(status="error", errcode="voterid-invalid", message="Invalid Voter ID")
        return json.dumps(d)            

    def find_voter(self, voterid):
        voter = Voter.find(voterid)
        if voter:
            logger.info("%s - match found", voterid)
        else:
            logger.info("%s - no match found", voterid)
        return voter

def main():
    FORMAT = "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)

    # set socket timeout so that ceokarnataka website won't take us down
    import socket
    socket.setdefaulttimeout(3)

    check_config()
    app.run()

if __name__ == '__main__':
    main()