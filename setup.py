# setup.py
from setuptools import setup, find_packages

setup(
    name="fudf",
    version="0.1.0",
    packages=find_packages(),                
    install_requires=[                       
    ],
    entry_points={
        "console_scripts": [
            "fudf = fudf.main:main",
        ],
    },
    author="Michael Lanahan",
    description="Streamline compiling external C UDFs for Fluent",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
)
