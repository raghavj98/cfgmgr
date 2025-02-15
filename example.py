from pyconfig import CfgMgr, CfgSchema, EnvLoader, FileLoader


class MyCfg(CfgSchema):
    foo: int
    bar: int
    baz: int


def hook(some_dict):
    if 'foo' not in some_dict:
        raise ValueError
    some_dict['foo'] = some_dict['foo'] * 2


def print_cfg():
    print(f'foo: {CfgMgr.get().foo}')
    print(f'bar: {CfgMgr.get().bar}')
    print(f'baz: {CfgMgr.get().baz}')



def load_cfg():
    file_loader = FileLoader('config.json', 'json')
    env_loader = EnvLoader('CFG_')  # Same as default
    CfgMgr.load(MyCfg,
            loaders=[file_loader, env_loader],
            baz=0,
            post_load_hook = hook
    )

if __name__ == '__main__':
    load_cfg()
    print_cfg()
