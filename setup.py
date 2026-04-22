from setuptools import setup

setup(
    name="code-review-graph-plus",
    version="2.3.2.post1",
    packages=["code_review_graph", "code_review_graph.tools", "code_review_graph.eval"],
    package_dir={"code_review_graph": "."},
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "code-review-graph-plus=code_review_graph.cli:main",
        ],
    },
)
