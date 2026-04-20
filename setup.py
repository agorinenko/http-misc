import setuptools

# pylint: disable=all

setuptools.setup(
    name='http-misc',
    version='3.0.2',
    author='Anton Gorinenko',
    author_email='anton.gorinenko@gmail.com',
    description='Утилитарный пакет межсервисного взаимодействия по протоколу HTTP',
    long_description='',
    keywords='python, utils, http',
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages('.', exclude=['tests'], include=['http_misc*']),
    classifiers=[
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Operating System :: OS Independent',
    ],
    install_requires=[
        'PyJWT'
    ],
    extras_require={
        'aiohttp': ['aiohttp'],
        'httpx': ['httpx'],
        'all': ['aiohttp', 'httpx'],
        'test': [
            'aiohttp',
            'httpx',
            'pytest',
            'python-dotenv',
            'envparse',
            'pytest-asyncio',
            'pytest-mock',
            'pytest-env',
            'freezegun'
        ]
    },
    python_requires='>=3.10',
)
