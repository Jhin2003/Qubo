import os
import time
import together
from together import Together
from typing import List, Dict

# Initialize the client
client = Together(api_key="f093074f102974466d625db36d8bd171b92df916fa78eb7b91faa9108e6ed5c2")

# --- CONFIGURATION: FALLBACK MODEL LISTS ---

# For Answering: Try the smartest model first, fall back to the fast one.
# 1. PRECISE: Starts with the heavy hitter (70B), falls back to lighter models.
MODELS_PRECISE = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",      # Primary
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",  # Fallback 1
    "mistralai/Mixtral-8x7B-Instruct-v0.1"          # Fallback 2
]

# 2. FAST: Starts with the lightweight model (8B), falls back to others.
MODELS_FAST = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",  # Primary (Fastest)
    "mistralai/Mixtral-8x7B-Instruct-v0.1",         # Fallback 1
    "meta-llama/Llama-3.3-70B-Instruct-Turbo"       # Last Resort
]

# For Rewriting: Keep as is
REWRITE_MODELS = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1"
]

# --- HELPER: GENERIC API CALL WITH FALLBACK ---
def query_llm_with_fallback(messages: List[Dict], model_list: List[str], max_tokens: int = 1024, temp: float = 0.0) -> str:
    """
    Tries models in order. If one fails (503/RateLimit), it moves to the next.
    """
    for model_name in model_list:
        try:
            # print(f"DEBUG: Attempting with model: {model_name}")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temp,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()

        except together.error.ServiceUnavailableError:
            print(f"Warning: {model_name} is overloaded (503). Switching to fallback...")
            time.sleep(1) # Brief pause before retry
            continue
            
        except together.error.RateLimitError:
            print(f"Warning: Rate limit hit on {model_name}. Switching to fallback...")
            time.sleep(2)
            continue
            
        except Exception as e:
            print(f"Unexpected error on {model_name}: {e}")
            continue

    # If all models fail
    raise Exception("All AI models are currently unavailable. Please try again later.")


# --- 1. QUERY REWRITER (The "Condense" Step) ---
async def contextualize_query(history: List[Dict[str, str]], latest_query: str):
    """
    Rewrites the latest query to be standalone based on the chat history.
    Uses 'REWRITE_MODELS' (prioritizing speed).
    """
    
    # If no history exists, no need to rewrite
    if not history:
        return latest_query

    # Format history into a string
    history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])

    prompt_content = f"""
    Given a chat history and the latest user question which might reference context in the chat history, 
    formulate a standalone question which can be understood without the chat history. 
    
    RULES:
    1. Do NOT answer the question. 
    2. Just reformulate it if it contains pronouns (he, she, it, that) referring to previous context.
    3. If the question is already standalone, return it exactly as is.

    Chat History:
    {history_text}

    Latest User Question: 
    {latest_query}

    Standalone Question:
    """

    messages = [{"role": "user", "content": prompt_content}]
    
    # Use the helper function with the REWRITE list
    return query_llm_with_fallback(messages, REWRITE_MODELS, max_tokens=200, temp=0.1)


# --- 2. MAIN GENERATOR (The "Historian" Step) ---
async def generate_response(context: str, query: str, history: List[Dict[str, str]] = [], mode: str = "fast"):
    """
    Generates the final answer using Context and History.
    Uses 'GENERATION_MODELS' (prioritizing intelligence).
    """
    if mode == "fast":
        selected_models = MODELS_FAST
        # Optional: Lower temperature for fast mode to be more deterministic/concise
        temperature = 0.0 
    else:
        # Default to precise
        selected_models = MODELS_PRECISE
        # Optional: Slightly higher temp if you want creative synthesis in precise mode
        temperature = 0.0
    # Format the history
    if history:
        history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])
        history_block = f"RECENT CONVERSATION HISTORY:\n{history_text}\n"
    else:
        history_block = ""

    prompt_content = f"""
ROLE: You are a meticulous academic historian. Your task is to analyze the provided sources (Context) and synthesize a response to the user's inquiry.

GUIDELINES:
1. STRICT SOURCE ADHERENCE: You must construct your narrative using ONLY the provided Context. Do not introduce outside historical facts, dates, or figures not present in the text.
2. CITATION REQUIREMENT: Every historical assertion must be backed by an inline citation: [source, page].
3. TONE: Maintain a formal, objective, and analytical tone suitable for historical discourse. Avoid conversational filler.
4. UNKNOWN INFO: If the provided archives (Context) do not contain the answer, reply strictly: "The provided documents do not contain sufficient evidence to answer this inquiry."
5. CONTEXT USAGE: Use the "Recent Conversation History" ONLY to understand the user's intent or continuity. Do NOT use the history as a source of facts. Facts must come from the "Context" section.

Context:
[1] Source: Rizal_Biography.pdf, Page: 12
Content: Jose Rizal left for Spain in May 1882 without the knowledge of his parents, focused on finishing his medical studies.

Question: Why did Rizal left?
Desired Output:
According to the records, Rizal departed for Spain in May 1882 primarily to complete his medical education, a departure undertaken without his parents' knowledge [Rizal_Biography.pdf, 12].

-----

NOW THE INQUIRY AND ARCHIVES:
{history_block}

Query:
{query}

Context:
{context}

Response (Narrative with Citations):
"""

    messages = [{"role": "user", "content": prompt_content}]

    # Use the helper function with the GENERATION list
    return query_llm_with_fallback(
        messages, 
        selected_models, 
        max_tokens=1024, 
        temp=temperature
    )