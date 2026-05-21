import os
import time
import datetime  
import together
from together import Together
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()  


client = Together(
    api_key=os.getenv("TOGETHER_API_KEY")
)

# --- CONFIGURATION: FALLBACK MODEL LISTS ---
# ... (Keep your existing model lists here) ...
MODELS_PRECISE = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
]

MODELS_FAST = [
    'Qwen/Qwen2.5-7B-Instruct-Turbo',
     "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo"
]

REWRITE_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct-Turbo",
     "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1"
]


MODELS_ROUTER = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
]

def analyze_document_relevance(sample_text: str) -> bool:
    """
    Scans a small sample of a document to determine if it relates 
    to Philippine history/culture. Returns True if relevant, False otherwise.
    """
    try:
        ANALYZER_PROMPT = """
        You are a strict document gatekeeper. 
        Read the following text excerpt from the beginning of an uploaded document.
        
        Determine if the document's content is related to:
        - Philippine history
        - Philippine cultural history
        - Filipino heritage or indigenous traditions
        - Philippine historical events, figures, or literature

        Text Excerpt:
        "{sample_text}"

        OUTPUT RULES:
        Analyze carefully.
        Return ONLY the word "YES" if it is related.
        Return ONLY the word "NO" if it has absolutely nothing to do with the Philippines or its history.
        Do NOT include punctuation or explanations.
        """
        
        messages = [{"role": "user", "content": ANALYZER_PROMPT.format(sample_text=sample_text)}]
        
        # Use FAST models to save time/money, and limit output to 5 tokens.
        raw_text = query_llm_with_fallback(
            messages=messages, 
            model_list=MODELS_FAST,  
            max_tokens=5, 
            temp=0.0
        ).strip().upper()
        
        print(f"[ANALYZER] Relevance check result: '{raw_text}'")
        
        if "YES" in raw_text:
            return True
        elif "NO" in raw_text:
            return False
            
        # Default to True if the LLM output something weird
        print(f"[WARN] Unclear analyzer intent: {raw_text}. Allowing document.")
        return True

    except Exception as e:
        print(f"[WARN] Document analyzer error ({e}). Defaulting to allowing document.")
        return True # We allow the document through if the API crashes
    
    
# --- HELPER 1: Internal Classifier ---
def _classify_query_intent(query: str) -> str:
    """
    Classifies intent using the Fallback Helper.
    """
    try:
        ROUTER_PROMPT = """
        You are an intent classifier for a retrieval system focused ONLY on Philippine cultural history and Philippine history.

        First determine whether the user's query is related to:
        - Philippine history
        - Philippine culture
        - Philippine historical figures
        - Philippine historical events
        - Philippine literature, traditions, or heritage

        If the query is NOT related to Philippine cultural history or Philippine history, classify it as:
        "OUT_OF_SCOPE"

        If it IS related, classify it into ONE of the following categories:

        1. "GLOBAL_SUMMARY":
        The user wants a summary, outline, or overview of the entire document.
        Examples: "Summarize the paper", "Give me the main points", "What is the document about?"

        2. "BROAD_SEARCH":
        The user asks for a list, comparison, or explanation requiring multiple pieces of information.
        Examples: "List all the themes", "What are the five goals?", "Compare Rizal and Bonifacio"

        3. "SPECIFIC_SEARCH":
        The user asks for a precise fact, date, name, or definition.
        Examples: "Who is Jose Rizal?", "When did Rizal go to Europe?", "What is the Katipunan?"

        4. "PAGE_SPECIFIC":
        The user explicitly asks about specific pages or page ranges.
        Examples: "Summarize page 10", "What happens on pages 15-20?", "Read the last page"

        5. "GREETING":
        Conversational messages that do not require retrieval.
        Examples: "Hi", "Hello", "Thanks", "Who are you?"

        6. "NONSENSE":
        The input is gibberish or meaningless.
        Examples: "asdf", "sdsdsd", "..."

        7. "OUT_OF_SCOPE":
        The query is not about Philippine cultural history or Philippine history analyze carefully if it can be answered.
        Examples: "Explain quantum physics", "Who is Elon Musk?"

        User Query: "{query}"

        OUTPUT:
        Return ONLY the category name.
        Do NOT include explanations.
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
        
        # Convert to upper and strip whitespace to be safe
        raw_text = raw_text.strip().upper()

        if "NONSENSE" in raw_text:
            return "NONSENSE"

        if "GREETING" in raw_text or "HI" in raw_text:
            return "GREETING"
        
        if "OUT_OF_SCOPE" in raw_text or "OUT OF SCOPE" in raw_text:
            return "OUT_OF_SCOPE"

        if "PAGE_SPECIFIC" in raw_text:
            return "PAGE_SPECIFIC"
        
        if "GLOBAL_SUMMARY" in raw_text:
            return "GLOBAL_SUMMARY"
            
        if "BROAD_SEARCH" in raw_text:
            return "BROAD_SEARCH"
            
        if "SPECIFIC_SEARCH" in raw_text:
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
   # if history:
    #    history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history])
     #   history_block = f"RECENT CONVERSATION HISTORY:\n{history_text}\n"
    #else:
     #   history_block = ""

    # --- KEY UPDATE: ENHANCED SYSTEM PROMPT WITH FEW-SHOT EXAMPLES ---
    prompt_content = f"""
ROLE:
You are a meticulous academic historian specializing in Philippine history, Filipino heritage, indigenous traditions, Philippine national heroes, and historical events.

PRIMARY TASK:
Analyze the provided Context and answer the user's inquiry using ONLY the information found in the Context.

GUIDELINES:

1. GREETINGS AND CASUAL CONVERSATION
- If the user input is only a greeting or casual conversation
  (examples: "hi", "hello", "thanks", "good morning"),
  respond naturally and briefly.
- Greetings do NOT require citations.

2. SCOPE VALIDATION
- Only answer questions related to:
  - Philippine history
  - Philippine cultural history
  - Filipino heritage
  - Indigenous Filipino traditions
  - Philippine heroes and icons
  - Historical events in the Philippines
  - Philippine political history

- If the inquiry is outside this scope, respond STRICTLY with:
  "I only answer questions about Philippine cultural history and Philippine history."

3. STRICT CONTEXT ADHERENCE
- ALL historical facts, names, dates, explanations, events,
  and interpretations MUST come ONLY from the provided Context.
- NEVER use outside knowledge.
- NEVER invent or infer unsupported information.

4. MISSING INFORMATION
- If the inquiry is within scope BUT the Context does not contain
  enough information to answer the question, respond STRICTLY with:
  "The provided documents do not contain sufficient information to answer this inquiry."

5. CITATION REQUIREMENT (CRITICAL)
- EVERY historical assertion derived from the Context
  MUST include an inline citation.

- Citation format:
  [source, page]

- Examples:
  [Rizal_Bio.pdf, 12]
  [Propaganda_Movement.pdf, 45]

- If multiple sources support the same statement,
  cite all relevant sources.

6. DIRECTNESS
- State facts directly and confidently.
- DO NOT begin responses with phrases such as:
  - "Based on the provided sources"
  - "According to the context"
  - "The documents state"

7. FORMAT FLEXIBILITY
- You MAY structure the response as:
  - paragraphs
  - bullet points
  - numbered lists
  - tables
  - timelines
  - summaries

- You may change formatting style,
  but factual content MUST remain strictly grounded in Context.

8. NO CONTEXT RULE
- If the Context section is empty, null, or contains no usable historical information,
  respond STRICTLY with:
  "The provided documents do not contain sufficient information to answer this inquiry."

=======================================================

FEW-SHOT EXAMPLES

[EXAMPLE 1: Greeting]

Query:
Hello

Context:
[1] Source: Rizal_Bio.pdf, Page: 12
Content: Jose Rizal left for Spain in May 1882.

Response:
Hello, how can I help you with Philippine history today?


[EXAMPLE 2: Standard Historical Query]

Query:
Why did Rizal leave for Spain?

Context:
[1] Source: Rizal_Bio.pdf, Page: 12
Content: Jose Rizal left for Spain in May 1882 without the knowledge of his parents, focused on finishing his medical studies.

Response:
Rizal left for Spain in May 1882 to complete his medical studies, and he departed without the knowledge of his parents [Rizal_Bio.pdf, 12].


[EXAMPLE 3: Bullet Formatting]

Query:
List the goals of the Propaganda Movement.

Context:
[1] Source: Propaganda_Movement.pdf, Page: 45
Content: The movement had three main goals: assimilation of the Philippines as a province of Spain, representation in the Spanish Cortes, and equality before the law.

Response:
The Propaganda Movement aimed to achieve the following:

- **Assimilation:** Making the Philippines a province of Spain [Propaganda_Movement.pdf, 45]
- **Representation:** Securing representation in the Spanish Cortes [Propaganda_Movement.pdf, 45]
- **Equality:** Achieving equality before the law [Propaganda_Movement.pdf, 45]


[EXAMPLE 4: Missing Information]

Query:
What did Rizal eat on his first night in Spain?

Context:
[1] Source: Rizal_Bio.pdf, Page: 12
Content: Rizal arrived in Spain in June.

Response:
The provided documents do not contain sufficient information to answer this inquiry.


=======================================================

NOW THE INQUIRY

Query:
{query}

Context:
{context}

Response:
"""

    messages = [{"role": "user", "content": prompt_content}]

    # Return Response
    return query_llm_with_fallback(
        messages, 
        selected_models, 
        max_tokens=4000, 
        temp=temperature
    )

   