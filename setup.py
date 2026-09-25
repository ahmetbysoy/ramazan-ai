from setuptools import setup, find_packages

setup(
    name="ramazan-ai",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.10.0",
        "typer>=0.15.0",
        "rich>=13.9.0",
        "litellm>=1.50.0",
        "gitpython>=3.1.40",
        "pytest>=8.0.0",
        "pyyaml>=6.0.2",
        "jsonschema>=4.23.0",
        "networkx>=3.4.0",
        "fastapi>=0.115.0",
        "uvicorn>=0.30.0",
    ],
    entry_points={
        "console_scripts": [
            "ramazan = ramazan.cli:app",
        ],
    },
)
