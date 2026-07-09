from setuptools import setup, find_packages

setup(
    name="luxelead",
    version="0.5.0",
    description="LuxeLead PPT Generator - 轻奢领先竞品的PPT排版工具",
    author="LuxeLead Team",
    author_email="support@luxelead.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "python-pptx>=0.6.23",
        "Pillow>=10.0.0",
        "lxml>=4.9.0",
        "ultralytics>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "luxelead=luxelead.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)