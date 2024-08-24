"""
MIT License

Copyright (c) 2024 Darshan P.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

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
