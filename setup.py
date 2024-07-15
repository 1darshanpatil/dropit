from setuptools import setup, find_packages
import os
import sys

package_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(package_dir, 'sharex'))

from dropit import __version__ 

with open(os.path.join(package_dir, 'requirements.txt')) as f:
    required = f.read().splitlines()

setup(
    name='dropit',
    version=__version__, 
    author='Darshan P.',
    author_email='drshnp@outlook.com',
    description='A Flask-based command line file sharing application.',
    long_description=open(os.path.join(package_dir, 'README.md')).read(),
    long_description_content_type='text/markdown',
    url='https://github.com/1darshanpatil/dropit',  
    packages=find_packages(),
    include_package_data=True, 
    install_requires=required, 
    entry_points={
        'console_scripts': [
            'dropit=dropit.main:run_app'
        ]
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Framework :: Flask',
    ],
    python_requires='>=3.6',
)
