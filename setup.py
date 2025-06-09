#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="autonomous-language-model",
    version="1.0.0",
    author="ALM Developer",
    author_email="developer@example.com",
    description="A robust autonomous language model interface for local Ollama instances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/alm",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "alm=main:main",
        ],
    },
    keywords="ai, ollama, language-model, autonomous, chatbot",
    project_urls={
        "Bug Reports": "https://github.com/example/alm/issues",
        "Source": "https://github.com/example/alm",
    },
) 