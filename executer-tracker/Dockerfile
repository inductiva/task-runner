# Start from the official Python base image.
FROM python:3.11

# Set the current working directory to /code.
WORKDIR /code

RUN apt-get update && apt-get install -y npm
RUN npm install -g nodemon

COPY ./requirements.txt /code/requirements.txt

# Install the package dependencies in the requirements file.
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./src /code

