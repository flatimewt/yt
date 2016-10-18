"""
This is a particle container that provides no indexing information.




"""

#-----------------------------------------------------------------------------
# Copyright (c) 2013, yt Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

import numpy as np

from yt.data_objects.data_containers import \
    YTFieldData, \
    YTDataContainer, \
    YTSelectionContainer
from yt.funcs import *
from yt.utilities.exceptions import \
    YTNonIndexedDataContainer
from yt.data_objects.octree_subset import ParticleOctreeSubset

# def _octree_indexed(self, *args, 

def _non_indexed(name):
    def _func_non_indexed(self, *args, **kwargs):
        if getattr(self, '_temp_spatial', False):
            return getattr(self.octree, name)(*args, **kwargs)
        else:
            raise YTNonIndexedDataContainer(self)
    return _func_non_indexed

class ParticleContainer(YTSelectionContainer):
    _spatial = False
    _type_name = 'particle_container'
    _skip_add = True
    _con_args = ('base_region', 'data_files', 'overlap_files', 'selector_mask')

    def __init__(self, base_region, data_files, overlap_files = [], 
                 selector_mask = None):
        self.field_data = YTFieldData()
        self.field_parameters = {}
        self.data_files = ensure_list(data_files)
        self.overlap_files = ensure_list(overlap_files)
        self.selector_mask = selector_mask
        self.ds = self.data_files[0].ds
        self._last_mask = None
        self._last_selector_id = None
        self._current_particle_type = 'all'
        # self._current_fluid_type = self.ds.default_fluid_type
        if hasattr(base_region, "base_selector"):
            self.base_selector = base_region.base_selector
            self.base_region = base_region.base_region
        else:
            self.base_region = base_region
            self.base_selector = base_region.selector
        self._octree = None
        self._temp_spatial = False
        if isinstance(base_region, ParticleContainer):
            self._temp_spatial = base_region._temp_spatial
            self._octree = base_region._octree
        elif isinstance(base_region, ParticleOctreeSubset):
            self._temp_spatial = True
            self._octree = base_region

    def __getattr__(self, *args, **kwargs):
        if self._temp_spatial:
            return getattr(self.octree, *args, **kwargs)
        else:
            raise AttributeError

    def __getitem__(self, key):
        if self._temp_spatial:
            return self.octree[key]
        else:
            return super(ParticleContainer, self).__getitem__(key)

    @property
    def selector(self):
        if self._temp_spatial:
            return self.octree.selector
        else:
            raise YTDataSelectorNotImplemented(self.oc_type_name)

    def select_particles(self, selector, x, y, z):
        mask = selector.select_points(x,y,z)
        return mask

    @contextlib.contextmanager
    def _as_spatial(self):
        self._temp_spatial = True
        yield self
        self._tmep_spatial = False

    @contextlib.contextmanager
    def _expand_data_files(self):
        old_data_files = self.data_files
        old_overlap_files = self.overlap_files
        self.data_files = list(set(self.data_files + self.overlap_files))
        self.data_files.sort()
        self.overlap_files = []
        with self.octree._expand_data_files():
            yield self
        self.data_files = old_data_files
        self.overlap_files = old_overlap_files

    @property
    def octree(self):
        # Cache octree so it is not constructed every time
        if self._octree is None:
            self._octree = ParticleOctreeSubset(
                self.base_region, self.data_files,
                overlap_files = self.overlap_files,
                selector_mask = self.selector_mask,
                over_refine_factor = self.ds.over_refine_factor)
        return self._octree

    def retrieve_ghost_zones(self, ngz, coarse_ghosts = False):
        gz_oct = self.octree.retrieve_ghost_zones(ngz, coarse_ghosts = coarse_ghosts)
        gz = ParticleContainer(gz_oct.base_region, gz_oct.data_files,
                               overlap_files = gz_oct.overlap_files,
                               selector_mask = gz_oct.selector_mask)
        gz._octree = gz_oct
        return gz

    select_blocks = _non_indexed('select_blocks')
    deposit = _non_indexed('deposit')
    smooth = _non_indexed('smooth')
    select_icoords = _non_indexed('select_icoords')
    select_fcoords = _non_indexed('select_fcoords')
    select_fwidth = _non_indexed('select_fwidth')
    select_ires = _non_indexed('select_ires')
    select = _non_indexed('select')
    count = _non_indexed('count')
    count_particles = _non_indexed('count_particles')
