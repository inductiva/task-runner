FROM python:3.9

# Install the package dependencies in the requirements file.
COPY /file-streamer/requirements.txt /requirements.txt
RUN pip install --no-cache-dir --upgrade -r /requirements.txt

COPY /file-streamer /file-streamer
WORKDIR /file-streamer
RUN pip install .

CMD ["python", "./file_streamer/sender.py"]
