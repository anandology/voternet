from webapp import xrender, check_config
from models import Place
import utils
import sys

def email_fill_voterid(place_key):
    """Reminds all PB volunteers who have not filled their voter ID
    in the specified place to fill it.

    place can be a PC/AC or a WARD.
    """
    place = Place.find(place_key)
    if not place:
        raise ValueError("Invalid place {0}".format(place_key))

    agents = [a for a in place.get_pb_agents() if not a.voterid if a.email]    
    for a in agents:
        utils.send_email(a.email, xrender.email_fill_voterid(a))

def main():  
    check_config()
    cmd = sys.argv[1]
    if cmd == 'fill-voterid':
        places = sys.argv[2:]
        for p in places:
            email_fill_voterid(p)

if __name__ == "__main__":
    main()            