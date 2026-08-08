import json


async def openrouter_embeddings(
    model: str,
    inputs: list[str],
    *,
    dimensions: int,
) -> list[list[float]]:
    from commands.ai import openrouter_provider

    response = await openrouter_provider().sdk_client.embeddings.create(
        model=model,
        input=inputs,
        dimensions=dimensions,
        extra_body={"provider": {"sort": "latency"}},
    )
    embeddings = [item.embedding for item in response.data]
    for embedding in embeddings:
        if len(embedding) != dimensions:
            raise RuntimeError(
                f"Expected {dimensions} embedding dimensions, got {len(embedding)}"
            )
    return embeddings


def vector32_json(embedding: list[float]) -> str:
    return json.dumps(embedding, separators=(",", ":"))
