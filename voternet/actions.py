from webapp import xrender, check_config
from models import Place
import utils
import sys
import web
import logging

logger = logging.getLogger(__name__)

def email_fill_voterid(place_key):
    """Reminds all PB volunteers who have not filled their voter ID
    in the specified place to fill it.

    place can be a PC/AC or a WARD.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    bcc = web.config.get("email_bcc_address")

    agents = [a for a in place.get_pb_agents() if not a.voterid if a.email]    
    for a in agents:
        utils.send_email(a.email, xrender.email_fill_voterid(a), bcc=bcc)

def autoadd_pb_agents(place_key):
    """Finds all volunteers in the place and adds a new role as polling booth agent.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    pb_agents = set((a.email, a.phone) for a in place.get_all_volunteers("pb_agent"))

    for v in place.get_all_volunteers():
        if (v.email, v.phone) not in pb_agents:
            v.place.add_volunteer(name=v.name, email=v.email, phone=v.phone, role='pb_agent', voterid=v.voterid)
            pb_agents.add((v.email, v.phone))

def setup_logger():
    FORMAT = "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)

def main():  
    setup_logger()
    
    # hack to work-around web.cookies() failure deepinside
    web.ctx.env = {}

    check_config()
    cmd = sys.argv[1]
    if cmd == 'email_fill_voterid':
        places = sys.argv[2:]
        for p in places:
            email_fill_voterid(p)
    elif cmd == "autoadd_pb_agents":
        places = sys.argv[2:]
        for p in places:
            autoadd_pb_agents(p)

if __name__ == "__main__":
    main()            