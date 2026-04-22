from setuptools import setup, find_packages

setup(
    name="code-review-graph",
    version="2.3.2.post1",
    packages=find_packages(),
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "code-review-graph=code_review_graph.cli:main",
        ],
    },
)
