# Executer tracker

This directory contains the code related to the executer tracker, the
component responsible for managing the execution of requests using the
right request. The executer tracker reads from a Redis stream, launching
a subprocess to run the Python script that corresponds to the received
request.

## Building the Docker image

Building a Docker image with this service requires building only one Docker image, it is 
the `executer` image, specified in the provided [Dockerfile](Dockerfile). This docker
image can be built with a following command:

```shell
docker build --name executer .
```

In the command above, the flag `name` is used to specify the name of the resulting
Docker image.

## Launching an executer container locally

After building the executer Docker image, named `executer` in this example, a container (named e.g. `exec-tracker`) can be created from that image:

```shell
> docker run --gpus all --cpus="12" \
 --name exec-tracker \
 --network inductiva-web-api_api \
 -v inductiva-web-api_artifact-store:/mnt/artifacts \
 -v /var/run/docker.sock:/var/run/docker.sock \
 -v /docker-images-config.json:/docker-images-config.json \ 
 --env EXECUTER_DOCKER_IMAGES_CONFIG=/docker-images-config.json \
 -v /exec-tracker:/working_dir \
 --env SHARED_DIR_HOST=/exec-tracker \
 --env SHARED_DIR_LOCAL=/working_dir 
 -v /gcloud/gcloud_key.json:/config/gcloud/gcloud_key.json \ 
 -env GOOGLE_APPLICATION_KEY=/config/gcloud/gcloud_key.json
 exec
```

This container must have access to the network shared by the web API
and Redis server, which is named `inductiva-web-api_api` if you use the `docker-compose.yml` provided in the root of the repository to launch local API and Redis instances.
The container also needs access to a shared volume with the web API, named `inductiva-web-api_artifact-store` if the `docker-compose.yml` is used. The `-v` option in the `docker run` command is used to specify the shared volume.
This container needs access to a local directory called `exec-tracker` where the outputs of the tasks will be stored. You might need to create this directory before launching the container.
There must be a JSON file called `docker-images-config.json` with the executer names and image names of the executers this container will run. Example if shown [here](https://github.com/inductiva/inductiva-web-api/blob/2711bdc96c701579fa4442016cd637725a7ae55a/executer-tracker/src/utils/config.py#L38).
To access and test Google Cloud resources within this container, the JSON file called `gcloud_key.json` with the GC credentials should exist in `/gcloud` directory.
The volume must be mounted to the `/mnt/artifacts` directory, as this is the directory from which the executer expects to access input/output files.
The additional options `gpus` and `cpus` serve to allow access to specific resources to the Docker container. In this case, `gpus` is used because the DualSPHysics executers requires access to GPUs.
Note that if you name the directory with the repository differently than `inductiva-web-api`, then you need to replace the prefix in the network and volume names with the directory name, since Docker Compose uses the directory name to prefix the containers/networks/volumes launched with a `docker-compose.yml` file.

To run the tasks in the API developed locally, define the api url and key as follows:
```
inductiva.api_url = "http://0.0.0.0:8000"
inductiva.api_key = "1234"
```
