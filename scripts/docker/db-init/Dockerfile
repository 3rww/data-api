FROM python:3.10

RUN apt-get update && \
    apt-get -y autoremove && \
    apt-get install -y \
    postgresql-client \
	libgeos-dev \
	binutils \
	libproj-dev \
	gdal-bin \
	git

RUN pip install pipenv
# COPY requirements.txt /code/
COPY Pipfile /code/
COPY Pipfile.lock /code/
WORKDIR /code/
RUN pipenv lock -r > requirements.txt
RUN pip install -r requirements.txt
# RUN pipenv install --deploy

COPY . /code/

CMD [ "./scripts/docker/wait-for-postgres.sh", "db", "./scripts/docker/db-init/startup.sh" ]
