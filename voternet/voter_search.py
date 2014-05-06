import os
import web
from models import Voter
from webapp import check_config
import logging
import json

logger = logging.getLogger(__name__)

urls = (
    "/", "voterid_search",
    "/AC(\d+)", 'voterid_search_ac',
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

class voterid_search_ac:
    def GET(self, ac):
        i = web.input(q="", format="html")
        if i.format == "json":
            return self.GET_json(ac, i)
        else:
            return self.GET_html(ac, i)

    def GET_html(self, ac, i):
        if i.q:
            logger.info("request for %s", i.q)
            voters = self.find_voters(ac, i.q)
            return render.voter_ac(voters, query=i.q)
        else:
            return render.voter_ac()

    def GET_json(self, ac, i):
        web.header("content-type", "application/json")        
        if not i.q:
            d = {
                "status": "error", 
                "errcode": "voterid-missing", 
                "message": "Please provide voterid as query parameter."
            }
        else:
            voters = self.find_voters(ac, i.q)
            if voters:
                d = dict(matches=voters, status="ok")
            else:
                d = dict(status="error", errcode="voterid-invalid", message="Invalid Voter ID")
        return json.dumps(d)            

    def find_voters(self, ac, q):
        voters = Voter.search(ac, q)
        if voters:
            logger.info("%s - %d matches found", q, len(voters))
        else:
            logger.info("%s - no match found", q)
        return voters

def main():
    FORMAT = "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)

    logger.info("ready")

    # set socket timeout so that ceokarnataka website won't take us down
    import socket
    socket.setdefaulttimeout(3)

    check_config()
    app.run()

if __name__ == '__main__':
    main()