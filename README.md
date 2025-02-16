# cfgmgr
Load and use configuration objects in python applications
- Load from environment of files (json and yaml currently supported)
- Files can recursively include other files (Settings from included files will be overwritten by including file)
- Simple syntax for consumers of configurations `CfgMgr.get('config_name').foo`
- To install, run python3 -m build, followed by python3 -m pip install dist/<wheel>
- See example.py in tests/ for detailed usage!
