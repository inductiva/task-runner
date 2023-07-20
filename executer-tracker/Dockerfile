FROM python:3.11

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

COPY ./executer-tracker/containers.json /etc/config/

CMD ["python", "main.py"]
