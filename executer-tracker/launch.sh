#!/bin/bash

PYTHON_BIN="/opt/executer-tracker/venv/bin/python3"
APP_PATH="/opt/executer-tracker/executer_tracker/main.py"
EXECUTER_TRACKER_DATA_DISK_DIR="/mnt/disks/executer-tracker-data"

start() {
	export EXECUTER_API_KEY="$(gcloud secrets versions access latest --secret=executer-tracker-api-key)"
	export WORKDIR=$EXECUTER_TRACKER_DATA_DISK_DIR"/workdir"
	export EXECUTER_IMAGES_DIR=$EXECUTER_TRACKER_DATA_DISK_DIR"/apptainer"
	export ARTIFACT_STORE="gs://"
	export GIT_COMMIT_HASH="$(cat revision.txt)"
	export MPIRUN_BIN_PATH_TEMPLATE="/opt/openmpi/{version}/bin/mpirun"
	export MPI_DEFAULT_VERSION="4.1.6"

	export API_URL="$(curl "http://metadata.google.internal/computeMetadata/v1/project/attributes/api-url" -H "Metadata-Flavor: Google")"
	export REDIS_HOSTNAME="$(curl "http://metadata.google.internal/computeMetadata/v1/project/attributes/redis-hostname" -H "Metadata-Flavor: Google")"
    export LOGGING_HOSTNAME="$(curl "http://metadata.google.internal/computeMetadata/v1/project/attributes/logging-hostname" -H "Metadata-Flavor: Google")"
	export MPI_EXTRA_ARGS="--allow-run-as-root"
	export EXECUTER_IMAGES_REMOTE_STORAGE="gs://inductiva-apptainer-images"
	export EXECUTER_TRACKER_TOKEN=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/attributes/executer_tracker_token" -H "Metadata-Flavor: Google")
	export LOCAL_MODE="false"

	DATA_DISK_MOUNT_PATH=/mnt/disks/executer-tracker-data
	export APPTAINER_CACHEDIR=$DATA_DISK_MOUNT_PATH/apptainer/.cache
	export APPTAINER_TMPDIR=$DATA_DISK_MOUNT_PATH/apptainer/.tmp
	mkdir -p $APPTAINER_CACHEDIR
	mkdir -p $APPTAINER_TMPDIR

	if [[ $1 == "mpi" ]]; then
		NETWORK_URI=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/network" -H "Metadata-Flavor: Google")
		NETWORK_NAME=$(basename $NETWORK_URI)
		ZONE_URI=$(curl "http://metadata.google.internal/computeMetadata/v1/instance/zone" -H "Metadata-Flavor: Google")
		ZONE=$(basename $ZONE_URI)
		REGION=$(echo $ZONE | sed 's/-.$//')
		SUBNET=$(gcloud compute networks subnets list --filter="network:$NETWORK_NAME" --regions=$REGION --format 'csv[no-heading](RANGE)')

		echo Subnet: $SUBNET

		export MPI_CLUSTER="true"
		export MPI_SHARE_PATH=$EXECUTER_TRACKER_DATA_DISK_DIR"/mpi"
		export MPI_HOSTFILE_PATH="/root/mpi_hosts"
		export MPI_EXTRA_ARGS="--allow-run-as-root --mca btl_tcp_if_include $SUBNET --mca oob_tcp_if_include $SUBNET"

		# Store Apptainer images in a shared directory so that every cluster
		# member can access them.
		export EXECUTER_IMAGES_DIR=$EXECUTER_TRACKER_DATA_DISK_DIR"/mpi/apptainer"
	fi

    $PYTHON_BIN $APP_PATH
}

start $@
