"""Pre-processing tools for Gromacs MD simulations"""

import Bio.PDB as bio


class ChainAFilter:
    """Filter to extract only proteic chains from a PDB file.

    This class is an object used in the PDBIO.save() method to filter
    the atoms that will be saved in the new PDB file, with the mandatory
    methods: accept_chain, accept_model, accept_residue and
    accept_atom methods. In the bio.PDBIO().save() method, each of the
    elements that constitute the system will be checked for acceptance
    with the corresponding method. Each of these methods returns true
    for the sections that fulfill the requirement of being part of
    a protein. The accept_model method is not used in this case, since
    there are no specificities for protein models that separate it from
    other elements of the system. Nonetheless, it is included in the
    class to avoid errors in the PDBIO.save() method."""

    def accept_chain(self, chain):
        """Accept only chains with alphabetic IDs"""
        return chain.get_id().isalpha()

    def accept_model(self, model):  # pylint: disable=unused-argument
        """Accept any model"""
        return True

    def accept_residue(self, residue):
        """Accept only standard residues"""
        return residue.id[0] == " "

    def accept_atom(self, atom):
        """Accept only protein atoms"""
        return atom.full_id[0] == "protein"


def protein_solvation_pre_process(pdb_file):
    """Extracts protein chain from PDB file and overwrite the file
    
    Using Biopython PDB module, we load the entire system to a PDB
    structure object. Then, we use the PDBIO module to save the
    structure to the same PDB file, using the ChainAFilter class to
    filter the atoms that will be saved."""

    pdb_parser = bio.PDBParser(QUIET=True)
    pdb_structure = pdb_parser.get_structure("protein", pdb_file)

    io = bio.PDBIO()
    io.set_structure(pdb_structure)
    io.save(pdb_file, select=ChainAFilter())
