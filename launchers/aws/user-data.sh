#!/bin/bash

# Install Docker
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

echo "INDUCTIVA_API_KEY=eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2R0NNIn0.3Mf6aeVx5eayjz2Kz1SZknkjZ_IqvaF7ZrCLwhJubneffUXA2oBwQQ.7lsfsvJJltI7QQEXaTX7lA.2WBWLbOE0oRoUeIAdhDP9fPedCh4rl5Zpyd2AyxgTPcKGEnjUafSk_b2ohIb_Jz8GV0.CgPlGBrqh_BxNzbzEvoc7g" | sudo tee -a .env
echo "INDUCTIVA_API_URL=https://api.inductiva.ai" | sudo tee -a .env > /dev/null
echo "MACHINE_GROUP_NAME='09Nov2024H11M22'" | sudo tee -a .env > /dev/null
export $(grep -v ^# .env | xargs)

sudo make task-runner-up &