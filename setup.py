import codecs
import re
from pathlib import Path

import setuptools


def read(file_path: str) -> str:
    return codecs.open(file_path, "r").read()


def get_version() -> str:
    version_file = read(str(Path("kotaemon", "__init__.py")))
    match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if match:
        return match.group(1)
    raise RuntimeError("Cannot find verison string")


setuptools.setup(
    name="kotaemon",
    version=get_version(),
    author="john",
    author_email="john@cinnamon.com",
    description="Kotaemon core library for AI development",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/Cinnamon/kotaemon/",
    packages=setuptools.find_packages(
        exclude=("tests", "tests.*", "examples", "examples.*")
    ),
    dependencies=[
        "click >= 8.1.7",
    ],
    install_requires=[
        "farm-haystack==1.19.0",
        "langchain",
        "theflow",
        "llama-index",
        "llama-hub",
        "nltk",
        "gradio",
        "openpyxl",
    ],
    extras_require={
        "dev": [
            "ipython",
            "pytest",
            "pre-commit",
            "black",
            "flake8",
            "sphinx",
            "coverage",
            # optional dependency needed for test
            "openai",
            "chromadb",
        ],
    },
    entry_points={"console_scripts": ["kh=kotaemon.cli:main"]},
    python_requires=">=3",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
)
