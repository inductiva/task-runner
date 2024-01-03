#!/bin/bash

PYTHON_BIN="/opt/executer-tracker/venv/bin/python3"
APP_PATH="/opt/executer-tracker/executer_tracker/main.py"

start() {
	export WORKDIR="/opt/executer-tracker/workdir"
	export ARTIFACT_STORE="gs://"
	export EXECUTER_IMAGES_DIR="/root/apptainer"
	export EXECUTERS_CONFIG="/etc/executer-images-config.json"
	export GIT_COMMIT_HASH="$(cat revision.txt)"
	export API_URL="$(curl "http://metadata.google.internal/computeMetadata/v1/project/attributes/api-url" -H "Metadata-Flavor: Google")"
	export REDIS_HOSTNAME="$(curl "http://metadata.google.internal/computeMetadata/v1/project/attributes/redis-hostname" -H "Metadata-Flavor: Google")"

	if [[ $1 == "mpi" ]]; then
		export MPI_HEAD_NODE="true"
	fi

    $PYTHON_BIN $APP_PATH
}

start $@
