#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import os

from setuptools import setup, find_packages

setup(
    name = 'supervisor-ext',
    version = '0.1.5',
    packages = find_packages(),
    author = 'Shoubin Tang',
    author_email = 'shoubin.tang@gmail.com',
    description = 'supervisor rpcinterface & ctlplugin extensions to get ext options.',
    long_description = open(os.path.join(os.path.dirname(__file__), 'README.md')).read(),
    keywords = '',
    url = 'https://github.com/tangr/supervisor-ext',
    include_package_data = True,
    zip_safe = False,
    namespace_packages = ['supervisor_ext'],
    classifiers = [
        # 'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4'
    ],
    entry_points = {
        'console_scripts': [
            'supervisor_ext = supervisor_ext.command_line:setup',
            'supervisor_ext_memorycheck = supervisor_ext.memorycheck:main'
        ]
    }
)
