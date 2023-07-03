# pylint: disable=missing-module-docstring
from setuptools import find_namespace_packages, setup

setup(
    name="inductiva-api-events",
    version="0.1.0",
    packages=find_namespace_packages(),
    namespace_packages=["inductiva_api"],
    install_requires=["pydantic==1.10.2", "redis"],
)
