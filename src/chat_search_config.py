EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024
ANSWER_MODEL = "x-ai/grok-4.3"
WINDOW_MESSAGE_COUNT = 24
WINDOW_STRIDE = 8
VECTOR_RESULT_COUNT = 8
FTS_HIT_COUNT = 8
ANSWER_EVIDENCE_COUNT = 8
QUERY_INSTRUCTION = (
    "Instruct: Given a question about Telegram chat history, retrieve the chat "
    "window that answers it.\nQuery: "
)
