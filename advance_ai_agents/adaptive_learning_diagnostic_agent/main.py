from misconception_library import MISCONCEPTIONS
from trace_parser import parse_steps
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')


def diagnose(student_steps):
    combined = parse_steps(student_steps)
    combined_embedding = model.encode(combined, convert_to_tensor=True)             
    best_match = None
    best_score = -1

    for name, data in MISCONCEPTIONS.items():
        desc_embedding = model.encode(data["description"], convert_to_tensor=True)
        score = util.cos_sim(combined_embedding, desc_embedding).item()
        if score > best_score:
            best_score = score
            best_match = name

    return best_match, best_score


if __name__ == "__main__":
    steps = [
        "i starts at 0",
        "0 < 5 is true",
        "i becomes 1",
        "print 0"
    ]

    match, score = diagnose(steps)
    print(f"Detected misconception: {match}")
    print(f"Confidence: {score:.2f}")
    print(f"Description: {MISCONCEPTIONS[match]['description']}")