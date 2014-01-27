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

* load sample data

    python voternet/initdb.py 

* run the app

    python votenet/webapp.py
