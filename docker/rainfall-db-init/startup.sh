#!/bin/bash

python3 manage.py migrate rainfall --no-input --database=rainfall_db
# pipenv run python3 manage.py migrate --no-input
