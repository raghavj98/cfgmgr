from pyconfig import PyConfig


def exampleFunc() -> None:
    print(f"This function uses configb: {PyConfig.get('configb')}")
