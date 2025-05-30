FROM python:3.9

ENV LOCAL_MODE=true
ENV EXECUTER_IMAGES_DIR=/executer-images

ARG API_URL=https://api.inductiva.ai
ENV API_URL=${API_URL}

RUN apt-get update && apt-get install -y wget

RUN wget https://www.7-zip.org/a/7z2409-linux-x64.tar.xz && \
    tar -xf 7z2409-linux-x64.tar.xz && \
    mv 7zz /usr/local/bin/ && chmod +x /usr/local/bin/7zz && \
    rm -rf 7z2409-linux-x64.tar.xz

RUN cd /tmp \
    && wget https://github.com/apptainer/apptainer/releases/download/v1.3.3/apptainer_1.3.3_amd64.deb \
    && apt-get install -y ./apptainer_1.3.3_amd64.deb \
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
ENV MPIRUN_BIN_PATH_TEMPLATE /opt/openmpi/{version}/bin/mpirun

# Install the package dependencies in the requirements file.
COPY /task-runner/requirements.txt /requirements.txt
RUN pip install --no-cache-dir --upgrade -r /requirements.txt

COPY /task-runner /task-runner
WORKDIR /task-runner
RUN pip install .

COPY ./common/events /common/events
RUN pip install --no-cache-dir --upgrade /common/events
COPY ./common/task_status /common/task_status
RUN pip install --no-cache-dir --upgrade /common/task_status

RUN useradd -m -s /bin/bash task-runner
RUN mkdir /workdir
RUN mkdir /executer-images
VOLUME /executer-images
RUN chown task-runner:task-runner /workdir
RUN chown task-runner:task-runner /executer-images
USER task-runner

CMD ["python", "./task_runner/main.py"]
