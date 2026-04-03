from setuptools import setup, find_packages

setup(
    name="adflux-rag",
    version="1.0.0",
    description="AdFlux Media RAG — Retrieval-Augmented Generation for lead intelligence",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "chromadb>=0.4.0",
        "sentence-transformers",
        "pandas",
        "tqdm",
        "python-dotenv",
        "ijson",
    ],
)
