#!/bin/bash

# Installing Docker

sudo apt-get update -y
sudo apt-get install -y ca-certificates curl 
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

#Running task-runner docker container

docker run -d --name file-tracker --env USER_API_KEY=a --volume workdir:/workdir --network host inductiva/file-tracker:main

docker run -d --name task-runner --env USER_API_KEY=a --env MACHINE_GROUP_NAME=a --env HOST_NAME=$(hostname) --volume ./apptainer:/executer-images --volume workdir:/workdir --network host --privileged --platform linux/amd64 inductiva/task-runner:main

# Install AWS CLI

curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
sudo apt install unzip
unzip awscliv2.zip
sudo ./aws/install

# Script that allows the VM to delete itself

echo '#!/bin/bash
export INSTANCE_ID=$(ec2metadata --instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID' > terminate_vm.sh
chmod +x terminate_vm.sh