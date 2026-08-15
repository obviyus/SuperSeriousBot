EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
MEMORY_MODEL = "deepseek/deepseek-v4-flash-0731"
ROUTER_MODEL = "qwen/qwen3.7-flash"
EMBEDDING_DIMENSIONS = 1024
UTTERANCE_EMBEDDING_DIMENSIONS = 256
UTTERANCE_GAP_SECONDS = 300
UTTERANCE_MAX_MESSAGES = 12
WINDOW_MESSAGE_COUNT = 24
WINDOW_STRIDE = 8
VECTOR_RESULT_COUNT = 12
AUTHOR_VECTOR_RESULT_COUNT = 512
ANSWER_EVIDENCE_COUNT = 6
QUERY_INSTRUCTION = (
    "Instruct: Retrieve Telegram chat windows containing direct or indirect "
    "evidence needed to answer the question. For abstract participant comparisons "
    "and 'most likely' questions, interpret the trait as chat persona and retrieve "
    "observable statements, preferences, attitudes, and behavior that support a "
    "playful choice.\nQuery: "
)
