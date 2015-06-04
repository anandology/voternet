#! /bin/bash

PORT=${1:-7000}
exec python voternet/webapp.py --config config.yml fastcgi $PORT
