FROM python:3.9

ARG API_URL=https://api.inductiva.ai
ENV API_URL=${API_URL}

# Install the package dependencies in the requirements file.
COPY /file-tracker/requirements.txt /requirements.txt
RUN pip install --no-cache-dir --upgrade -r /requirements.txt

COPY /file-tracker /file-tracker
WORKDIR /file-tracker
RUN pip install .

CMD ["python", "./file_tracker/main.py"]
