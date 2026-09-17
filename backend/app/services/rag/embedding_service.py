from abc import ABC, abstractmethod

import numpy as np


class EmbeddingService(ABC):
    """Turn text into vectors. Swap MiniLM, E5, etc. via EMBEDDING_MODEL."""

    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape (n, dimension), L2-normalized."""
