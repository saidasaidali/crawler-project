
import pandas as pd
from database import data_collection
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3"


def load_data(keyword=None):
    query = {}
    if keyword:
        query["keywords"] = {"$in": [keyword]}

    docs = list(data_collection.find(query, {"_id": 0}))
    df = pd.DataFrame(docs)

    if "crawled_at" in df.columns:
        df["crawled_at"] = pd.to_datetime(df["crawled_at"], errors="coerce")

    return df


def generate_charts(df):
    charts = {}

    if "keywords" in df.columns:
        kw = df.explode("keywords")
        charts["keywords"] = {str(k): int(v) for k, v in kw["keywords"].value_counts().head(10).to_dict().items()}

    if "url" in df.columns:
        charts["sources"] = {str(k): int(v) for k, v in df["url"].value_counts().head(10).to_dict().items()}

    if "crawled_at" in df.columns:
        trend = df.groupby(df["crawled_at"].dt.date).size()
        charts["trend"] = {str(k): int(v) for k, v in trend.to_dict().items()}

    return charts



def query_llm(df, question):
    summary = f"""
Données analysées:
- Nombre de documents: {len(df)}
"""

    if "keywords" in df.columns:
        top_kw = df.explode("keywords")["keywords"].value_counts().head(5).index.tolist()
        summary += f"- Top mots-clés: {', '.join(top_kw)}\n"

    if "url" in df.columns:
        top_sources = df["url"].value_counts().head(5).index.tolist()
        summary += f"- Top sources: {', '.join(top_sources)}\n"

    prompt = f"""
Tu es un analyste de données.

Question:
{question}

Données:
{summary}

Donne une réponse claire en français + une conclusion ou recommandation.
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
    except Exception as e:
        return "❌ Erreur Ollama: " + str(e)


    result = response.json()
    return result["response"]


def process_question(question, keyword=None):
    df = load_data(keyword)

    if df.empty:
        return {"type": "text", "message": "Aucune donnée disponible."}

    charts = generate_charts(df)
    llm_text = query_llm(df, question)

    return {
        "type": "dashboard",
        "message": llm_text,
        "charts": charts
    }

