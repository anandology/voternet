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

def update_voterinfo(place_key):
    """Updtes voter info of all volunteers with voterids whos voter info is not updated yet.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))    
    for a in place.get_all_volunteers("pb_agent"):
        a.populate_voterid_info()

def setup_logger():
    FORMAT = "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)

def main():  
    setup_logger()

    # hack to work-around web.cookies() failure deepinside
    web.ctx.env = {}

    check_config()
    CMDS = {
        'email_fill_voterid': email_fill_voterid,
        'autoadd_pb_agents': autoadd_pb_agents,
        'update_voterinfo': update_voterinfo
    }
    cmdname = sys.argv[1]
    cmd = CMDS.get(cmdname)
    if cmd:
        places = sys.argv[2:]
        for p in places:
            cmd(p)
    else:
        print >> sys.stderr, "Unknown command {}".format(cmdname)

if __name__ == "__main__":
    main()            