#!/bin/bash

python3 manage.py migrate --no-input --database=default
# python3 manage.py initadmin