from collections import defaultdict
from app.schemas.state import AnalysisState
from app.schemas.models import Evidence, PainPoint
from app.services.data_loader import load_reviews

ASPECTS = {"battery": ["battery", "batteries"], "clip": ["clip"], "runtime": ["runtime"], "brightness": ["brightness"]}

def run_voc_analysis(state: AnalysisState, data_root) -> dict:
    reviews = load_reviews(data_root)
    grouped = defaultdict(list)
    for review in reviews:
        text = f"{review['title']} {review['review_text']}".lower()
        for aspect, words in ASPECTS.items():
            if any(word in text for word in words):
                grouped[aspect].append(review)
    pain_points = []
    for aspect, rows in grouped.items():
        ids = [row["review_id"] for row in rows]
        products = sorted({row["product"] for row in rows})
        for row in rows:
            state.add_evidence(Evidence(id=f"ev-review-{row['review_id']}", source=row["source"], content=row["review_text"], data_nature="SAMPLE", confidence="LOW"))
        pain_points.append(PainPoint(pain_point={"battery":"Power flexibility and battery expectations", "clip":"Pocket clip retention", "runtime":"Runtime communication", "brightness":"Brightness expectation"}[aspect], aspect=aspect, mentions=len(rows), frequency=round(len(rows)/len(reviews), 2), severity="MEDIUM" if aspect != "clip" else "HIGH", products=products, evidence_review_ids=ids, confidence="LOW").model_dump())
    return {"review_count": len(reviews), "data_notice": "SAMPLE / DEMO reviews only; not a live Amazon dataset.", "pain_points": sorted(pain_points, key=lambda item: item["mentions"], reverse=True), "sources": [{"source":"CSV import", "data_nature":"SAMPLE"}]}
