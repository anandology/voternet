from webapp import check_config
from models import Place, Invite, get_db
import utils
import sys
import web
import re
import logging
from multiprocessing.pool import ThreadPool

logger = logging.getLogger(__name__)

def email_fill_voterid(place_key):
    """Reminds all PB volunteers who have not filled their voter ID
    in the specified place to fill it.

    place can be a PC/AC or a WARD.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    agents = [a for a in place.get_pb_agents() if a.email and not a.voterid]

    pool = ThreadPool(20)
    def sendmail(a):
        utils.sendmail_voterid_pending(a)
    pool.map(sendmail, agents)

def email_invites():
    def sendmail(a):
        try:
            utils.sendmail_voterid_pending(a)
        except Exception:
            logger.error("failed to send email to %s", a)
    agents = Invite.find_all()    
    pool = ThreadPool(20)    
    pool.map(sendmail, agents)

def add_invites(place_key, filename, batch):
    from webapp import import_people

    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    rows = [line.strip("\n").split("\t") for line in open(filename) if line.strip()]
    re_badchars = re.compile("[^A-Za-z0-9 \.-]+")
    count = 0
    with get_db().transaction():
        for row in rows:
            name, phone, email = row
            name = re_badchars.sub("", name).strip()
            d = web.storage(name=name, phone=phone, email=email, place=None, role=None)
            if import_people().add_volunteer(d, place, batch=batch, as_invite=True):
                count += 1
    logger.info("imported %s people", count)

def email_voterid_added(place_key):
    """Email all volunteers that their voter ID registration is complete.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    agents = [a for a in place.get_pb_agents() if a.email and a.get_voterid_info()]    
    conn = utils.get_smtp_conn()    
    for a in agents:
        utils.sendmail_voterid_added(a, conn=conn)

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

def debug(place_key):
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))    

    agents = [a for a in place.get_pb_agents() if a.voterid if a.email]
    a = agents[0]
    utils.sendmail_voterid_added(a)

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
        'email_voterid_added': email_voterid_added,
        'autoadd_pb_agents': autoadd_pb_agents,
        'update_voterinfo': update_voterinfo,
        'add_pb_agents': add_pb_agents,       
        'email_invites': email_invites,
        'debug': debug, 
    }
    cmdname = sys.argv[1]
    print cmdname
    cmd = CMDS.get(cmdname)
    if cmdname == 'add_pb_agents':
        add_pb_agents(sys.argv[2], sys.argv[3])
    elif cmdname == 'email_invites':
        email_invites()
    elif cmdname == 'add_invites':
        add_invites(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd:
        places = sys.argv[2:]
        for p in places:
            cmd(p)
    else:
        print >> sys.stderr, "Unknown command {}".format(cmdname)

if __name__ == "__main__":
    main()            