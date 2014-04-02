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

def add_pb_agents(place_key, tsv_file):
    """Takes a tsv file containing name, phone, email fields and adds them as PB agents.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    def parse_line(line):
        name, phone, email = line.strip("\n").split("\t")
        return web.storage(name=name, phone=phone, email=email, voterid=None)

    agents = [parse_line(line) for line in open(tsv_file) if line.strip()]
    _add_pb_agents(place, agents)

def _add_pb_agents(place, agents):
    """Expect that each agent is a storage object with name, phone, email and voterid fields.
    """
    pb_agents = set((a.email, a.phone) for a in place.get_all_volunteers("pb_agent"))
    for a in agents:
        if (a.email, a.phone) not in pb_agents:
            p = a.get("place") or place
            p.add_volunteer(name=a.name, email=a.email, phone=a.phone, role='pb_agent', voterid=a.voterid)
            pb_agents.add((a.email, a.phone))
            logger.info("adding {} <{}> as volunteer".format(a.name, a.email))

def autoadd_pb_agents(place_key):
    """Finds all volunteers in the place and adds a new role as polling booth agent.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    _add_pb_agents(place, place.get_all_volunteers())

def update_voterinfo(place_key):
    """Updtes voter info of all volunteers with voterids whos voter info is not updated yet.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))    
    for a in place.get_all_volunteers("pb_agent"):
        a.populate_voterid_info()
        info = a.get_voterid_info()
        if info and info.pb_id != a.place_id:
            a.update(place_id=info.pb_id)

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
        'update_voterinfo': update_voterinfo,
        'add_pb_agents': add_pb_agents,        
    }
    cmdname = sys.argv[1]
    print cmdname
    cmd = CMDS.get(cmdname)
    if cmdname == 'add_pb_agents':
        add_pb_agents(sys.argv[2], sys.argv[3])
    elif cmd:
        places = sys.argv[2:]
        for p in places:
            cmd(p)
    else:
        print >> sys.stderr, "Unknown command {}".format(cmdname)

if __name__ == "__main__":
    main()            