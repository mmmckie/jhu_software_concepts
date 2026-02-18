"""Setuptools configuration for module_5."""

from setuptools import find_packages, setup


setup(
    name="jhu-software-concepts-module-5",
    version="0.1.0",
    description="GradCafe admissions pipeline and Flask analysis app",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    py_modules=[
        "clean",
        "db_config",
        "load_data",
        "main",
        "query_data",
        "run",
        "scrape",
    ],
)
