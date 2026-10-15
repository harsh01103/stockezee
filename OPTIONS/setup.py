from setuptools import setup, find_packages

setup(
    name="stockezee-options-engine",
    version="4.5.1",
    author="Harsh Vardhan Ajmera",
    author_email="hajmera011@gmail.com",
    description="High-Frequency Options Microstructure, LLVM Greeks & ML Execution Engine",
    packages=find_packages(include=["auth*", "market*", "opportunities*", "features*", "trade*", "config*"]),
    python_requires=">=3.10",
    install_requires=[
        "polars>=0.20.0",
        "pyarrow>=14.0.0",
        "numba>=0.58.0",
        "numpy>=1.24.0",
        "cryptography>=41.0.0",
        "protobuf>=4.25.0",
        "pydantic>=2.0.0",
        "loguru>=0.7.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
)
