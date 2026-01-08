from setuptools import setup

setup(
    name="custom-network-proxy-server",
    version="1.0.0",
    description="A custom HTTP/HTTPS proxy server with filtering, caching, logging, and authentication",
    author="Krit Jain",
    python_requires=">=3.10",
    py_modules=[
        "server",
        "handler",
        "parser",
        "forwarder",
        "filter",
        "cache",
        "logger",
        "config_loader",
    ],
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[],
    entry_points={
        "console_scripts": [
            "proxy-server=server:main",
        ]
    },
)
