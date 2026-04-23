from flask import Flask, request, jsonify
from database import sources_collection
from datetime import datetime
from flask_cors import CORS
from crawler import crawl_source_smart
from scheduler import start_scheduler, schedule_all_sources
from scheduler import schedule_source, remove_source_job
from database import data_collection
import pandas as pd
from datetime import datetime
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

    # Cherche le mot exact dans la liste 'keywords'
    results = list(
        data_collection.find(
            {
                    "$or": [
                       {"keywords": {"$regex": keyword, "$options": "i"}},
                       {"content": {"$regex": keyword, "$options": "i"}},
                       {"url": {"$regex": keyword, "$options": "i"}}
                    ]
            },
            {"content": 1, "url": 1, "keywords": 1, "crawled_at": 1}
        )
    )

    for r in results:
        r["_id"] = str(r["_id"])

    return jsonify(results)


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





if __name__ == "__main__":
    #schedule_all_sources()
    start_scheduler()
    app.run(debug=True)