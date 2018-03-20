from setuptools import setup, find_packages
from os import path

import aiostratum_proxy

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError):
    from codecs import open
    here = path.abspath(path.dirname(__file__))
    with open(path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()

setup(
    name='aiostratum_proxy',
    version=aiostratum_proxy.__version__,
    description='Python3 asyncio stratum protocol mining proxy',
    long_description=long_description,
    keywords='async asyncio aio crypto cryptocurrency blockchain '
             'mining stratum protocol proxy pool equihash bitcoin'
             'litecoin',

    license='MIT',
    author='wetblanketcc',
    author_email='35851045+wetblanketcc@users.noreply.github.com',
    url='https://github.com/wetblanketcc/aiostratum_proxy',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: AsyncIO',
        'Intended Audience :: Financial and Insurance Industry',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: System :: Networking',
    ],

    packages=find_packages(),

    python_requires='>=3.5',
    install_requires=[
        'aiojsonrpc2==1.0.0',
        'PyYAML==3.12',
    ],

    entry_points = {
        'console_scripts': [
            'aiostratum-proxy=aiostratum_proxy.application:main'
        ],
    }
)
