ARG BASE_IMAGE

# Specify the executer base image as a build argument.
# Available executers with respective Dockerfiles are present
# in the executers directory.
FROM ${BASE_IMAGE}

# Install the package dependencies in the requirements file.
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./src /code

# Set the current working directory to /code.
WORKDIR /code

ENV ARTIFACT_STORE=/mnt/artifacts

CMD ["python", "executer_tracker.py", "--redis_consumer_name=${REDIS_CONSUMER_NAME}"]
