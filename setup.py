#!/usr/bin/env python3
"""
Setup script for Safe Computer Class
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="safe-computer-class",
    version="0.5.0",
    author="SCC Team",
    description="Safe Computer Class - School Network Security & File Sharing System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/Safe_Computer_Class",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyQt6>=6.0.0,<7.0.0",
        "requests>=2.28.0",
        "pyserial>=3.5",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
        "server": [
            "gunicorn>=21.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "scc=scc:main",
        ],
    },
)
