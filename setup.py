from setuptools import setup, find_packages

# Read version from __init__.py
with open("cofog_panel/__init__.py") as f:
    version = next(line for line in f if line.startswith('__version__')).split('=')[1].strip().strip('"\'')

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cofog-panel",
    version=version,
    author="Your Name/Team Name",
    author_email="your.email@example.com",
    description="Tool to harmonize IMF GFS COFOG data into reproducible panel datasets.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/COFOG-Panel",
    packages=find_packages(exclude=("tests",)), # Ensure only directories with __init__.py are included
    install_requires=[
        "pandas>=2.0.0",
        "openpyxl",
        "gspread",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "google-api-python-client",
        "typer[all]",
        "gspread-dataframe",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires='>=3.8',
    
    # DEFINE ENTRY POINT FOR CLI
    entry_points={
        'console_scripts': [
            # CONFIRM: The 'cofog-panel' command points to module 'cli' inside package 'cofog_panel'
            'cofog-panel = cofog_panel.cli:app', 
        ],
    },
)