FROM python:3.10

RUN apt-get update
RUN apt-get -y autoremove && apt-get install -y \
	libgeos-dev \
	binutils \
	libproj-dev \
	gdal-bin \
	git

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir /code
WORKDIR /code/
# RUN pip install
RUN pip install pipenv
# COPY requirements.txt /code/requirements.txt
COPY Pipfile /code/Pipfile
COPY Pipfile.lock /code/Pipfile.lock
# RUN pipenv lock -r > requirements.txt
RUN pipenv requirements > requirements.txt
RUN pip install -r /code/requirements.txt
# RUN pipenv install --deploy

COPY . /code/

CMD [ "./scripts/docker/trwwapi/startup.sh" ]