from sentence_transformers import SentenceTransformer


def encode_texts(texts):

    if type(texts) == str:
        texts = [texts]

    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    embeddings = model.encode(texts)

    return embeddings