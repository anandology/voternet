"""module to load voter details from EC website.
"""
import web
import sys
import logging
from bs4 import BeautifulSoup
import urllib

logger = logging.getLogger(__name__)

URL = "http://ceoaperms.ap.gov.in/Search/search1.aspx"

HEADERS = {
    "Referer": URL,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/33.0.1750.146 Safari/537.36"
}


class Browser(web.Browser):
    _soup = None

    def get_soup(self):
        """Returns beautiful soup of the current document."""
        if self._soup is None:
            self._soup = BeautifulSoup(self.data, "lxml")
        return self._soup

    def read_formdata(self):
        soup = self.get_soup()
        params = {}

        for s in soup.find_all("select"):
            params[s['name']] = self.find_select_value(s)

        params['__EVENTARGUMENT'] = ''
        params['__LASTFOCUS'] = ''
        ev = soup.find("input", {"name": "__EVENTVALIDATION"})
        if ev:
            params['__EVENTVALIDATION']  = ev['value']
        params['__VIEWSTATE'] = soup.find("input", {"name": "__VIEWSTATE"})['value']
        return params

    def find_select_value(self, select):
        if isinstance(select, basestring):
            select = self.get_soup().find("select", {"name": select})
        option = select.find("option", {"selected": "selected"})
        return option and option.get('value')   

    def open(self, url, payload=None, headers=HEADERS):
        xparams = payload and dict((k, v) for k, v in payload.items() if not k.startswith("_") and v)
        logger.info("open %s %s", URL, xparams)

        if isinstance(payload, dict):
            payload = urllib.urlencode(payload)

        self._soup = None
        return web.Browser.open(self, url, payload, headers)             

def get_voter_details(district_code, ac_code, voterid):
    # ignore voterids like "yes" etc.
    if len(voterid) <= 4:
        return

    logger.info("get_voter_details %s", voterid)    
    b = Browser()
    b.open(URL)

    # select district
    params = b.read_formdata()
    params['ddldistlist'] = district_code
    params['__EVENTTARGET'] = 'ddldistlist'
    params['__VIEWSTATEENCRYPTED'] = ''
    params['RadioButtonList1'] = 'STARTSWITH'
    params['RadioButtonList2'] = 'B'
    params['txtHNo'] = ''
    params['txtFname'] = ''
    del params['ddlaclist']
    b.open(URL, params)

    # fill in ac and voterid
    params = b.read_formdata()
    params['__EVENTTARGET'] = ''
    params['__VIEWSTATEENCRYPTED'] = ''
    params['RadioButtonList1'] = 'STARTSWITH'
    params['RadioButtonList2'] = 'B'
    params['txtHNo'] = ''
    params['txtFname'] = ''
    params['ddlaclist'] = ac_code
    params['txtIdNo'] = voterid
    params['btn_Search'] = "Search"
    b.open(URL, params)

    # parse the response
    soup = b.get_soup()
    table = soup.find("table", {"id": "GridView1"})
    if not table:
        return
    last_row = table.find_all("tr")[-1]
    data = [td.getText().strip() for td in last_row.find_all(("td", "tr"))]

    data = data[:-1] # skip the last column which is just a print link.
    cols = "name age house idcard rel_name part sl_no gender".split()
    d = web.storage(zip(cols, data))
    re_num = web.re_compile("(\d+)")
    part_no = re_num.match(d.part).group(1)
    info = web.storage(voterid=voterid, 
            name=d.name, 
            rel_name=d.rel_name, 
            age=d.age, 
            gender=d.gender, 
            address=d.house,
            part_no=part_no,
            part=d.part)
    logger.info("voter info %s %s", voterid, info)
    return info

if __name__ == '__main__':
    FORMAT = "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    print get_voter_details(sys.argv[1], sys.argv[2], sys.argv[3])
