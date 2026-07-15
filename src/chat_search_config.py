EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024
ANSWER_MODEL = "x-ai/grok-4.3"
WINDOW_MESSAGE_COUNT = 24
WINDOW_STRIDE = 8
VECTOR_RESULT_COUNT = 12
AUTHOR_VECTOR_RESULT_COUNT = 512
ANSWER_EVIDENCE_COUNT = 6
QUERY_INSTRUCTION = (
    "Instruct: Retrieve Telegram chat windows containing direct or indirect "
    "evidence needed to answer the question. For participant comparisons and "
    "'most likely' questions, retrieve relevant statements, preferences, "
    "attitudes, and behavior.\nQuery: "
)
