##############################################################################
#
# Copyright (c) Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Setup for package cipher.longrequest
"""
import os
from setuptools import setup, find_packages


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

setup(
    name='cipher.longrequest',
    version='1.0.11.dev0',
    url="http://pypi.python.org/pypi/cipher.longrequest/",
    author='Zope Foundation and Contributors',
    author_email='zope-dev@zope.org',
    description="Detecting long requests LIVE, using paster",
    long_description=(
        read('README.txt')
        + '\n\n' +
        read('CHANGES.txt')
        ),
    license='ZPL 2.1',
    keywords="CipherHealth long request thread paster",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Zope Public License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP',
        'Framework :: Zope3'],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    extras_require=dict(
        test=[
            'zope.testing',
            'zope.testrunner',
            'mock',
        ],
    ),
    install_requires=[
        'setuptools',
        'zope.component',
        'cipher.background',
        'Paste',
    ],
    include_package_data=True,
    zip_safe=False,
    entry_points='''
    [paste.filter_app_factory]
    longrequest= cipher.longrequest.longrequest:make_filter
    [distutils.commands]
    ftest = zope.testrunner.eggsupport:ftest
    '''
)
