# Task Runner
Task Runner allows you to run simulations locally via the Inductiva API.

## How to Run
The prerequisites for running the Task Runner are docker and a Inductiva account. 

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
The application is run by launching a docker container. The default Task Runner does not access the GPU, but a different container with CUDA support is also available.

#### Task Runner
Build and run the docker container:

```
make task-runner-up
```

#### Task Runner with GPU access
Build and run the Task Runner with CUDA support:

```
make task-runner-cuda-up
```

Please make sure you have the nvidia drivers installed. 

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

### For developers/contributors
The following are instructions that can help developers setup the development mode or create scenarios for testing features. 

#### Connect to local API
If you want connect to an API that is running locally in your `.env` file set the url as:

```
INDUCTIVA_API_URL=http://host.docker.internal:(api-port)
``` 

Replacing api-port with the port where the API is exposed. 

#### Lite mode
To implement and test features that do not require running MPI simulators it is possible to build and run a lighter version of the Task Runner that does not install openmpi by:

```
make task-runner-lite-up
```

NOTE: The simulators that use openmpi (eg. AmrWind, CaNs) can not be chosen to run simulations in Lite mode. 

#### Launching more than one Task Runner on the same machine
To launch more than one Task Runner associated to the same Machine Group, add argument `ID=` when calling make.
For example to launch 3 Task Runners connected to the same Machine Group do:
```
make task-runner-up
make ID=2 task-runner-up
make ID=3 task-runner-up
```
