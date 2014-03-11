voternet
========

System to manage volunteers for election campaign, from state to polling booth level.

Currently designed to work with Karnataka.

System Requirements
===================

* PostgreSQL
* Python 2.6+

How to setup
============

* clone the repo

        git clone https://github.com/anandology/voternet.git
        cd voternet

* setup virtualenv

        virtualenv . 
        source bin/activate
        # For windows, try the following instead
        # bin/activate.bat

* install required Python packages

        python setup.py develop

* create voternet postgres database

        createdb voternet

* create schema

        psql voternet < voternet/schema.sql

* setup config file
    
        cp sample_config.yml config.yml
        # edit config.yml and make changes as required

* load sample data (See places/KA for sample files and required format).

        python voternet/loaddata.py --config config.yml places/KA KA Karnataka

* Add yourself as admin

        python voternet/loaddata.py --config config.yml --add-admin yourname@gmail.com

* run the app

        python voternet/webapp.py --config config.yml

Instructions to setup the system for a state
=============================================

Ask the webmaster to add you as admin for the state. You'll be able to add more users once you are an admin.

Admin Tasks
-----------

* Add more admin users from /state_code/users (e.g. /KA/users).
* Add coordinators for a state from /state_code (e.g. /KA)
* setup regions from /state_code/regions (e.g. /KA/regions). Parliamentary Constitituencies are grouped into regions, they usually represent the polical structure in the party. For example, Karnataka has Bangalore, Tumkur, Hassan etc. regions.
* Group polling booths as groups. There are 2 different grouping, wards and regions. Wards are added at the load time from the input data and regions can be added manually. As of now, there is no way to create a new ward manually. This can be done from /state-code/ACXXX/groups. (e.g /KA/AC123/groups)
* Add coordinators and volunteers for each level

   * state - e.g. /KA
   * region - e.g. /KA/R01
   * PC - e.g. /KA/PC01
   * AC - e.g. /KA/AC152
   * ward - e.g. /KA/AC152/W005
   * group - e.g. /KA/AC152/G03
   * polling booth - e.g. /KA/AC152/PB0123

* It is possible to add volunteers to State, PC or AC, but that is not usually done. We usually add many volunteers at ward/region level as sometimes it is too cumbersome to assign volunteers to each polling booth.
* Door-to-door coverage activity can be added from polling booth page /KA/AC152/PB0123

Permission System
-----------------

* Admin can add coordinator or volunteer at any level
* A coordinator can add coordinators and volunteers to any place in his subtree
