FROM python:3.9

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
RUN ./configure --prefix=/opt/openmpi/4.1.6
RUN make all
RUN make install
RUN ldconfig

RUN apt-get install -y gmsh

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

CMD ["python", "./executer_tracker/main.py"]
