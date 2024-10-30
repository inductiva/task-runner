FROM python:3.9

# Install the package dependencies in the requirements file.
COPY /file-tracker/requirements.txt /requirements.txt
RUN pip install --no-cache-dir --upgrade -r /requirements.txt

COPY /file-tracker /file-tracker
WORKDIR /file-tracker
RUN pip install .

CMD ["python", "./file_tracker/main.py"]
