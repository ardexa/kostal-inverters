"""Collect from Kostal Inverters and send the data to your cloud using Ardexa

See:
https://github.com/ardexa/kostal-inverters
"""

from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='kostal_ardexa',
    version='0.1.1',
    description='Collect from Kostal Inverters and send the data to your cloud using Ardexa',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ardexa/kostal-inverters',
    author='Ardexa Pty Limited',
    author_email='support@ardexa.com',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='kostal solar inverter ardexa',
    py_modules=['kostal_ardexa'],
    install_requires=[
        'ardexaplugin',
        'Click',
        'hexdump',
    ],

    entry_points={
        'console_scripts': [
            'kostal_ardexa=kostal_ardexa:cli',
        ],
    },

    project_urls={  # Optional
        'Bug Reports': 'https://github.com/ardexa/kostal-inverters/issues',
        'Source': 'https://github.com/ardexa/kostal-inverters/',
    },
)
