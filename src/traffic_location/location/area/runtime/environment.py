"""Observe execution identity; no pip, apt, credentials or provider downloads."""
import importlib.metadata
import platform

def fingerprint():
    packages={}
    for name in ['numpy','shapely','pyproj','pandas','networkx','folium','cupy-cuda12x']:
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]=None
    return {'python':platform.python_version(),'packages':packages}
