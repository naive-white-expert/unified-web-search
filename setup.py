from setuptools import setup, find_packages

setup(
    name="unified-web-search",
    version="2.0.0",
    description="联网搜索统一接口 - 一个接口，自动选择最优服务商（百炼/Tavily/火山引擎）",
    author="Kang Rui",
    url="https://github.com/naive-white-expert/unified-web-search",
    packages=find_packages(),
    install_requires=[
        "PyYAML>=5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)