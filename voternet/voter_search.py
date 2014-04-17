import os
import web
from models import Voter
from webapp import check_config
import logging

logger = logging.getLogger(__name__)

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
            logger.info("request for %s", i.voterid)
            voter = Voter.find(i.voterid)
            if voter:
                logger.info("%s - match found", i.voterid)
            else:
                logger.info("%s - no match found", i.voterid)
            return render.voter(voter, query=i.voterid)
        else:
            return render.voter()

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