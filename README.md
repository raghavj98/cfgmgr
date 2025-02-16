# pyconfig
Load and use configuration objects in python applications
- Load from environment of files (json and yaml currently supported)
- Files can recursively include other files (Settings from included files will be overwritten by including file)
- Simple syntax for consumers of configurations `CfgMgr.get('config_name').foo`
- See example.py in tests/ for detailed usage!
