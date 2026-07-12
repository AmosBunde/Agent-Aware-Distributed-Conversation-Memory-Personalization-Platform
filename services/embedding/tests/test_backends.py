import math

import pytest

from services.embedding.app.backends import LocalHashingBackend, build_backend


async def test_same_input_same_vector():
    backend = LocalHashingBackend(dim=384)
    [a] = await backend.embed(["I prefer concise answers"])
    [b] = await backend.embed(["I prefer concise answers"])
    assert a == b


async def test_vectors_are_unit_norm_and_correct_dim():
    backend = LocalHashingBackend(dim=384)
    [vec] = await backend.embed(["senior python engineer"])
    assert len(vec) == 384
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-9)


async def test_similar_texts_score_higher_than_unrelated():
    backend = LocalHashingBackend(dim=384)
    [python_help, python_prefs, cooking] = await backend.embed(
        [
            "help me debug python code",
            "python code style preferences",
            "recipe for banana bread",
        ]
    )
    sim_related = sum(a * b for a, b in zip(python_help, python_prefs, strict=True))
    sim_unrelated = sum(a * b for a, b in zip(python_help, cooking, strict=True))
    assert sim_related > sim_unrelated


async def test_empty_text_yields_valid_unit_vector():
    backend = LocalHashingBackend(dim=8)
    [vec] = await backend.embed(["   "])
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0)


def test_build_backend_local():
    assert build_backend("local", 384).name == "local"


def test_build_backend_openai_requires_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_backend("openai", 384, api_key="")


def test_build_backend_unknown_rejected():
    with pytest.raises(ValueError, match="Unknown embedding backend"):
        build_backend("word2vec", 384)
