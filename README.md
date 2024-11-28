# Task Runner
Task Runner allows you to run simulations locally via the Inductiva API.

## How to Run

### Pre-requisites

- Operating System: **Linux** -- MacOS should work, but might be slower building MPI dependencies. Windows was not yet tested.
- **docker** -- user should already have been added to the docker group, or have admin rights to do it
- **git** -- (optional) to clone this repository, alternatively download the zip file.
- **make** (optional) -- to launch the commands easily, alternatively run them explicitely on the terminal.
- **nvidia container toolkit** -- (optional) -- this is required only if you want to launch the TaskRunner with NVIDIA GPU support -- please follow the [official instructions](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) to install the libraries and then configure Docker.


Additionally you need:

- an **Inductiva API key**. (register at https://console.inductiva.ai)

### Setup Environment

Create a file named `.env` where you will store your Inductiva API key and the Inductiva API URL.
```
INDUCTIVA_API_KEY=xxxxxxxxxx
INDUCTIVA_API_URL=https://api.inductiva.ai
```
To specify a name for your machine group or to connect a task-runner to an already existing machine add the machine group name to your `.env` file

```
MACHINE_GROUP_NAME='my-machine-group-name'
```

### Build and Run the application
The application can be run in two different ways: the fully functional `Normal mode` that takes longer to build, or a lighter `Lite mode` that does not install openmpi.

#### Normal mode
Build and run the docker container:

```
make task-runner-up
```

#### Lite mode
Build and run a lighter version of the Task Runner

```
make task-runner-lite-up
```

NOTE: The simulators that use openmpi (eg. AmrWind, CaNs) can not be chosen to run simulations in Lite mode. 

#### With GPU access
Build and run the Task Runner with CUDA support:

```
make task-runner-cuda-up
```

### Run Simulations

You can now run simulations locally by passing a local machine when you call the `run` function. Try out the following example:

```py
import inductiva

input_dir = inductiva.utils.files.download_from_url(
    "https://storage.googleapis.com/inductiva-api-demo-files/"
    "gromacs-input-example.zip", True)

commands = [
    "gmx solvate -cs tip4p -box 2.3 -o conf.gro -p topol.top",
    ("gmx grompp -f energy_minimization.mdp -o min.tpr -pp min.top "
     "-po min.mdp -c conf.gro -p topol.top"),
    "gmx mdrun -s min.tpr -o min.trr -c min.gro -e min.edr -g min.log",
    ("gmx grompp -f positions_decorrelation.mdp -o decorr.tpr "
     "-pp decorr.top -po decorr.mdp -c min.gro"),
    ("gmx mdrun -s decorr.tpr -o decorr.trr -x  -c decorr.gro "
     "-e decorr.edr -g decorr.log"),
    ("gmx grompp -f simulation.mdp -o eql.tpr -pp eql.top "
     "-po eql.mdp -c decorr.gro"),
    ("gmx mdrun -s eql.tpr -o eql.trr -x trajectory.xtc -c eql.gro "
     "-e eql.edr -g eql.log")
]

machine = inductiva.resources.machine_groups.get_by_name('my-machine-group-name')

gromacs = inductiva.simulators.GROMACS()

task = gromacs.run(
    input_dir=input_dir,
    commands=commands,
    on=machine
)
task.wait()

task.download_outputs()
```
