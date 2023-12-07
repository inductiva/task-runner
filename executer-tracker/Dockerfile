FROM python:3.11

RUN apt-get update && apt-get install -y wget
RUN cd /tmp \
    && wget https://github.com/apptainer/apptainer/releases/download/v1.2.5/apptainer_1.2.5_amd64.deb \
    && apt-get install -y ./apptainer_1.2.5_amd64.deb \
    && rm /tmp/*

# Accept git commit as a build argument and set it as environment variable
# so that it can be accessed in the code.
# Provide argument by adding the following to the docker build command:
# --build-arg GIT_COMMIT_HASH=$(git rev-parse HEAD)
ARG GIT_COMMIT_HASH
ENV GIT_COMMIT_HASH=$GIT_COMMIT_HASH

# Install the package dependencies in the requirements file.
COPY /executer-tracker/requirements.txt /requirements.txt
RUN pip install --no-cache-dir --upgrade -r /requirements.txt

COPY /executer-tracker /executer-tracker
WORKDIR /executer-tracker
RUN pip install .

COPY ./common/events /common/events
RUN pip install --no-cache-dir --upgrade /common/events
COPY ./common/task_status /common/task_status
RUN pip install --no-cache-dir --upgrade /common/task_status

ENV ARTIFACT_STORE=/mnt/artifacts

CMD ["python", "./executer_tracker/main.py"]
