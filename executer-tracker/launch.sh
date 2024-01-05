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
		NETWORK_URI=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/network" -H "Metadata-Flavor: Google")
		NETWORK_NAME=$(basename $NETWORK_URI)
		ZONE_URI=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/zone" -H "Metadata-Flavor: Google")
		ZONE=$(basename $ZONE_URI)
		REGION=$(echo $ZONE | sed 's/-.$//')
		SUBNET=$(gcloud compute networks subnets list --filter="name=( '$NETWORK_NAME' )" --regions=$REGION --format 'csv[no-heading](RANGE)')

		echo Subnet: $SUBNET

		export MPI_HEAD_NODE="true"
		export MPI_SHARE_PATH="/mpi"
		export MPI_HOSTFILE_PATH="/root/mpi_hosts"
		export MPI_EXTRA_ARGS="--allow-run-as-root --mca btl_tcp_if_include $SUBNET --mca oob_tcp_if_include $SUBNET"
	fi

    $PYTHON_BIN $APP_PATH
}

start $@
