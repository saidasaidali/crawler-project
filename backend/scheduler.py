from apscheduler.schedulers.background import BackgroundScheduler
from crawler import crawl_source_smart  # 🔹 utiliser crawl_url au lieu de crawl_source
from database import sources_collection  # Assure-toi que tu importes bien ta collection MongoDB

scheduler = BackgroundScheduler()

# Planifier une source individuelle
def schedule_source(source):
    if "schedule" not in source:
        print(f"[Warning] La source {source['url']} n'a pas de schedule, elle sera ignorée")
        return

    schedule = source["schedule"]
    unit = schedule["unit"]
    value = schedule["value"]

    trigger_args = {unit: value}

    scheduler.add_job(
        crawl_source_smart,          # 🔹 nouvelle fonction crawl_url
        trigger="interval",
        args=[source],
        id=source["url"],   # Chaque source a un job unique
        replace_existing=True,
        **trigger_args
    )

# Planifier toutes les sources activées
def schedule_all_sources():
    sources = sources_collection.find({"enabled": True})
    for source in sources:
        schedule_source(source)
    print("[Scheduler] Tous les jobs des sources activées sont planifiés")

# Supprimer un job existant
def remove_source_job(source_id):
    try:
        scheduler.remove_job(source_id)
    except:
        pass

# Démarrer le scheduler
def start_scheduler():
    scheduler.start()
