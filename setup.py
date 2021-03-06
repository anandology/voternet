from setuptools import setup, find_packages
import glob, os

dependencies = [
    'web.py',
    'psycopg2',
    'markdown',
    'pyYAML',
    'tablib',
    'xappy',
    'flup',
    'pytz',
    'WTForms'
]

setup(
    name='voternet',
    version='0.1.0-dev',
    description='Voternet',
    packages=find_packages(exclude=["ez_setup"]),
    install_requires=dependencies
)
