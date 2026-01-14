from sentence_transformers import SentenceTransformer


def encode_texts(texts):
    if type(texts) == str:
        texts = [texts]

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    embeddings = model.encode(texts)

    return embeddings


def expressed_to_binary(value, positive_values=None, negative_values=None) -> int:
    """
    Convert a value to 1 (expressed) or 0 (not expressed)

    Parameters
    ----------
    value : any
        Cell value from dataframe
    positive_values : set[str]
        Values that indicate expression
    negative_values : set[str]
        Values that indicate no expression

    Returns
    -------
    int
        1 if expressed, 0 otherwise
    """

    if value is None:
        return 0

    v = str(value).strip().lower()

    positive_values = positive_values or {
        "yes",
        "y",
        "true",
        "1",
        "positive",
        "+",
        "expressed",
    }
    negative_values = negative_values or {
        "no",
        "n",
        "false",
        "0",
        "negative",
        "-",
        "not expressed",
    }

    if v in positive_values:
        return 1
    if v in negative_values:
        return 0

    # Default fallback: treat unknown as not expressed
    return 0
