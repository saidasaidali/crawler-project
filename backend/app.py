from flask import Flask, request, jsonify
from database import sources_collection
from datetime import datetime
from flask_cors import CORS
from crawler import crawl_source_smart
from scheduler import start_scheduler, schedule_all_sources
from scheduler import schedule_source, remove_source_job
from database import data_collection
import pandas as pd
import re
from chatbot_llm import process_question


app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Web Crawler API is running"

# Ajouter une source
@app.route("/sources", methods=["POST"])
def add_source():
    source = request.json

    source["enabled"] = True
    source["running"] = False
    source["last_crawled"] = None
    source["created_at"] = datetime.now()

    if "schedule" not in source:
        return jsonify({"error": "La source doit contenir une planification"}), 400

    sources_collection.insert_one(source)
    schedule_source(source)
    return jsonify({"message": "Source ajoutée avec succès"})

# Lister les sources
@app.route("/sources", methods=["GET"])
def get_sources():
    sources = list(sources_collection.find({}, {"_id": 0}))
    return jsonify(sources)

# Lancer le crawling d’une source
@app.route("/sources/<path:source_id>/start", methods=["POST"])
def start_crawling(source_id):
    source = sources_collection.find_one({"url": source_id})
    if not source:
        return jsonify({"error": "Source introuvable"}), 404

    sources_collection.update_one({"url": source_id}, {"$set": {"running": True, "enabled": True}})
    schedule_source(source)
    return jsonify({"message": "Crawling démarré"})

# Arrêter le crawling d'une source
@app.route("/sources/<path:source_id>/stop", methods=["POST"])
def stop_crawling(source_id):
    source = sources_collection.find_one({"url": source_id})
    if not source:
        return jsonify({"error": "Source introuvable"}), 404

    sources_collection.update_one({"url": source_id}, {"$set": {"running": False}})
    remove_source_job(source_id)
    return jsonify({"message": "Crawling arrêté"})

# Activer/Désactiver une source
@app.route("/sources/<path:source_id>/toggle", methods=["PUT"])
def toggle_source(source_id):
    source = sources_collection.find_one({"url": source_id})
    if not source:
        return jsonify({"error": "Source introuvable"}), 404

    new_status = not source["enabled"]
    sources_collection.update_one({"url": source_id}, {"$set": {"enabled": new_status}})

    if new_status:
        schedule_source(source)
    else:
        remove_source_job(source_id)

    return jsonify({"message": f"Source {'activée' if new_status else 'désactivée'}"})

# Modifier une source
@app.route("/sources/<path:source_id>", methods=["PUT"])
def update_source(source_id):
    data = request.json

    if "schedule" not in data:
        return jsonify({"error": "La source doit contenir une planification"}), 400

    sources_collection.update_one({"url": source_id}, {"$set": data})

    remove_source_job(source_id)
    source = sources_collection.find_one({"url": data.get("url", source_id)})
    schedule_source(source)

    return jsonify({"message": "Source mise à jour"})

# Supprimer une source
@app.route("/sources/<path:source_id>", methods=["DELETE"])
def delete_source(source_id):
    remove_source_job(source_id)
    sources_collection.delete_one({"url": source_id})
    return jsonify({"message": "Source supprimée"})



@app.route("/search", methods=["GET"])
def search():
    keyword = request.args.get("q")

    if not keyword or keyword.strip() == "":
        return jsonify([])

    keyword = keyword.strip()

    # Vérifier si le mot-clé recherché est défini dans les sources
    sources_with_keyword = list(sources_collection.find(
        {"keywords": {"$in": [keyword]}},
        {"url": 1, "_id": 0}
    ))
    
    source_urls = [s["url"] for s in sources_with_keyword]
    is_source_keyword = len(source_urls) > 0

    # Si le mot-clé est défini dans les sources, ne renvoyer que les pages qui contiennent ce mot-clé
    if is_source_keyword:
        query = {
            "source": {"$in": source_urls},
            "$or": [
                {"keywords": {"$in": [keyword]}},
                {"keywords_found": {"$in": [keyword]}}
            ]
        }
    else:
        query = {
            "$or": [
                {"keywords": {"$regex": keyword, "$options": "i"}},
                {"keywords_found": {"$regex": keyword, "$options": "i"}},
                {"content": {"$regex": keyword, "$options": "i"}},
                {"url": {"$regex": keyword, "$options": "i"}}
            ]
        }

    results = list(
        data_collection.find(
            query,
            {"content": 1, "url": 1, "keywords": 1, "keywords_found": 1, "crawled_at": 1, "source": 1}
        )
    )

    for r in results:
        r["_id"] = str(r["_id"])

    return jsonify({
        "results": results,
        "is_source_keyword": is_source_keyword,
        "matching_sources": source_urls if is_source_keyword else []
    })


@app.route("/chatbot", methods=["POST"])
def chatbot():
    try:
        data = request.json
        question = data.get("message", "")
        result = process_question(question)
        return jsonify(result)
    except Exception as e:
        print("❌ ERREUR CHATBOT:", e)
        return jsonify({"message": "❌ Erreur serveur: " + str(e)}), 500

# Analytics endpoints
@app.route("/analytics/total_pages", methods=["GET"])
def get_total_pages():
    total = data_collection.count_documents({})
    return jsonify({"total_pages": total})

@app.route("/analytics/pages_per_source", methods=["GET"])
def get_pages_per_source():
    pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    result = list(data_collection.aggregate(pipeline))
    data = {item["_id"]: item["count"] for item in result}
    return jsonify(data)

@app.route("/analytics/keyword_frequency", methods=["GET"])
def get_keyword_frequency():
    pipeline = [
        {"$unwind": "$keywords"},
        {"$group": {"_id": "$keywords", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    result = list(data_collection.aggregate(pipeline))
    data = {item["_id"]: item["count"] for item in result}
    return jsonify(data)

@app.route("/analytics/ai_investment", methods=["GET"])
def get_ai_investment():
    ai_terms = [
        "ia", "ai", "intelligence artificielle", "machine learning",
        "deep learning", "apprentissage automatique", "data science",
        "automatisation", "robotique", "analyse prédictive"
    ]
    ai_pattern = re.compile(r"\b(?:" + "|".join([re.escape(term) for term in ai_terms]) + r")\b", re.IGNORECASE)

    total_pages = data_collection.count_documents({})
    ai_query = {
        "$or": [
            {"keywords": {"$in": ai_terms}},
            {"keywords_found": {"$in": ai_terms}},
            {"content": {"$regex": r"\b(?:" + "|".join([re.escape(term) for term in ai_terms]) + r")\b", "$options": "i"}}
        ]
    }
    ai_pages = data_collection.count_documents(ai_query)
    ai_ratio = round((ai_pages / total_pages) * 100, 1) if total_pages else 0.0

    source_pipeline = [
        {"$match": ai_query},
        {"$group": {"_id": "$source", "ai_pages": {"$sum": 1}}},
        {"$sort": {"ai_pages": -1}}
    ]
    source_data = list(data_collection.aggregate(source_pipeline))
    source_relevance = [{"source": item["_id"], "ai_pages": item["ai_pages"]} for item in source_data]

    trend_pipeline = [
        {"$match": ai_query},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$crawled_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    trend_data = list(data_collection.aggregate(trend_pipeline))
    ai_trend = {item["_id"]: item["count"] for item in trend_data}

    recommendation = "Collecte supplémentaire recommandée avant décision IA."
    if ai_ratio >= 20:
        recommendation = "Forte présence IA détectée : explorer un investissement IA prioritaire."
    elif ai_ratio >= 10:
        recommendation = "Intérêt IA modéré : renforcer la collecte et piloter des cas d’usage IA."
    elif ai_ratio > 0:
        recommendation = "Faible présence IA : collecter plus de données IA avant décision."
    else:
        recommendation = "Aucune présence IA détectée actuellement dans les données collectées."

    return jsonify({
        "total_pages": total_pages,
        "ai_pages": ai_pages,
        "ai_ratio": ai_ratio,
        "source_relevance": source_relevance,
        "ai_trend": ai_trend,
        "recommendation": recommendation
    })

@app.route("/analytics/recent_crawls", methods=["GET"])
def get_recent_crawls():
    limit = int(request.args.get("limit", 10))
    recent = list(data_collection.find({}, {"url": 1, "crawled_at": 1, "_id": 0}).sort("crawled_at", -1).limit(limit))
    return jsonify(recent)

@app.route("/analytics/source_performance", methods=["GET"])
def get_source_performance():
    pipeline = [
        {"$group": {
            "_id": "$source",
            "pages": {"$sum": 1},
            "avg_keywords": {"$avg": {"$size": {"$ifNull": ["$keywords", []]}}},
            "total_keywords": {"$sum": {"$size": {"$ifNull": ["$keywords", []]}}},
            "last_crawl": {"$max": "$crawled_at"}
        }},
        {"$sort": {"pages": -1}}
    ]
    result = list(data_collection.aggregate(pipeline))
    for item in result:
        item["source"] = item.pop("_id")
        if isinstance(item.get("last_crawl"), datetime):
            item["last_crawl"] = item["last_crawl"].isoformat()
    return jsonify(result)

@app.route("/analytics/source_keyword_coverage", methods=["GET"])
def get_source_keyword_coverage():
    sources = list(sources_collection.find({}, {"url": 1, "keywords": 1, "enabled": 1, "_id": 0}))
    coverage = []
    for source in sources:
        defined_keywords = [kw for kw in source.get("keywords", []) if kw]
        found_keywords = set()
        if defined_keywords:
            pipeline = [
                {"$match": {"source": source["url"]}},
                {"$project": {"keywords": {"$ifNull": ["$keywords", []]}, "keywords_found": {"$ifNull": ["$keywords_found", []]}}},
                {"$project": {"allKeywords": {"$setUnion": ["$keywords", "$keywords_found"]}}},
                {"$unwind": "$allKeywords"},
                {"$match": {"allKeywords": {"$in": defined_keywords}}},
                {"$group": {"_id": None, "found": {"$addToSet": "$allKeywords"}}}
            ]
            result = list(data_collection.aggregate(pipeline))
            if result:
                found_keywords = set(result[0].get("found", []))
        coverage_percent = round((len(found_keywords) / len(defined_keywords)) * 100, 1) if defined_keywords else 0.0
        missing = [kw for kw in defined_keywords if kw not in found_keywords]
        coverage.append({
            "source": source["url"],
            "enabled": bool(source.get("enabled", False)),
            "defined_keywords": defined_keywords,
            "found_keywords": sorted(list(found_keywords)),
            "missing_keywords": missing,
            "coverage_percent": coverage_percent,
            "keyword_count": len(defined_keywords)
        })
    return jsonify(coverage)

@app.route("/analytics/source_decisions", methods=["GET"])
def get_source_decisions():
    sources = list(sources_collection.find({}, {"url": 1, "keywords": 1, "enabled": 1, "schedule": 1, "last_crawled": 1, "_id": 0}))
    decisions = []
    threshold_date = datetime.now() - pd.Timedelta(days=7)
    for source in sources:
        url = source["url"]
        defined_keywords = [kw for kw in source.get("keywords", []) if kw]
        page_count = data_collection.count_documents({"source": url})
        recent_count = data_collection.count_documents({"source": url, "crawled_at": {"$gte": threshold_date}})
        visualization = list(data_collection.aggregate([
            {"$match": {"source": url}},
            {"$project": {"keywords": {"$ifNull": ["$keywords", []]}, "keywords_found": {"$ifNull": ["$keywords_found", []]}}},
            {"$project": {"allKeywords": {"$setUnion": ["$keywords", "$keywords_found"]}}},
            {"$unwind": "$allKeywords"},
            {"$match": {"allKeywords": {"$in": defined_keywords}}},
            {"$group": {"_id": None, "found": {"$addToSet": "$allKeywords"}}}
        ]))
        found_keywords = set(visualization[0].get("found", [])) if visualization else set()
        coverage_percent = round((len(found_keywords) / len(defined_keywords)) * 100, 1) if defined_keywords else 0.0
        recommendations = []
        if not source.get("enabled", False):
            recommendations.append("Source désactivée")
        if recent_count == 0:
            recommendations.append("Aucun crawl récent (7 jours)")
        if coverage_percent < 50 and defined_keywords:
            recommendations.append("Faible couverture mots-clés")
        if page_count == 0:
            recommendations.append("Aucun contenu collecté")
        if not recommendations:
            recommendations.append("Source performante")
        decisions.append({
            "source": url,
            "enabled": bool(source.get("enabled", False)),
            "schedule": source.get("schedule", {}),
            "last_crawled": source.get("last_crawled"),
            "pages": page_count,
            "recent_pages": recent_count,
            "coverage_percent": coverage_percent,
            "matched_keywords": sorted(list(found_keywords)),
            "recommendations": recommendations
        })
    return jsonify(decisions)

@app.route("/analytics/crawl_trends", methods=["GET"])
def get_crawl_trends():
    # Group by date
    pipeline = [
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$crawled_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    result = list(data_collection.aggregate(pipeline))
    data = {item["_id"]: item["count"] for item in result}
    return jsonify(data)

# Get available keywords from sources
@app.route("/keywords", methods=["GET"])
def get_keywords():
    sources = list(sources_collection.find({}, {"keywords": 1, "url": 1, "_id": 0}))
    keywords_map = {}
    
    for source in sources:
        if "keywords" in source and source["keywords"]:
            for keyword in source["keywords"]:
                if keyword not in keywords_map:
                    keywords_map[keyword] = []
                keywords_map[keyword].append(source["url"])
    
    return jsonify(keywords_map)





if __name__ == "__main__":
    #schedule_all_sources()
    start_scheduler()
    app.run(debug=True)