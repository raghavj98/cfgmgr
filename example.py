from pyconfig import PyConfig
from example2 import exampleFunc


@PyConfig.post_load
def hook(d):
    for el in d:
        print(f"For key {el}, vlaue is {d[el]}")


def main():
    PyConfig.load('example/config.json', env=True, env_prefix='PYCFG_', configc='kwargs_c_val', configd='kwargs_d_val')
    exampleFunc()


if __name__ == '__main__':
    main()
