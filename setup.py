from setuptools import setup, find_packages

setup(
    name="custom-network-proxy-server",
    version="1.0.0",
    description="A custom HTTP/HTTPS proxy server with filtering, caching, logging, and authentication",
    author="Your Name",
    python_requires=">=3.10",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[],
    entry_points={
        "console_scripts": [
            "proxy-server=server:main",
        ]
    },
)
