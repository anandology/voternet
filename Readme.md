voternet
========

System to manage volunteers for election campaign, from state to polling booth level.

Currently designed to work with Karnataka.

How to setup
============

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
