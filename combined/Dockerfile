FROM inductiva/task-runner:latest

USER root

# Install file-tracker
COPY /file-tracker/requirements.txt /file-tracker-requirements.txt
RUN pip install --no-cache-dir --upgrade -r /file-tracker-requirements.txt

COPY /file-tracker /file-tracker
WORKDIR /file-tracker
RUN pip install .

ENV FILE_TRACKER_HOST=0.0.0.0
ENV FILE_TRACKER_PORT=5000

EXPOSE 5000

# Create startup script
WORKDIR /
COPY /start_services.sh /start_services.sh
RUN chmod +x /start_services.sh
RUN chown task-runner:task-runner /start_services.sh

USER task-runner

CMD ["/start_services.sh"]
