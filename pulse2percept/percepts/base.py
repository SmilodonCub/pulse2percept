import numpy as np
from sys import platform
import matplotlib as mpl
if platform == "darwin":  # OS X
    mpl.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.axes import Subplot
from matplotlib.animation import FuncAnimation

import imageio
import logging
from skimage.transform import resize

from ..utils import Data, Grid2D


class Percept(Data):
    """Visual percept

    .. versionadded:: 0.6

    Parameters
    ----------
    data : 3D NumPy array
        A NumPy array specifying the percept in (Y, X, T) dimensions
    space : :py:class:`~pulse2percept.utils.Grid2D`
        A grid object specifying the (x,y) coordinates in space
    time : 1D array
        A list of time points
    metadata : dict, optional, default: None
        Additional stimulus metadata can be stored in a dictionary.

    """

    def __init__(self, data, space=None, time=None, metadata=None):
        xdva = None
        ydva = None
        if space is not None:
            if not isinstance(space, Grid2D):
                raise TypeError("'space' must be a Grid2D object, not "
                                "%s." % type(space))
            xdva = space._xflat
            ydva = space._yflat
        if time is not None:
            time = np.array([time]).flatten()
        self._internal = {
            'data': data,
            'axes': [('ydva', ydva), ('xdva', xdva), ('time', time)],
            'metadata': metadata
        }
        self.rewind()
        # def f(a1, a2):
        #     # https://stackoverflow.com/a/26410051
        #     return (((a1 - a2[:,:,np.newaxis])).prod(axis=1)<=0).any(axis=0)

    def get_brightest_frame(self):
        """Return the brightest frame

        Looks for the brightest pixel in the percept, determines at what point
        in time it happened, and returns all brightness values at that point
        in a 2D NumPy array

        Returns
        -------
        frame : 2D NumPy array
            A slice ``percept.data[..., tmax]`` where ``tmax`` is the time at
            which the percept reached its maximum brightness.
        """
        return self.data[..., np.argmax(np.max(self.data, axis=(0, 1)))]

    def rewind(self):
        """Rewind the iterator"""
        self._next_frame = 0

    def __iter__(self):
        """Iterate over all frames in self.data"""
        self.rewind()
        return self

    def __next__(self):
        """Returns the next frame when iterating over all frames"""
        this_frame = self._next_frame
        print('next, frame:', this_frame, 'shape:', self.data.shape[-1])
        if this_frame >= self.data.shape[-1]:
            raise StopIteration
        self._next_frame += 1
        return self.data[..., this_frame]

    def plot(self, time=None, kind='pcolor', ax=None, **kwargs):
        """Plot the percept

        Parameters
        ----------
        kind : { 'pcolor' | 'hex' }, optional, default: 'pcolor'
            Kind of plot to draw:
            *  'pcolor': using Matplotlib's ``pcolor``. Additional parameters
               (e.g., ``vmin``, ``vmax``) can be passed as keyword arguments.
            *  'hex': using Matplotlib's ``hexbin``. Additional parameters
               (e.g., ``gridsize``) can be passed as keyword arguments.
        time : None, optional, default: None
            The time point to plot. If None, plots the brightest frame.
            Use ``play`` to play the percept frame-by-frame.
        ax : matplotlib.axes.Axes; optional, default: None
            A Matplotlib Axes object. If None, a new Axes object will be
            created.

        Returns
        -------
        ax : matplotlib.axes.Axes
            Returns the axes with the plot on it

        """
        if time is None:
            idx = np.argmax(np.max(self.data, axis=(0, 1)))
            frame = self.data[..., idx]
        else:
            # Need to be smart about what to do when plotting more than one
            # frame.
            raise NotImplementedError
        if ax is None:
            if 'figsize' in kwargs:
                figsize = kwargs['figsize']
            else:
                figsize = (12, 8)
                # figsize = np.int32(np.array(self.shape[:2][::-1]) / 15)
                # figsize = np.maximum(figsize, 1)
            _, ax = plt.subplots(figsize=figsize)
        else:
            if not isinstance(ax, Subplot):
                raise TypeError("'ax' must be a Matplotlib axis, not "
                                "%s." % type(ax))

        vmin, vmax = frame.min(), frame.max()
        cmap = kwargs['cmap'] if 'cmap' in kwargs else 'gray'
        X, Y = np.meshgrid(self.xdva, self.ydva, indexing='xy')
        if kind == 'pcolor':
            # Create a pseudocolor plot. Make sure to pass additional keyword
            # arguments that have not already been extracted:
            other_kwargs = {key: kwargs[key]
                            for key in (kwargs.keys() - ['figsize', 'cmap',
                                                         'vmin', 'vmax'])}
            ax.pcolormesh(X, Y, np.flipud(frame), cmap=cmap, vmin=vmin,
                          vmax=vmax, **other_kwargs)
        elif kind == 'hex':
            # Create a hexbin plot:
            gridsize = kwargs['gridsize'] if 'gridsize' in kwargs else 80
            # X, Y = np.meshgrid(self.xdva, self.ydva, indexing='xy')
            # Make sure to pass additional keyword arguments that have not
            # already been extracted:
            other_kwargs = {key: kwargs[key]
                            for key in (kwargs.keys() - ['figsize', 'cmap',
                                                         'gridsize', 'vmin',
                                                         'vmax'])}
            ax.hexbin(X.ravel(), Y.ravel()[::-1], frame.ravel(),
                      cmap=cmap, gridsize=gridsize, vmin=vmin, vmax=vmax,
                      **other_kwargs)
        else:
            raise ValueError("Unknown plot option '%s'. Choose either 'pcolor'"
                             "or 'hex'." % kind)
        ax.set_aspect('equal', adjustable='box')
        ax.set_xlim(self.xdva[0], self.xdva[-1])
        ax.set_xticks(np.linspace(self.xdva[0], self.xdva[-1], num=5))
        ax.set_xlabel('x (dva)')
        ax.set_ylim(self.ydva[0], self.ydva[-1])
        ax.set_yticks(np.linspace(self.ydva[0], self.ydva[-1], num=5))
        ax.set_ylabel('y (dva)')
        return ax

    def play(self, fps=None, ax=None):
        """Animate the percept as HTML with JavaScript

        Parameters
        ----------
        fps : float or None
            If None, uses the percept's time axis. Not supported for
            non-homogeneous time axis.
        ax : matplotlib.axes.Axes; optional, default: None
            A Matplotlib Axes object. If None, a new Axes object will be
            created.

        Returns
        -------
        ani : matplotlib.animation.FuncAnimation
            A Matplotlib animation object that will play the percept
            frame-by-frame.

        """
        def update(data):
            mat.set_data(data)
            return mat

        def data_gen():
            while True:
                yield next(self)

        if self.time is None:
            raise ValueError("Cannot animate a percept with time=None.")

        # There are several options to animate a percept in Jupyter/IPython
        # (see https://stackoverflow.com/a/46878531). Displaying the animation
        # as HTML with JavaScript is compatible with most browsers and even
        # %matplotlib inline (although it can be kind of slow):
        plt.rcParams["animation.html"] = 'jshtml'
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))
        else:
            fig = ax.figure
        # Rewind the percept and show the first frame:
        self.rewind()
        mat = ax.imshow(next(self), cmap='gray', vmax=self.data.max())
        fig.colorbar(mat)
        plt.close(fig)
        # Determine the frame rate:
        if fps is None:
            interval = np.unique(np.diff(self.time))
            if len(interval) > 1:
                raise NotImplementedError
            interval = interval[0]
        else:
            interval = 1000.0 / fps
        # Create the animation:
        ani = FuncAnimation(fig, update, data_gen, interval=interval)
        return ani

    def save(self, fname, shape=None, fps=None):
        """Save the percept as an MP4 or GIF

        Parameters
        ----------
        fname : str
            The filename to be created, with the file extension indicating the
            file type. Percepts with time=None can be saved as images (e.g.,
            '.jpg', '.png', '.gif'). Multi-frame percepts can be saved as
            movies (e.g., '.mp4', '.avi', '.mov') or '.gif'.
        shape : (height, width) or None, optional, default: (320,)
            The desired width x height of the resulting image/video.
            Use (h, None) to use a specified height and automatically infer the
            width from the percept's aspect ratio.
            Analogously, use (None, w) to use a specified width.
            If shape is None, width will be set to 320px and height will be
            inferred accordingly.
        fps : float or None
            If None, uses the percept's time axis. Not supported for
            non-homogeneous time axis.

        Notes
        -----
        *  ``shape`` will be adjusted so that width and height are multiples
            of 16 to ensure compatibility with most codecs and players.

        """
        if shape is None:
            # Use 320px width and infer height from aspect ratio:
            shape = (None, 320)
        height, width = shape
        if height is None and width is None:
            raise ValueError('If shape is a tuple, must specify either height '
                             'or width or both.')
        # Infer height or width if necessary:
        if height is None and width is not None:
            height = width / self.data.shape[1] * self.data.shape[0]
        elif height is not None and width is None:
            width = height / self.data.shape[0] * self.data.shape[1]
        # Rescale percept to desired shape:
        data = resize(self.data, (np.int32(height), np.int32(width)))
        data -= data.min()
        if not np.isclose(data.max(), 0):
            data /= data.max() * 255

        if self.time is None:
            # No time component, store as an image:
            imageio.imwrite(fname, data.astype(np.uint8))
        else:
            # With time component, store as a movie:
            if fps is None:
                interval = np.unique(np.diff(self.time))
                if len(interval) > 1:
                    raise NotImplementedError
                fps = 1000.0 / interval[0]
            imageio.mimwrite(fname, data.transpose((2, 0, 1)).astype(np.uint8),
                             fps=fps)
        logging.getLogger(__name__).info('Created %s.' % fname)
