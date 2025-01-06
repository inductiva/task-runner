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

sudo apt install -y git-all

sudo apt install make

cd /home/ubuntu
git clone https://github.com/inductiva/task-runner.git
cd task-runner

echo "INDUCTIVA_API_URL=https://api.inductiva.ai" | sudo tee -a .env > /dev/null

echo "INDUCTIVA_API_KEY='eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2R0NNIn0.4UwkIEog-BD_gAUgiC2xJfHzZ3nllIA2wnmKzKnELOO70ftFRr447g.LXbJWKthD9Vup4V8XK0l_Q.CBliZCG9sfmRvlZysRu9sapQCAniwgTIvvx5qzvmyNFUpaEFDeAhpvL8luHMDvgx9JI.xH-YDY2qilGp4lxMe-NldA'" | sudo tee -a .env > /dev/null
echo "MACHINE_GROUP_NAME='06_01_2025_17_19'" | sudo tee -a .env > /dev/null
export $(grep -v ^# .env | xargs)

make task-runner-lite-up &
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
sudo apt install unzip
unzip awscliv2.zip
sudo ./aws/install

echo '#!/bin/bash
export INSTANCE_ID=$(ec2metadata --instance-id)
aws ec2 terminate-instances --instance-ids $INSTANCE_ID' > terminate_vm.sh
chmod +x terminate_vm.sh