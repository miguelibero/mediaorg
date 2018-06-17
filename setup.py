#!/usr/bin/env python

from setuptools import setup

setup(
    name='mediaorg',
    version='1.0',
    description='Organizes your media collection by time',
    long_description=open('README.md').read(),
    author='Miguel Ibero',
    author_email='miguel@ibero.me',
    license='LICENSE.txt',
    url='https://github.com/miguelibero/mediaorg',
    entry_points={
        'console_scripts': ['mediaorg=mediaorg.__main__:main'],
    },
    packages=['mediaorg'],
    install_requires=[
        "piexif >= 1.0.13",
        "parsedatetime >= 2.4",
        "argparse >= 1.4.0",
        "python-magic >= 0.4.15",
    ]
)
