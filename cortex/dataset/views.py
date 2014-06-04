import json

import h5py
import numpy as np

from .. import options
from . import BrainData, VolumeData, VertexData

default_cmap = options.config.get("basic", "default_cmap")

def normalize(data):
    if isinstance(data, tuple):
        if len(data) == 3:
            if data[0].dtype == np.uint8:
                return VolumeRGB(data[0][...,0], data[0][...,1], data[0][...,2], *data[1:])
            return Volume(*data)
        elif len(data) == 2:
            return Vertex(*data)
        else:
            raise TypeError("Invalid input for Dataview")
    elif isinstance(data, Dataview):
        return data
    else:
        raise TypeError("Invalid input for Dataview")

def _from_hdf_data(h5, name, xfmname=None, **kwargs):
    """Decodes a __hash named node from an HDF file into the 
    constituent Vertex or Volume object"""
    try:
        dnode = h5.get("/data/%s"%name)
    except KeyError:
        dnode = h5.get(name)

    subj = dnode.attrs['subject']
    if xfmname is not None:
        mask = None
        if "mask" in dnode.attrs:
            try:
                db.get_mask(subj, xfmname, dnode.attrs['mask'])
                mask = dnode.attrs['mask']
            except IOError:
                mask = dataset.get_mask(subj, xfmname, dnode.attrs['mask'])
        return Volume(dnode, subj, xfmname, mask=mask, **kwargs)
    else:
        return Vertex(dnode, subj, **kwargs)

def _from_hdf_view(data, **kwargs):
    if len(data) == 1:
        return _from_hdf_data(node.file, data[0], **kwargs)
    elif len(data) == 2:
        dim1 = _from_hdf_data(node.file, data[0], xfmname=xfmname[0])
        dim2 = _from_hdf_data(node.file, data[1], xfmname=xfmname[1])
        cls = Vertex2D if isinstance(dim1, Vertex) else Volume2D
        return Volume2D(dim1, dim2, **kwargs)
    elif len(data) == 4:
        red, green, blue = [_from_hdf_data(node.file, d, xfmname=xfmname) for d in data[:3]]
        alpha = None 
        if data[3] is not None:
            alpha = _from_hdf_data(node.file, data[3], xfmname=xfmname)

        cls = VertexRGB if isinstance(red, Vertex) else VolumeRGB
        return cls(red, green, blue, alpha=alpha, description=desc, cmap=cmap,
            vmin=vmin[0], vmin2=vmin[1], vmax=vmax[0], vmax2=vmax[1], state=state, **attrs)
    else:
        raise ValueError("Invalid Dataview specification")

class Dataview(object):
    def __init__(self, cmap=None, vmin=None, vmax=None, description="", state=None, **kwargs):
        if self.__class__ == Dataview:
            raise TypeError('Cannot directly instantiate Dataview objects')

        self.cmap = cmap if cmap is not None else default_cmap
        self.vmin = vmin
        self.vmax = vmax
        self.state = state
        self.attrs = kwargs
        if 'priority' not in self.attrs:
            self.attrs['priority'] = 1
        self.description = description

    def copy(self, *args):
        return self.__class__(*args, 
            cmap=self.cmap, 
            vmin=self.vmin, 
            vmax=self.vmax, 
            description=self.description, 
            state=self.state, 
            **self.attrs)

    @property
    def priority(self):
        return self.attrs['priority']

    @priority.setter
    def priority(self, value):
        self.attrs['priority'] = value

    def to_json(self):
        return dict(
            cmap=self.cmap, 
            vmin=self.vmin, 
            vmax=self.vmax, 
            state=self.state, 
            attrs=self.attrs, 
            desc=self.description)

    def __iter__(self):
        if isinstance(self.data, BrainData):
            yield self.data
        else:
            for data in self.data:
                if isinstance(data, BrainData):
                    yield data
                else:
                    for d in data:
                        yield d

    @staticmethod
    def from_hdf(node):
        data = json.loads(node[0])
        desc, cmap = node[1:3]
        vmin = json.loads(node[3])
        vmax = json.loads(node[4])
        state = json.loads(node[5])
        attrs = json.loads(node[6])
        try:
            xfmname = json.loads(node[7])
        except ValueError:
            xfmname = 

        if len(data) == 1:
            data = data[0]
            if len(data) == 1:
                return _from_hdf_data(node.file, data[0], xfmname=xfmname, description=desc, cmap=cmap,
                    vmin=vmin, vmax=vmax, state=state, **attrs)
            elif len(data) == 2:
                dim1 = _from_hdf_data(node.file, data[0], xfmname=xfmname[0])
                dim2 = _from_hdf_data(node.file, data[1], xfmname=xfmname[1])
                cls = Vertex2D if isinstance(dim1, Vertex) else Volume2D
                return Volume2D(dim1, dim2, description=desc, cmap=cmap, vmin=vmin, vmax=vmax, 
                    state=state, **attrs)
            elif len(data) == 4:
                red, green, blue = [_from_hdf_data(node.file, d, xfmname=xfmname) for d in data[:3]]
                alpha = None 
                if data[3] is not None:
                    alpha = _from_hdf_data(node.file, data[3], xfmname=xfmname)

                cls = VertexRGB if isinstance(red, Vertex) else VolumeRGB
                return cls(red, green, blue, alpha=alpha, description=desc, cmap=cmap,
                    vmin=vmin[0], vmin2=vmin[1], vmax=vmax[0], vmax2=vmax[1], state=state, **attrs)
            else:
                raise ValueError("Invalid Dataview specification")
        else:
            view = [for name in data]


    def _write_hdf(self, h5, name="data", data=None, xfmname=None):
        views = h5.require_group("/views")
        view = views.require_dataset(name, (8,), h5py.special_dtype(vlen=str))
        view[0] = json.dumps(data)
        view[1] = self.description
        try:
            view[2] = self.cmap
            view[3] = json.dumps(self.vmin)
            view[4] = json.dumps(self.vmax)
        except AttributeError:
            #For VolumeRGB/Vertex, there is no cmap/vmin/vmax
            pass
        view[5] = json.dumps(self.state)
        view[6] = json.dumps(self.attrs)
        view[7] = json.dumps(xfmname)
        return view

class Multiview(Dataview):
    def __init__(self, views, description=""):
        for view in views:
            if not isinstance(view, Dataview):
                raise TypeError("Must be a View object!")
        raise NotImplementedError

class Volume(VolumeData, Dataview):
    def __init__(self, data, subject, xfmname, mask=None, 
        cmap=None, vmin=None, vmax=None, description="", **kwargs):
        super(Volume, self).__init__(data, subject, xfmname, mask=mask, 
            cmap=cmap, vmin=vmin, vmax=vmax, description=description, **kwargs)

    def _write_hdf(self, h5, name="data"):
        datanode = VolumeData._write_hdf(self, h5)
        viewnode = Dataview._write_hdf(self, h5, name=name,
            data=[[self.name]], xfmname=self.xfmname)
        return viewnode

class Vertex(VertexData, Dataview):
    def __init__(self, data, subject, cmap=None, vmin=None, vmax=None, description="", **kwargs):
        super(Vertex, self).__init__(data, subject, cmap=cmap, vmin=vmin, vmax=vmax, 
            description=description, **kwargs)

    def _write_hdf(self, h5, name="data"):
        datanode = VolumeData._write_hdf(self, h5)
        viewnode = Dataview._write_hdf(self, h5, name=name, data=[[self.name]])
        return viewnode

class VolumeRGB(Dataview):
    def __init__(self, red, green, blue, subject=None, xfmname=None, alpha=None, description="", 
        state=None, **kwargs):
        if isinstance(red, VolumeData):
            if not isinstance(green, VolumeData) or red.subject != green.subject:
                raise TypeError("Invalid data for green channel")
            if not isinstance(blue, VolumeData) or red.subject != blue.subject:
                raise TypeError("Invalid data for blue channel")
            self.red = red
            self.green = green
            self.blue = blue
        else:
            if subject is None or xfmname is None:
                raise TypeError("Subject and xfmname are required")
            self.red = Volume(red, subject, xfmname)
            self.green = Volume(green, subject, xfmname)
            self.blue = Volume(blue, subject, xfmname)

        self.alpha = alpha
        self.description = description
        self.state = state
        self.attrs = kwargs
        if 'priority' not in self.attrs:
            self.attrs['priority'] = 1

    @property
    def volume(self):
        if self.alpha is None:
            alpha = np.ones_like(self.red.volume)
        if not isinstance(self.alpha, Volume):
            alpha = Volume(alpha, self.red.subject, self.red.xfmname)

        volume = []
        for dv in (self.red, self.green, self.blue, alpha):
            vol = dv.volume
            if vol.dtype != np.uint8:
                if dv.vmin is None:
                    if vol.min() < 0:
                        vol -= vol.min()
                else:
                    vol -= dv.vmin()

                if dv.vmax is None:
                    if vol.max() > 1:
                        vol /= vol.max()
                else:
                    vol /= dv.vmax
                vol = (vol * 255).astype(np.uint8)
            volume.append(vol)

        return np.array(volume).transpose([1, 2, 3, 4, 0])

    def _write_hdf(self, h5, name="data"):
        VolumeData._write_hdf(self.red, h5)
        VolumeData._write_hdf(self.green, h5)
        VolumeData._write_hdf(self.blue, h5)

        alpha = None
        if self.alpha is not None:
            VolumeData._write_hdf(self.alpha, h5)
            alpha = self.alpha.name

        data = [[self.red.name, self.green.name, self.blue.name, alpha]]
        viewnode = Dataview._write_hdf(self, h5, name=name, 
            data=data, xfmname=self.red.xfmname)
        return viewnode

    def __repr__(self):
        return "<RGB volumetric data for (%s, %s)>"%(self.red.subject, self.red.xfmname)

    def __hash__(self):
        return hash(_hash(self.volume))

class VertexRGB(Dataview):
    def __init__(self, red, green, blue, subject=None, alpha=None, description=""):
        if isinstance(red, VertexData):
            if not isinstance(green, VertexData) or red.subject != green.subject:
                raise TypeError("Invalid data for green channel")
            if not isinstance(blue, VertexData) or red.subject != blue.subject:
                raise TypeError("Invalid data for blue channel")
            self.red = red
            self.green = green
            self.blue = blue
        else:
            if subject is None:
                raise TypeError("Subject name is required")
            self.red = Vertex(red, subject)
            self.green = Vertex(green, subject)
            self.blue = Vertex(blue, subject)

        self.alpha = alpha
        self.description = description

    @property
    def vertices(self):
        if self.alpha is None:
            alpha = np.ones_like(red)
        if not isinstance(self.alpha, Vertex):
            alpha = Vertex(self.alpha, self.subject)

        verts = []
        for dv in (self.red, self.green, self.blue, alpha):
            vert = dv.vertices
            if vert.dtype != np.uint8:
                if vert.min() < 0:
                    vert -= vert.min()
                if vert.max() > 1:
                    vert /= vert.max()
                vert = (vert * 255).astype(np.uint8)
            verts.append(vert)

        return np.array(verts).transpose([1, 2, 0])

    def _write_hdf(self, h5, name="data"):
        VertexData._write_hdf(self.red, h5)
        VertexData._write_hdf(self.green, h5)
        VertexData._write_hdf(self.blue, h5)

        alpha = None
        if self.alpha is not None:
            VertexData._write_hdf(self.alpha, h5)
            alpha = self.alpha.name

        data = [self.red.name, self.green.name, self.blue.name, alpha]
        viewnode = Dataview._write_hdf(self, h5, name=name, 
            data=data)
        return viewnode

    def __repr__(self):
        return "<RGB vertex data for (%s)>"%(self.subject)

    def __hash__(self):
        return hash(_hash(self.vertices))

class Volume2D(Dataview):
    def __init__(self, dim1, dim2, subject=None, xfmname=None, description="", cmap=None,
        vmin=None, vmax=None, vmin2=None, vmax2=None, **kwargs):
        if isinstance(dim1, VolumeData):
            if subject is not None or xfmname is not None:
                raise TypeError("Subject and xfmname cannot be specified with Volumes")
            if not isinstance(dim2, VolumeData) or dim2.subject != dim1.subject:
                raise TypeError("Invalid data for second dimension")
            self.dim1 = dim1
            self.dim2 = dim2
            vmin, vmin2 = dim1.vmin, dim2.vmin
            vmax, vmax2 = dim1.vmax, dim2.vmax
        else:
            self.dim1 = Volume(dim1, subject, xfmname)
            self.dim2 = Volume(dim2, subject, xfmname)

        self.vmin2 = vmin2 if vmin2 is not None else vmin
        self.vmax2 = vmax2 if vmax2 is not None else vmax

        super(Volume2D, self).__init__(description=description, cmap=cmap, vmin=vmin, vmax=vmax, **kwargs)
        self.attrs['xfmnames'] = [self.dim1.xfmname, self.dim2.xfmname]

    def _write_hdf(self, h5, name="data"):
        VolumeData._write_hdf(self.dim1, h5)
        VolumeData._write_hdf(self.dim2, h5)

        viewnode = Dataview._write_hdf(self, h5, name=name)
        viewnode[0] = json.dumps([self.dim1.name, self.dim2.name])
        viewnode[3] = json.dumps([float(self.vmin), float(self.vmin2)])
        viewnode[4] = json.dumps([float(self.vmax), float(self.vmax2)])
        return viewnode

    def __repr__(self):
        return "<2D volumetric data for (%s, %s)>"%(self.dim1.subject, self.dim1.xfmname)

class Vertex2D(Dataview):
    def __init__(self, dim1, dim2, subject=None, description="", cmap=None,
        vmin=None, vmax=None, vmin2=None, vmax2=None, **kwargs):
        if isinstance(dim1, VertexData):
            if subject is not None:
                raise TypeError("Subject cannot be specified with Volumes")
            if not isinstance(dim2, VertexData) or dim2.subject != dim1.subject:
                raise TypeError("Invalid data for second dimension")
            self.dim1 = dim1
            self.dim2 = dim2
            vmin, vmin2 = dim1.vmin, dim2.vmin
            vmax, vmax2 = dim1.vmax, dim2.vmax
        else:
            self.dim1 = Vertex(dim1, subject)
            self.dim2 = Vertex(dim2, subject)

        self.vmin2 = vmin2 if vmin2 is not None else vmin
        self.vmax2 = vmax2 if vmax2 is not None else vmax
        super(Vertex2D, self).__init__(description=description, cmap=cmap, vmin=vmin, vmax=vmax, **kwargs)

    def _write_hdf(self, h5, name="data"):
        VertexData._write_hdf(self.dim1, h5)
        VertexData._write_hdf(self.dim2, h5)

        viewnode = Dataview._write_hdf(self, h5, name=name)
        viewnode[0] = json.dumps([self.dim1.name, self.dim2.name])
        viewnode[3] = json.dumps([float(self.vmin), float(self.vmin2)])
        viewnode[4] = json.dumps([float(self.vmax), float(self.vmax2)])
        return viewnode

    def __repr__(self):
        return "<2D vertex data for (%s)>"%self.dim1.subject