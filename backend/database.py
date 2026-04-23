from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["web_crawler"]

sources_collection = db["sources"]
data_collection = db["crawled_data"]
analysis_collection = db["analysis_results"]