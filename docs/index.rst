.. cfg-mgr documentation master file, created by
   sphinx-quickstart on Mon May 18 10:09:04 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

cfg-mgr documentation
=====================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Installation
============

Install ``cfg-mgr`` with pip::

   pip install cfg-mgr

The base install includes the JSON and TOML (requires python>=3.11) file loaders.
Loaders for other file formats require optional dependencies, installed as extras:

YAML file loader (with PyYaml)::

   pip install cfg-mgr[yaml]

``.env`` file loader (with python-dotenv)::

   pip install cfg-mgr[dotenv]

All optional file loaders::

   pip install cfg-mgr[all]

Or clone/fork the source: https://github.com/raghavj98/cfgmgr

API Reference
=============

.. automodule:: cfgmgr
   :members:
   :member-order: bysource
   :undoc-members:
   :show-inheritance:
