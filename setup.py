#!/usr/bin/env python

from setuptools import setup

setup(
    name='photorg',
    version='1.0',
    description='Orders your photo collection based on exif tags',
    long_description=open('README.md').read(),
    author='Miguel Ibero',
    author_email='miguel@ibero.me',
    license='LICENSE.txt',
    url='https://github.com/miguelibero/photorg',
    entry_points={
        'console_scripts': ['photorg=photorg.__main__:main'],
    },
    packages=['photorg'],
    install_requires=[
        "piexif >= 1.0.13",
        "argparse >= 1.4.0",
        "python-magic >= 0.4.15"
    ]
)
