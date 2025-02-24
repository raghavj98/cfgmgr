from cfgmgr import CfgMgr, CfgSchema, FileLoader, EnvLoader


class MyCfg(CfgSchema):
    db_user: str
    db_pwd: str
    db_host: str
    db_port: int
    admins: list[str]


def hook(some_dict):
    # Might want to check if the db_server is listening at this point
    host = some_dict['db_host']
    port = some_dict['db_port']
    print(f"checking connectivity on db://{host}:{port}")


def load_cfg():
    file_loader = FileLoader('config_files/config.json', 'json', include_key='include')
    CfgMgr.load(MyCfg,
                loaders=[
                    file_loader,
                ],
                post_load_hook=hook
                )


if __name__ == '__main__':
    load_cfg()
    print(CfgMgr.get())
