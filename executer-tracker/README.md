# Executer tracker

This directory contains the code related to the executer tracker, the
component responsible for managing the execution of requests using the
right request. The executer tracker reads from a Redis stream, launching
a subprocess to run the Python script that corresponds to the received
request.

## Building the Docker image

To build and launch a Docker container with this service, use the provided
[`Dockerfile`](Dockerfile). The provided Docker image is built on top of
an image that should be provided as a build argument.

First, build the base Docker image for a given executer. For instance, for the `math` executer, `cd` into  `executers/math` and run:
```shell
> docker build -t inductiva-executer-math-base .
```
Then, build the executer-tracker Docker image (from the `executer-tracker` directory), specifying the right executer as a base image:

```shell
> docker build -t inductiva-executer-math --build-arg BASE_IMAGE=inductiva-executer-math-base  .
```

Then, create a container (named e.g. `math`) from that image:

```shell
> docker run --network inductiva-web-api_api -v artifact-store:/mnt/  --env REDIS_HOSTNAME=redis-server --env REDIS_CONSUMER_NAME=consumer-name --name math inductiva-executer-math
```

Note that this container must have access to the network shared by the web API
and Redis server, which is named `inductiva-web-api_api` if you use the `docker-compose.yml` provided in the root of the repository to launch local API and Redis instances. The `-v` option in the `docker run` command specifies the name of the shared volume, so that both the API and the executers have access to a shared directory. The `REDIS_CONSUMER_NAME` environment variable specifies the name of the consumer when connecting to the Redis stream. Note that the name should be unique for all executer-trackers, so if you lanch multiple executer trackers, make sure to give each one a different name. The `REDIS_HOSTNAME` environment variable specifies the hostname where the Redis server is running. In the case where the provided `docker-compose.yml` is used, then the name is `redis-server` (which is the name of the launched container).
