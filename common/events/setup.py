from setuptools import setup

setup(
    name='inductiva-api-events',
    version='0.1.0',
    packages=['inductiva_api.events'],
    package_dir={'inductiva_api.events': '.'},
    install_requires=['pydantic', 'redis'],
)
