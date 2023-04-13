# Executer tracker

This directory contains the code related to the executer tracker, the
component responsible for managing the execution of requests using the
right request. The executer tracker reads from a Redis stream, launching
a subprocess to run the Python script that corresponds to the received
request.

## Building the Docker image

Building a Docker image with this service requires building two Docker images.
The `executer-tracker` image, specified in the provided [Dockerfile](Dockerfile) is
built with an `executer` image as base image, *e.g.*, an image built with a Dockerfile
provided in the [executers](../executers/) directory.

To automate this building process, a [script](../scripts/build_executer_image.py) is provided.
The script can be used as follows (from the root of the repository):

```shell
python scripts/build_executer_image.py --name dualsph-executer --executer_path executers/sph/dualsphysics
```

In the command above, the flag `name` is used to specify the name of the resulting
Docker image, and `executer_path` to specify the path where the executer is defined
(*i.e.*, the path that contains the executer's `Dockerfile`).
Check the docstring at the top of the script for more information on how to use
the script, *e.g.*, how to pass additional flags to `docker build` command.

Then, create a container (named e.g. `dualsph`) from that image:

```shell
> docker run --gpus all --cpus="12" \
    --network inductiva-web-api_api \
    -v inductiva-web-api_artifact-store:/mnt/artifacts \
    --env ARTIFACT_STORE=/mnt/artifacts \
    --env REDIS_HOSTNAME=redis-server \
    --env REDIS_CONSUMER_NAME=consumer-name \
    --name dualsph \
    dualpsh-executer
```

Note that this container must have access to the network shared by the web API
and Redis server, which is named `inductiva-web-api_api` if you use the `docker-compose.yml` provided in the root of the repository to launch local API and Redis instances.
The container also needs access to a shared volume with the web API, named `inductiva-web-api_artifact-store` if the `docker-compose.yml` is used. The `-v` option in the `docker run` command is used to specify the shared volume. Additionally, the `ARTIFACT_STORE` should be set to the directory where the `inductiva-web-api_artifact-store` is mounted.
The `REDIS_CONSUMER_NAME` environment variable specifies the name of the consumer when connecting to the Redis stream. Note that the name should be unique for all executer-trackers, so if you lanch multiple executer trackers, make sure to give each one a different name. The `REDIS_HOSTNAME` environment variable specifies the hostname where the Redis server is running. In the case where the provided `docker-compose.yml` is used, then the name is `redis-server` (which is the name of the launched container).
The additional options `gpus` and `cpus` serve to allow access to specific resources to the Docker container. In this case, `gpus` is used because the DualSPHysics executers requires access to GPUs.
