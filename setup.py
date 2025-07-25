from setuptools import setup

setup(
    name="lciafmt",
    version="1.3.0",
    packages=["lciafmt"],
    package_dir={'lciafmt': 'lciafmt'},
    package_data={'lciafmt': ["data/*.*"]},
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=["fedelemflowlist @ git+https://github.com/USEPA/fedelemflowlist.git@develop#egg=fedelemflowlist",
                      "esupy @ git+https://github.com/USEPA/esupy.git@develop#egg=esupy",
                      "olca-schema>=0.0.11",
                      "pandas>=0.22",
                      "openpyxl>=3.0.7",
                      "pyyaml>=5.3"
                      ],
    extras_require={"ImpactWorld": ["pyodbc >= 4.0.30;platform_system=='Windows'"]},
    license="MIT",
    author='Ben Young, Michael Srocka, Wesley Ingwersen, Troy Hottle, Ben Morelli',
    author_email='ingwersen.wesley@epa.gov',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: IDE",
        "Intended Audience :: Science/Research",
        "License :: MIT",
        "Programming Language :: Python :: 3.x",
        "Topic :: Utilities",
    ],
    description='Standardizes the format and flows of life cycle impact assessment data'
)
