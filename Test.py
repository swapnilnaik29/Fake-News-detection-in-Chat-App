import pickle

# Load vectorizer
with open("tfidf_vectorizer.pkl", "rb") as file:
    vectorizer = pickle.load(file)

# Load model
with open("random_forest_model.pkl", "rb") as file:
    model = pickle.load(file)

# Test prediction
test_text = [" "]
test_vectorized = vectorizer.transform(test_text)
probability = model.predict_proba(test_vectorized)[:, 1]
print("Probability of being REAL:", probability)
