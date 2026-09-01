"""
CourseMatch backend — FastAPI wrapper around the recommend() logic.

Loads precomputed artifacts exported from the Colab notebook (see the
project README for exactly which files to copy into ./data). Nothing here
retrains anything -- it only runs inference: encode the query text, rank
courses by similarity, apply filters and nudges.

Run with:
    uvicorn main:app --reload --port 8000
"""

import os
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

DEGREE_TO_LEVEL_NUDGE = {
    "undergrad": {"beginner": 1.0, "intermediate": 0.6, "advanced": 0.2},
    "masters":   {"beginner": 0.5, "intermediate": 1.0, "advanced": 0.7},
    "phd":       {"beginner": 0.3, "intermediate": 0.7, "advanced": 1.0},
}
CONTRASTIVE_BLEND = 0.5  # weight given to the contrastive-trained space vs. raw SBERT similarity

app = FastAPI(title="CourseMatch Recommender API")

# Local dev: allow the frontend (opened as a local file or on any port) to call this.
# Tighten allow_origins if you ever deploy this publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print(f"[startup] Loading data from {DATA_DIR} ...")
df = pd.read_csv(os.path.join(DATA_DIR, "unified_courses.csv"))
raw_embeddings = np.load(os.path.join(DATA_DIR, "course_embeddings.npy"))

using_hybrid = False
contrastive_embeddings = None
try:
    contrastive_embeddings = np.load(os.path.join(DATA_DIR, "contrastive_embeddings.npy"))
    cluster_df = pd.read_csv(os.path.join(DATA_DIR, "node_index_with_clusters.csv"))
    df["cluster_id"] = cluster_df["cluster_id"].values
    using_hybrid = True
    print("[startup] Loaded contrastive embeddings + cluster assignments -- using hybrid ranking.")
except FileNotFoundError:
    df["cluster_id"] = -1
    print("[startup] contrastive_embeddings.npy not found -- falling back to raw SBERT similarity only.")

print("[startup] Loading SentenceTransformer (all-MiniLM-L6-v2) -- first run downloads the model, ~90MB ...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print(f"[startup] Ready. {len(df)} courses loaded.")


class RecommendRequest(BaseModel):
    target_topic: str
    degree: Optional[str] = None
    specialization: Optional[str] = None
    is_paid: Optional[bool] = None
    max_duration_weeks: Optional[float] = None
    extra_description: Optional[str] = ""
    top_k: int = 5


@app.get("/health")
def health():
    return {"status": "ok", "courses_loaded": len(df), "hybrid_ranking": using_hybrid}


@app.post("/recommend")
def recommend(req: RecommendRequest):
    query_parts = [req.target_topic]
    if req.specialization:
        query_parts.append(f"background in {req.specialization}")
    if req.extra_description:
        query_parts.append(req.extra_description)
    query_text = ". ".join(query_parts)

    query_embedding = model.encode([query_text], normalize_embeddings=True)
    content_sim_raw = cosine_similarity(query_embedding, raw_embeddings)[0]

    if using_hybrid:
        # Anchor the query to its nearest neighbor in raw SBERT space, then
        # rank everyone else by that neighbor's position in the (better
        # performing) contrastive-trained space.
        best_match_idx = content_sim_raw.argmax()
        anchor_z = contrastive_embeddings[best_match_idx:best_match_idx + 1]
        content_sim_refined = cosine_similarity(anchor_z, contrastive_embeddings)[0]
        content_sim = (1 - CONTRASTIVE_BLEND) * content_sim_raw + CONTRASTIVE_BLEND * content_sim_refined

        query_cluster = df.loc[best_match_idx, "cluster_id"]
        cluster_bonus = (df["cluster_id"] == query_cluster).astype(float).values * 0.15
    else:
        content_sim = content_sim_raw
        cluster_bonus = np.zeros(len(df))

    mask = pd.Series(True, index=df.index)
    if req.is_paid is not None:
        mask &= (df["is_paid"] == req.is_paid) | df["is_paid"].isna()
    if req.max_duration_weeks is not None:
        mask &= (df["duration_weeks"] <= req.max_duration_weeks) | df["duration_weeks"].isna()

    candidates = df[mask].copy()
    candidate_idx = candidates.index.values
    score = content_sim[candidate_idx] + cluster_bonus[candidate_idx]

    if req.degree and req.degree.lower() in DEGREE_TO_LEVEL_NUDGE:
        nudge_table = DEGREE_TO_LEVEL_NUDGE[req.degree.lower()]
        level_nudge = candidates["level"].fillna("").str.lower().map(
            lambda lvl: nudge_table.get(lvl, 0.5)
        ).values
        score = score + 0.1 * level_nudge

    completeness_penalty = (candidates["data_completeness"] == "partial").astype(float).values * 0.05
    score = score - completeness_penalty

    candidates["match_score"] = score
    results = candidates.sort_values("match_score", ascending=False).head(req.top_k)

    output = []
    for _, row in results.iterrows():
        output.append({
            "title": row["title"],
            "platform": row["platform"],
            "level": row["level"] if pd.notna(row["level"]) else "Not specified",
            "is_paid": bool(row["is_paid"]) if pd.notna(row["is_paid"]) else None,
            "price": float(row["price"]) if pd.notna(row["price"]) else None,
            "duration_weeks": float(row["duration_weeks"]) if pd.notna(row["duration_weeks"]) else None,
            "url": row["url"] if pd.notna(row["url"]) else None,
            "description": row["description"] if pd.notna(row["description"])
                           else "Detailed description not available for this course.",
            "match_score": round(float(row["match_score"]), 3),
            "data_completeness": row["data_completeness"],
        })

    return {"results": output, "hybrid_ranking": using_hybrid}
