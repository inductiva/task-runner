FROM python:3.11

RUN apt-get update && apt-get install -y wget
RUN cd /tmp \
    && wget https://github.com/apptainer/apptainer/releases/download/v1.2.5/apptainer_1.2.5_amd64.deb \
    && apt-get install -y ./apptainer_1.2.5_amd64.deb \
    && rm /tmp/*

WORKDIR /
RUN wget https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.6.tar.gz
RUN apt-get install -y build-essential
RUN tar zxvf openmpi-4.1.6.tar.gz
WORKDIR /openmpi-4.1.6
RUN ./configure --prefix=/usr/local
RUN make all
RUN make install
RUN ldconfig


RUN apt-get install -y gmsh

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

RUN apt-get install -y openssh-server

RUN sed -i '/^#PermitRootLogin/s/#//' /etc/ssh/sshd_config
RUN sed -i '/^PermitRootLogin/s/prohibit-password/yes/' /etc/ssh/sshd_config
RUN service ssh start


ARG SSH_DIR=/root/.ssh

COPY ./executer-tracker/id_mpi $SSH_DIR/id_mpi
COPY ./executer-tracker/id_mpi.pub $SSH_DIR/id_mpi.pub
COPY ./executer-tracker/id_mpi.pub $SSH_DIR/authorized_keys

RUN chmod 0700 $SSH_DIR
RUN chmod 0644 $SSH_DIR/id_mpi.pub
RUN chmod 0600 $SSH_DIR/authorized_keys
RUN chmod 0600 $SSH_DIR/id_mpi
RUN (echo "Host *"; echo " IdentityFile ~/.ssh/id_mpi"; echo " StrictHostKeyChecking no"; echo "") > $SSH_DIR/config

CMD ["bash", "-c", "service ssh start && python ./executer_tracker/main.py"]
