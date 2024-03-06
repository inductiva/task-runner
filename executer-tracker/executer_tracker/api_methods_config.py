"""Mapping of API methods to the Executer classes that perform those methods."""
from executer_tracker import executers

api_method_to_script = {
    "sph.splishsplash.run_simulation":
        executers.splishplash.SPlisHSPlasHExecuter,
    "sph.dualsphysics.run_simulation":
        executers.dualsphysics.DualSPHysicsExecuter,
    "sw.swash.run_simulation":
        executers.swash.SWASHExecuter,
    "sw.xbeach.run_simulation":
        executers.xbeach.XBeachExecuter,
    "fvm.openfoam_foundation.run_simulation":
        executers.openfoam.OpenFOAMExecuter,
    "fvm.openfoam_esi.run_simulation":
        executers.openfoam.OpenFOAMExecuter,
    "md.gromacs.run_simulation":
        executers.gromacs.GROMACS,
    "stellarators.simsopt.run_simulation":
        executers.simsopt.SimsoptExecuter,
    "fem.fenicsx.run_simulation":
        executers.fenicsx.LinearElasticityFEniCSxExecuter,
    "fdm.fds.run_simulation":
        executers.fds.FDSExecuter,
    "reef3d.reef3d.run_simulation":
        executers.reef3d.REEF3DExecuter,
    "tester.echo.run_simulation":
        executers.dummy.DummyExecuter,
    "swan.swan.run_simulation":
        executers.swan.SWANExecuter,
    "dummy.dummy.mpi_hello_world":
        executers.dummy.MPIHelloWorldExecuter,
    "schism.schism.run_simulation":
        executers.schism.SCHISMExecuter,
}
