"""
Data structures for AdaptaHOP frontend.




"""

#-----------------------------------------------------------------------------
# Copyright (c) 2013, yt Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

import numpy as np
import stat
import os
import re

from yt.data_objects.data_containers import \
    YTSelectionContainer
from yt.data_objects.static_output import \
    Dataset
from yt.frontends.halo_catalog.data_structures import \
    HaloCatalogFile, HaloCatalogParticleIndex
from yt.funcs import \
    setdefaultattr
from yt.geometry.particle_geometry_handler import \
    ParticleIndex
from yt.utilities.cython_fortran_utils import FortranFile
from yt.units import Mpc

from .definitions import \
    HEADER_ATTRIBUTES
from .fields import \
    AdaptaHOPFieldInfo



class AdaptaHOPDataset(Dataset):
    _index_class = HaloCatalogParticleIndex
    _file_class = HaloCatalogFile
    _field_info_class = AdaptaHOPFieldInfo

    # AdaptaHOP internally assumes 1Mpc == 3.0824cm
    _code_length_to_Mpc = (1.0 * Mpc).to('cm').value / 3.08e24

    def __init__(self, filename, dataset_type="adaptahop_binary",
                 n_ref = 16, over_refine_factor = 1,
                 units_override=None, unit_system="cgs",
                 parent_ds=None
                 ):
        self.n_ref = n_ref
        self.over_refine_factor = over_refine_factor
        if parent_ds is None:
            raise RuntimeError('The AdaptaHOP frontend requires a parent dataset to be passed as `parent_ds`.')
        self.parent_ds = parent_ds

        super(AdaptaHOPDataset, self).__init__(filename, dataset_type,
                                              units_override=units_override,
                                              unit_system=unit_system)

    def _set_code_unit_attributes(self):
        setdefaultattr(self, 'length_unit', self.quan(self._code_length_to_Mpc, "Mpc"))
        setdefaultattr(self, 'mass_unit', self.quan(1e11, "Msun"))
        setdefaultattr(self, 'velocity_unit', self.quan(1.0, "km / s"))
        setdefaultattr(self, 'time_unit', self.length_unit / self.velocity_unit)

    def _parse_parameter_file(self):
        with FortranFile(self.parameter_filename) as fpu:
            params = fpu.read_attrs(HEADER_ATTRIBUTES)
        self.dimensionality = 3
        self.unique_identifier = \
            int(os.stat(self.parameter_filename)[stat.ST_CTIME])
        # Domain related things
        self.filename_template = self.parameter_filename
        self.file_count = 1
        nz = 1 << self.over_refine_factor
        self.domain_dimensions = np.ones(3, "int32") * nz

        # Set things up
        self.cosmological_simulation = 1
        self.current_redshift = (1.0 / params['aexp']) - 1.0
        self.omega_matter = params['omega_t']
        self.current_time = self.quan(params['age'], 'Gyr')
        self.omega_lambda = 0.724  # hard coded if not inferred from parent ds
        self.hubble_constant = 0.7  # hard coded if not inferred from parent ds
        self.periodicity = (True, True, True)
        self.particle_types = ("halos")
        self.particle_types_raw = ("halos")

        # Inherit stuff from parent ds -- if they exist
        for k in ('omega_lambda', 'hubble_constant', 'omega_matter', 'omega_radiation'):
            v = getattr(self.parent_ds, k, None)
            if v is not None:
                setattr(self, k, v)

        self.domain_left_edge = np.array([0., 0., 0.])
        self.domain_right_edge = self.parent_ds.domain_right_edge.to('Mpc').value * \
            self._code_length_to_Mpc

        self.parameters.update(params)

    @classmethod
    def _is_valid(self, *args, **kwargs):
        fname = os.path.split(args[0])[1]
        if not fname.startswith('tree_bricks') or not re.match('^tree_bricks\d{3}$', fname):
            return False
        return True

    def halo(self, halo_id, ptype='DM'):
        """
        Create a data container to get member particles and individual
        values from halos. Halo mass, position, and velocity are set as attributes.
        Halo IDs are accessible through the field, "member_ids".  Other fields that
        are one value per halo are accessible as normal.  The field list for
        halo objects can be seen in `ds.halos_field_list`.

        Parameters
        ----------
        halo_id : int
            The id of the halo or group
        ptype : str, default DM
            The type of particles the halo is made of.
        """
        return AdaptaHOPHaloContainer(
            ptype, halo_id, parent_ds=self.parent_ds, halo_ds=self)

class AdaptaHOPHaloContainer(YTSelectionContainer):
    """
    Create a data container to get member particles and individual
    values from halos. Halo mass, position, and velocity are set as attributes.
    Halo IDs are accessible through the field, "member_ids".  Other fields that
    are one value per halo are accessible as normal.  The field list for
    halo objects can be seen in `ds.halos_field_list`.

    Parameters
    ----------
    ptype : string
        The type of halo, either "Group" for the main halo or
        "Subhalo" for subhalos.
    particle_identifier : int or tuple of ints
        The halo or subhalo id.  If requesting a subhalo, the id
        can also be given as a tuple of the main halo id and
        subgroup id, such as (1, 4) for subgroup 4 of halo 1.

    Attributes
    ----------
    particle_identifier : int
        The id of the halo or subhalo.
    group_identifier : int
        For subhalos, the id of the enclosing halo.
    subgroup_identifier : int
        For subhalos, the relative id of the subhalo within
        the enclosing halo.
    particle_number : int
        Number of particles in the halo.
    mass : float
        Halo mass.
    position : array of floats
        Halo position.
    velocity : array of floats
        Halo velocity.

    Note
    ----
    Relevant Fields:

     * particle_number - number of particles
     * subhalo_number - number of subhalos
     * group_identifier - id of parent group for subhalos

    Examples
    --------

    >>> import yt
    >>> ds = yt.load('output_00080_halos/tree_bricks080', parent_ds=yt.load('output_00080/info_00080.txt'))
    >>>
    >>> ds.halo(1, ptype='io')
    >>> print(halo.mass)
    119.22804260253906 100000000000.0*Msun
    >>> print(halo.position)
    [26.80901299 24.35978484  5.45388672] code_length
    >>> print(halo.velocity)
    [3306394.95849609 8584366.60766602 9982682.80029297] cm/s
    >>> print(halo["io", "particle_mass"])
    [3.19273578e-06 3.19273578e-06 ... 3.19273578e-06 3.19273578e-06] code_mass
    >>>
    >>> # particle ids for this halo
    >>> print(halo.member_ids)
    [     48      64     176 ... 999947 1005471 1006779]
    >>>
    """

    _type_name = "halo"
    _con_args = ("ptype", "particle_identifier", "parent_ds", "halo_ds")
    _spatial = False
    # Do not register it to prevent .halo from being attached to all datasets
    _skip_add = True

    def __init__(self, ptype, particle_identifier, parent_ds, halo_ds):
        if ptype not in parent_ds.particle_types_raw:
            raise RuntimeError("Possible halo types are %s, supplied \"%s\"." %
                               (parent_ds.particle_types_raw, ptype))

        # Setup required fields
        self._dimensionality = 3
        self.ds = parent_ds

        # Halo-specific 
        self.halo_ds = halo_ds
        self.ptype = ptype
        self.particle_identifier = particle_identifier

        # Set halo particles data
        self._set_halo_properties()
        self._set_halo_member_data()

        # Call constructor
        super(AdaptaHOPHaloContainer, self).__init__(
            parent_ds, {})


    def __repr__(self):
        return "%s_%s_%09d" % \
          (self.ds, self.ptype, self.particle_identifier)

    
    def __getitem__(self, key):
        return self.region[key]

    @property
    def ihalo(self):
        """The index in the catalog of the halo"""
        ihalo = getattr(self, '_ihalo', None)
        if ihalo:
            return ihalo
        else:
            halo_id = self.particle_identifier
            halo_ids = self.halo_ds.r['halos', 'particle_identifier'].astype(int)
            ihalo = np.searchsorted(halo_ids, halo_id)
            
            assert halo_ids[ihalo] == halo_id

            self._ihalo = ihalo
            return self._ihalo
        

    def _set_halo_member_data(self):
        ptype = self.ptype
        halo_ds = self.halo_ds
        parent_ds = self.ds
        ihalo = self.ihalo

        # Note: convert to physical units to prevent errors when jumping
        # from halo_ds to parent_ds
        halo_pos = halo_ds.r['halos', 'particle_position'][ihalo, :].to('Mpc').value
        halo_vel = halo_ds.r['halos', 'particle_velocity'][ihalo, :].to('km/s').value
        halo_radius = halo_ds.r['halos', 'r'][ihalo].to('Mpc').value

        members = self.member_ids
        ok = False
        f = 1/1.1
        center = parent_ds.arr(halo_pos, 'Mpc')
        radius = parent_ds.arr(halo_radius, 'Mpc')
        # Find smallest sphere containing all particles
        while not ok:
            f *= 1.1
            sph = parent_ds.sphere(
                center,
                f*radius)

            part_ids = sph[ptype, 'particle_identity'].astype(int)

            ok = len(np.lib.arraysetops.setdiff1d(members, part_ids)) == 0

        # Set bulk velocity
        sph.set_field_parameter('bulk_velocity', (halo_vel, 'km/s'))

        # Build subregion that only contains halo particles
        reg = sph.cut_region(
            ['np.in1d(obj["io", "particle_identity"].astype(int), members)'],
            locals=dict(members=members, np=np))

        self.sphere = sph
        self.region = reg

    def _set_halo_properties(self):
        ihalo = self.ihalo
        ds = self.halo_ds
        # Add position, mass, velocity member functions
        for attr_name in ('mass', 'position', 'velocity'):
            setattr(self, attr_name, ds.r['halos', 'particle_%s' % attr_name][ihalo])
        # Add members
        self.member_ids = self.halo_ds.index.io.members(ihalo).astype(np.int64)
