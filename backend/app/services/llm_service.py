import os
import time
import datetime  # <--- NEW IMPORT
import together
from together import Together

import re  # Missing in your snippet, added for regex
from typing import List, Dict, Optional

# Initialize the client
client = Together(api_key="f093074f102974466d625db36d8bd171b92df916fa78eb7b91faa9108e6ed5c2")

# --- CONFIGURATION: FALLBACK MODEL LISTS ---
# ... (Keep your existing model lists here) ...
MODELS_PRECISE = [
   
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
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


# Initialize internal client for routing (Uses the same key)
client = Together(api_key="f093074f102974466d625db36d8bd171b92df916fa78eb7b91faa9108e6ed5c2")



# --- HELPER 1: Internal Classifier ---

def _classify_query_intent(query: str) -> str:
    """
    Classifies intent using the Fallback Helper.
    """
    try:
        ROUTER_PROMPT = """
        Analyze the user's query and classify it into one of three distinct Retrieval Categories:

        1. "GLOBAL_SUMMARY": The user wants a summary, outline, or overview of the *entire* document. (e.g., "Summarize the paper", "Give me the main points", "What is the doocument about?")
        2. "BROAD_SEARCH": The user asks for a list, comparison, or explanation that requires gathering many scattered details. (e.g., "List all the themes", "What are the 5 goals?", "Compare X and Y")
        3. "SPECIFIC_SEARCH": The user asks for a precise fact, date, name, or definition. (e.g., "Who is Rizal?", "When did he leave?", "What is the capital?")
        4. "PAGE_SPECIFIC": The user explicitly asks for content from specific pages or page ranges. (e.g., "Summarize page 10", "What happens on pages 15-20?", "Read the last page")
        5. "GREETING": Conversational filler, greetings, thanks, or questions NOT requiring external information. (e.g., "Hi", "Hello", "Thank you", "Who are you?")
        6. "NONSENSE": The input is gibberish, random characters, too short to mean anything, or linguistically incoherent. (e.g., "asdf", "sdsdsd", "..." )
        User Query: "{query}"
        OUTPUT: Output ONLY the category name. No other text.
        """

        # Construct the message for the helper
        messages = [{"role": "user", "content": ROUTER_PROMPT.format(query=query)}]
        
        # CALL THE HELPER (Instead of raw client.chat.completions.create)
        raw_text = query_llm_with_fallback(
            messages=messages, 
            model_list=MODELS_ROUTER,  # Uses the fast router list
            max_tokens=15, 
            temp=0.0
        ).upper()
        
        print(f"[RETRIEVER] LLM Classifier Output: '{raw_text}'")

        if re.search(r"\b(NONSENSE|GIBBERISH|INVALID)", raw_text):
            return "NONSENSE"

        if re.search(r"\b(GREETING|CHAT|HI|HELLO)", raw_text):
            return "GREETING"
        
        # HUNT for Keywords
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

# --- HELPER: GENERIC API CALL WITH FALLBACK & LOGGING ---
def query_llm_with_fallback(messages: List[Dict], model_list: List[str], max_tokens: int = 1024, temp: float = 0.0) -> str:
    """
    Tries models in order. Logs the exact prompt to a text file before sending.
    """
    
    # --- NEW: LOGGING BLOCK ---
    try:
        # Opens (or creates) a file named 'llm_prompt_logs.txt' in append mode
        with open("llm_prompt_logs.txt", "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'='*60}\n")
            f.write(f"TIMESTAMP: {timestamp}\n")
            f.write(f"MODELS QUEUED: {model_list}\n")
            f.write("-" * 20 + " PROMPT START " + "-" * 20 + "\n")
            
            # Loop through messages to write them cleanly
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

# ... (The rest of your functions: contextualize_query and generate_response remain exactly the same) ...


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
    4. PRESERVE CONSTRAINTS: If the user asks for a specific format (table, bullet points), tone (funny, professional), page, Length, etc., YOU MUST KEEP THIS IN THE REWRITTEN QUERY.
    5. GREETINGS: If the user says "Hello" or "Thanks", keep it as is.

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

    # --- KEY UPDATE: ENHANCED SYSTEM PROMPT WITH FEW-SHOT EXAMPLES ---
    prompt_content = f"""
ROLE: You are a meticulous academic historian. Your task is to analyze the provided sources (Context) and synthesize a response to the user's inquiry.

GUIDELINES:
1. STRICT SOURCE ADHERENCE (FACTS): You must derive all historical facts, dates, names, and events ONLY from the provided Context.
2. FORMATTING PERMISSION (STYLE): You are explicitly allowed to structure the response as requested by the user (e.g., bullet points, tables, numbered lists, summaries). You may change the *format* of the information, provided the *factual content* remains strictly grounded in the Context.
3. CITATION REQUIREMENT: Every historical assertion must be backed by an inline citation: [source, page].
4. UNKNOWN INFO: If the provided archives (Context) do not contain the answer, reply strictly: "Please elaborate your question further."

6. DIRECTNESS (CRITICAL): State facts directly and confidently. DO NOT start sentences with "Based on the provided sources," "The documents state," or "According to the context." Just answer the question.

=== FEW-SHOT EXAMPLES (LEARN FROM THESE PATTERNS) ===

[EXAMPLE 1: Greeting]
Context:
[1] Source: Rizal_Bio.pdf, Page: 12
Content: Jose Rizal left for Spain in May 1882 without the knowledge of his parents, focused on finishing his medical studies.
Query: Hello
Response:
Hello, how can i help you?

[EXAMPLE 2: Standard Narrative Query]
Context:
[1] Source: Rizal_Bio.pdf, Page: 12
Content: Jose Rizal left for Spain in May 1882 without the knowledge of his parents, focused on finishing his medical studies.
Query: Why did Rizal leave?
Response:
According to the records, Rizal departed for Spain in May 1882 primarily to complete his medical education, a departure undertaken without his parents' knowledge [Rizal_Bio.pdf, 12].

[EXAMPLE 3: Formatting/List Request]
Context:
[1] Source: Propaganda_Movement.pdf, Page: 45
Content: The movement had three main goals: assimilation of the Philippines as a province of Spain, representation in the Spanish Cortes, and equality before the law.
Query: List the goals of the movement in bullet points.
Response:
The Propaganda Movement aimed to achieve the following:
* **Assimilation:** Making the Philippines a formal province of Spain [Propaganda_Movement.pdf, 45].
* **Representation:** Securing seats in the Spanish Cortes [Propaganda_Movement.pdf, 45].
* **Equality:** Ensuring Filipinos were equal to Spaniards before the law [Propaganda_Movement.pdf, 45].

[EXAMPLE 4: Negative/Unknown Constraint]
Context:
[1] Source: Rizal_Bio.pdf, Page: 12
Content: Rizal arrived in Spain in June.
Query: What did Rizal eat for dinner on his first night?
Response:
The provided documents do not contain sufficient evidence to answer this inquiry.

=======================================================

NOW THE INQUIRY:

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
        max_tokens=4000,  # UPDATED: Increased to allow for longer lists/summaries
        temp=temperature
    )

   