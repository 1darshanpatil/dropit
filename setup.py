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

import os
import re

from setuptools import setup, find_packages

package_dir = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(package_dir, 'dropit', '__init__.py'), encoding='utf-8') as version_file:
    __version__ = re.search(r'__version__\s*=\s*"([^"]+)"', version_file.read()).group(1)

setup(
    name='dropit',
    version=__version__, 
    author='Darshan P.',
    author_email='drshnp@outlook.com',
    description='A Flask-based command line file sharing application.',
    long_description=open(os.path.join(package_dir, 'README.md'), encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/1darshanpatil/dropit',
    project_urls={
        'Source': 'https://github.com/1darshanpatil/dropit',
        'Issue Tracker': 'https://github.com/1darshanpatil/dropit/issues',
    },
    license='MIT',
    packages=find_packages(),
    include_package_data=True, 
    install_requires=[
        'Flask>=3.1.1,<4',
        'Flask-BasicAuth>=0.2.0',
        'cheroot>=10.0.0',
        'Werkzeug>=3.1.3,<4',
        'qrcode>=7.3,<9',
        'cryptography>=41.0.0',
    ],
    entry_points={
        'console_scripts': [
            'dropit=dropit.main:run_app'
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Framework :: Flask',
        'Topic :: Communications :: File Sharing',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
    ],
    python_requires='>=3.9',
)
