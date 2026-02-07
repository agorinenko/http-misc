import setuptools

# pylint: disable=all

setuptools.setup(
    name='http-misc',
    version='1.0.5',
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
    # TODO: Убрать версии
    install_requires=[
        'aiohttp',
    ],
    extras_require={
        'test': [
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
