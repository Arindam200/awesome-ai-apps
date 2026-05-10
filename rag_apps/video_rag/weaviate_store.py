"""Weaviate v4 client wrapper for the VideoSegment collection."""

from __future__ import annotations

import os
from typing import Iterable

import weaviate
from weaviate.auth import AuthApiKey
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.query import Filter, MetadataQuery

COLLECTION = "VideoSegment"


def get_client() -> weaviate.WeaviateClient:
    url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    api_key = os.getenv("WEAVIATE_API_KEY")
    if api_key:
        return weaviate.connect_to_weaviate_cloud(cluster_url=url, auth_credentials=AuthApiKey(api_key))
    host = url.replace("http://", "").replace("https://", "").split(":")[0]
    port = int(url.split(":")[-1]) if ":" in url.replace("http://", "").replace("https://", "") else 8080
    return weaviate.connect_to_local(host=host, port=port)


def ensure_schema(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists(COLLECTION):
        return
    client.collections.create(
        name=COLLECTION,
        vectorizer_config=Configure.Vectorizer.none(),
        vector_index_config=Configure.VectorIndex.hnsw(distance_metric=VectorDistances.COSINE),
        properties=[
            Property(name="video_id", data_type=DataType.TEXT),
            Property(name="modality", data_type=DataType.TEXT),
            Property(name="start_time", data_type=DataType.NUMBER),
            Property(name="end_time", data_type=DataType.NUMBER),
            Property(name="clip_path", data_type=DataType.TEXT),
        ],
    )


def reset_collection(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists(COLLECTION):
        client.collections.delete(COLLECTION)
    ensure_schema(client)


def upsert_segments(
    client: weaviate.WeaviateClient, segments: Iterable[dict], vectors: Iterable[list[float]]
) -> int:
    coll = client.collections.get(COLLECTION)
    count = 0
    with coll.batch.dynamic() as batch:
        for seg, vec in zip(segments, vectors):
            batch.add_object(properties=seg, vector=vec)
            count += 1
    return count


def search(
    client: weaviate.WeaviateClient,
    query_vector: list[float],
    top_k: int = 8,
    video_id: str | None = None,
    modality: str | None = None,
) -> list[dict]:
    coll = client.collections.get(COLLECTION)
    filters = []
    if video_id:
        filters.append(Filter.by_property("video_id").equal(video_id))
    if modality:
        filters.append(Filter.by_property("modality").equal(modality))
    combined = None
    if filters:
        combined = filters[0]
        for f in filters[1:]:
            combined = combined & f
    res = coll.query.near_vector(
        near_vector=query_vector,
        limit=top_k,
        filters=combined,
        return_metadata=MetadataQuery(distance=True),
    )
    out = []
    for o in res.objects:
        props = dict(o.properties)
        props["score"] = 1.0 - (o.metadata.distance or 0.0)
        out.append(props)
    return out
