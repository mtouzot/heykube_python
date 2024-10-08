import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="heykube",  # Replace with your own username
    version="0.5.0",
    author="Dave Garrett, Martin TOUZOT",
    author_email="info@22ndsolutions.com, martin.touzot@gmail.com",
    description="Implements Python-based interface library for HEYKUBE",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mtouzot/heykube_python",
    packages=setuptools.find_packages(),
    scripts=["scripts/heykube_cli.py"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=["bleak==0.10.0", "service_identity"],
)
