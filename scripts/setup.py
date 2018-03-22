from setuptools import setup

setup(
    name='KostalArdexa',
    version='0.1.0',
    py_modules=['kostal_ardexa'],
    install_requires=[
        'Click',
        'hexdump',
    ],
    entry_points='''
        [console_scripts]
        kostal_ardexa=kostal_ardexa:cli
    ''',
)
