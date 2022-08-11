#!/bin/bash

python3 manage.py collectstatic --no-input
python3 manage.py runserver 0.0.0.0:7000