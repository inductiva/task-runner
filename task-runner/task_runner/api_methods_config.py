"""Mapping of API simulators to the Executer classes that perform those simulations."""
from typing import Optional, Type

from task_runner import executers

simulator_to_executer = {
    "splishsplash":
        executers.splishplash.SPlisHSPlasHExecuter,
    "dualsphysics":
        executers.dualsphysics.DualSPHysicsExecuter,
    "swash":
        executers.swash.SWASHExecuter,
    "xbeach":
        executers.xbeach.XBeachExecuter,
    "openfoam_foundation":
        executers.openfoam.OpenFOAMExecuter,
    "openfoam_esi":
        executers.openfoam.OpenFOAMExecuter,
    "openfast":
        executers.openfast.OpenFASTExecuter,
    "cans":
        executers.cans.CaNSExecuter,
    "amrWind":
        executers.amrWind.AmrWindExecuter,
    "gromacs":
        executers.gromacs.GROMACS,
    "simsopt":
        executers.simsopt.SimsoptExecuter,
    "fenicsx":
        executers.fenicsx.LinearElasticityFEniCSxExecuter,
    "fds":
        executers.fds.FDSExecuter,
    "reef3d":
        executers.reef3d.REEF3DExecuter,
    "swan":
        executers.swan.SWANExecuter,
    "schism":
        executers.schism.SCHISMExecuter,
    "nwchem":
        executers.nwchem.NWChemExecuter,
    "fvcom":
        executers.fvcom.FVCOMExecuter,
    "arbitrary_commands":
        executers.arbitrary_commands_executer.ArbitraryCommandsExecuter,
    "quantumespresso":
        executers.quantumespresso.QuantumEspressoExecuter,
}


def get_executer(simulator: str) -> Optional[Type[executers.BaseExecuter]]:
    """Get the Executer class for the given API method.

    Args:
        api_method: The API method to get the Executer class for.

    Returns:
        The Executer class that performs the given API method.
    """
    return simulator_to_executer.get(simulator)
