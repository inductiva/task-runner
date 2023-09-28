FROM python:3.11

# Accept git commit as a build argument and set it as environment variable
# so that it can be accessed in the code.
# Provide argument by adding the following to the docker build command:
# --build-arg GIT_COMMIT=$(git rev-parse HEAD)
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

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

CMD ["python", "main.py"]
