# Start from the official Python base image.
FROM python:3.11

# Set the current working directory to /code.
WORKDIR /code

COPY ./executer_tracker.py /code/executer_tracker.py
COPY ./task_request_handler.py /code/task_request_handler.py
COPY ./subprocess_tracker.py /code/subprocess_tracker.py
COPY ./utils /code/utils

COPY ./requirements.txt /code/requirements.txt

# Install the package dependencies in the requirements file.
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN apt-get update && apt-get install -y npm
RUN npm install -g nodemon
