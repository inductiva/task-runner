ARG BASE_IMAGE

# Specify the executer base image as a build argument.
# Available executers with respective Dockerfiles are present
# in the executers directory.
FROM ${BASE_IMAGE}

# Install the package dependencies in the requirements file.
COPY ./executer-tracker/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./executer-tracker/src /code


COPY ./common/events /common/events
RUN pip install --no-cache-dir --upgrade /common/events
COPY ./common/task_status /common/task_status
RUN pip install --no-cache-dir --upgrade /common/task_status

# Set the current working directory to /code.
WORKDIR /code

ENV ARTIFACT_STORE=/mnt/artifacts

CMD ["python", "executer_tracker.py"]
