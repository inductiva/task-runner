## Base image deps

OS: debian 11 (bullseye)

1. MPI

```
wget https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.6.tar.gz
sudo apt-get update && sudo apt-get install build-essential
tar zxvf openmpi-4.1.6.tar.gz
cd openmpi-4.1.6/
./configure --prefix=/usr/local
make all
sudo make install
which mpicc
which mpiexec
mpiexec --version
mpicc --version
sudo ldconfig
```

2. Apptainer

```
wget https://github.com/apptainer/apptainer/releases/download/v1.2.4/apptainer_1.2.4_amd64.deb
sudo apt install -y ./apptainer_1.2.4_amd64.deb
```


3. skopeo, jq

```
apt-get install skopeo jq
```

4. NFS server

```
apt-get install nfs-kernel-server
```

5. [Docker](https://docs.docker.com/engine/install/debian/#install-using-the-repository)

6. We also assume that there is a SSH key pair (`/root/.ssh/id_mpi_cluster` and `/root/.ssh/id_mpi_cluster.pub`) that is used to ssh between the machines when we launch multiple.

7. The base image also has a directory called `/export/mpi` that is exported with NFS.

File `/etc/exports`:

```
/export       10.0.0.0/8(rw,fsid=0,no_subtree_check,sync,no_root_squash)
/export/mpi   10.0.0.0/8(rw,nohide,insecure,no_subtree_check,sync,no_root_squash)
```

8. Python 3.9, `python3-venv`

```
sudo apt-get install python3-venv
```
