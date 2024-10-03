"""Mapping of API methods to the Executer classes that perform those methods."""
from typing import Optional, Type

from task_runner import executers

api_method_to_executer = {
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
    "openfast.openfast.run_simulation":
        executers.openfast.OpenFASTExecuter,
    "cans.cans.run_simulation":
        executers.cans.CaNSExecuter,
    "amrWind.amrWind.run_simulation":
        executers.amrWind.AmrWindExecuter,
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
    "compchem.nwchem.run_simulation":
        executers.nwchem.NWChemExecuter,
    "fvcom.fvcom.run_simulation":
        executers.fvcom.FVCOMExecuter,
    "arbitrary.arbitrary_commands.run_simulation":
        executers.arbitrary_commands_executer.ArbitraryCommandsExecuter,
}


def get_executer(api_method: str) -> Optional[Type[executers.BaseExecuter]]:
    """Get the Executer class for the given API method.

    Args:
        api_method: The API method to get the Executer class for.

    Returns:
        The Executer class that performs the given API method.
    """
    return api_method_to_executer.get(api_method)