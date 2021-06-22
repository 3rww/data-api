#!/bin/bash

python3 manage.py migrate --no-input --database=default
# pipenv run python3 manage.py migrate --no-input
