import os
import asyncio  # <--- CHANGED: Replaced 'time' with 'asyncio'
import datetime
import re
from typing import List, Dict, Optional
from together import AsyncTogether  # <--- CHANGED: Import AsyncTogether

# --- CONFIGURATION: FALLBACK MODEL LISTS ---
MODELS_PRECISE = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "openai/gpt-oss-120b",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1"
]

MODELS_FAST = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo"
]

REWRITE_MODELS = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1"
]

MODELS_ROUTER = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1"
]

# Initialize ASYNC client
# (Ideally, use os.environ.get("TOGETHER_API_KEY") for safety)
client = AsyncTogether(api_key="f093074f102974466d625db36d8bd171b92df916fa78eb7b91faa9108e6ed5c2")


# --- HELPER: GENERIC ASYNC API CALL WITH FALLBACK ---
async def query_llm_with_fallback(messages: List[Dict], model_list: List[str], max_tokens: int = 1024, temp: float = 0.0) -> str:
    """
    Async version: Tries models in order. Logs to file.
    """
    
    # --- LOGGING BLOCK (Kept Synchronous for simplicity) ---
    try:
        with open("llm_prompt_logs.txt", "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'='*60}\n")
            f.write(f"TIMESTAMP: {timestamp}\n")
            f.write(f"MODELS QUEUED: {model_list}\n")
            f.write("-" * 20 + " PROMPT START " + "-" * 20 + "\n")
            for msg in messages:
                role = msg.get('role', 'unknown').upper()
                content = msg.get('content', '')
                f.write(f"[{role}]:\n{content}\n")
            f.write("-" * 20 + " PROMPT END " + "-" * 21 + "\n")
            f.write(f"{'='*60}\n\n")
    except Exception as e:
        print(f"Warning: Failed to log prompt to file: {e}")
    # --------------------------

    for model_name in model_list:
        try:
            # CHANGED: Added 'await'
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            # We catch generic exceptions because specific Together errors vary by version
            # If it's a rate limit or service error, we wait and retry
            print(f"Warning: Issue with {model_name}: {e}. Switching to fallback...")
            
            # CHANGED: Use asyncio.sleep instead of time.sleep
            await asyncio.sleep(1) 
            continue

    raise Exception("All AI models are currently unavailable. Please try again later.")


# --- HELPER 1: Internal Classifier ---
async def _classify_query_intent(query: str) -> str:
    """
    Classifies intent using the Fallback Helper (Async).
    """
    try:
        ROUTER_PROMPT = """
        Analyze the user's query and classify it into one of three distinct Retrieval Categories:

        1. "GLOBAL_SUMMARY": The user wants a summary, outline, or overview of the *entire* document.
        2. "BROAD_SEARCH": The user asks for a list, comparison, or explanation that requires gathering many scattered details.
        3. "SPECIFIC_SEARCH": The user asks for a precise fact, date, name, or definition.
        4. "PAGE_SPECIFIC": The user explicitly asks for content from specific pages.
        5. "GREETING": Conversational filler, greetings, thanks.
        6. "NONSENSE": The input is gibberish.

        User Query: "{query}"
        OUTPUT: Output ONLY the category name. No other text.
        """

        messages = [{"role": "user", "content": ROUTER_PROMPT.format(query=query)}]
        
        # CHANGED: Added 'await'
        raw_text = await query_llm_with_fallback(
            messages=messages, 
            model_list=MODELS_ROUTER, 
            max_tokens=15, 
            temp=0.0
        )
        
        raw_text = raw_text.upper()
        print(f"[RETRIEVER] LLM Classifier Output: '{raw_text}'")

        if re.search(r"\b(NONSENSE|GIBBERISH|INVALID)", raw_text):
            return "NONSENSE"
        if re.search(r"\b(GREETING|CHAT|HI|HELLO)", raw_text):
            return "GREETING"
        if re.search(r"\b(PAGE|PAGES|RANGE)", raw_text):
            return "PAGE_SPECIFIC"
        if re.search(r"\b(GLOBAL|SUMMARY|OUTLINE)", raw_text):
            return "GLOBAL_SUMMARY"
        if re.search(r"\b(BROAD|LIST|COMPARE)", raw_text):
            return "BROAD_SEARCH"
        if re.search(r"\b(SPECIFIC|PRECISE|FACT)", raw_text):
            return "SPECIFIC_SEARCH"

        print(f"[RETRIEVER_WARN] Unclear Intent: '{raw_text}'. Defaulting to SPECIFIC.")
        return "SPECIFIC_SEARCH"

    except Exception as e:
        print(f"[RETRIEVER_WARN] Classifier Error ({e}). Defaulting to SPECIFIC.")
        return "SPECIFIC_SEARCH"


# --- 1. QUERY REWRITER ---
async def contextualize_query(history: List[Dict[str, str]], latest_query: str):
    """
    Rewrites the latest query to be standalone (Async).
    """
    if not history:
        return latest_query

    history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])

    prompt_content = f"""
    Given a chat history and the latest user question which might reference context in the chat history, 
    formulate a standalone question which can be understood without the chat history. 
    
    RULES:
    1. Do NOT answer the question. 
    2. Just reformulate it if it contains pronouns.
    3. If the question is already standalone, return it exactly as is.
    4. PRESERVE CONSTRAINTS: If the user asks for a specific format, tone, page, etc., KEEP IT.
    5. GREETINGS: If the user says "Hello" or "Thanks", keep it as is.

    Chat History:
    {history_text}

    Latest User Question: 
    {latest_query}

    Standalone Question:
    """

    messages = [{"role": "user", "content": prompt_content}]
    
    # CHANGED: Added 'await'
    return await query_llm_with_fallback(messages, REWRITE_MODELS, max_tokens=200, temp=0.1)


# --- 2. MAIN GENERATOR ---
async def generate_response(context: str, query: str, history: List[Dict[str, str]] = [], mode: str = "fast"):
    """
    Generates the final answer (Async).
    """
    if mode == "fast":
        selected_models = MODELS_FAST
        temperature = 0.0 
    else:
        selected_models = MODELS_PRECISE
        temperature = 0.0
        
    if history:
        history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])
        history_block = f"RECENT CONVERSATION HISTORY:\n{history_text}\n"
    else:
        history_block = ""

    prompt_content = f"""
ROLE: You are a meticulous academic historian. Your task is to analyze the provided sources (Context) and synthesize a response to the user's inquiry.

GUIDELINES:
1. STRICT SOURCE ADHERENCE (FACTS): Derive facts ONLY from the provided Context.
2. FORMATTING PERMISSION (STYLE): You may structure the response as requested (bullets, tables, etc.).
3. CITATION REQUIREMENT: Every assertion must be backed by an inline citation: [source, page].
4. UNKNOWN INFO: If the Context does not contain the answer, reply: "Please elaborate your question further."
5. DIRECTNESS: Just answer the question.

=== FEW-SHOT EXAMPLES ===
[EXAMPLE 1: Greeting]
Query: Hello
Response: Hello, how can i help you?

[EXAMPLE 2: Standard Narrative Query]
Query: Why did Rizal leave?
Response: According to the records, Rizal departed for Spain in May 1882 primarily to complete his medical education, a departure undertaken without his parents' knowledge [Rizal_Bio.pdf, 12].

[EXAMPLE 3: Formatting/List Request]
Query: List the goals of the movement in bullet points.
Response:
The Propaganda Movement aimed to achieve the following:
* **Assimilation:** Making the Philippines a formal province of Spain [Propaganda_Movement.pdf, 45].
* **Representation:** Securing seats in the Spanish Cortes [Propaganda_Movement.pdf, 45].

NOW THE INQUIRY:

Query:
{query}

Context:
{context}

Response (Narrative with Citations):
"""

    messages = [{"role": "user", "content": prompt_content}]

    # CHANGED: Added 'await'
    return await query_llm_with_fallback(
        messages, 
        selected_models, 
        max_tokens=4000, 
        temp=temperature
    )