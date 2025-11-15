import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
business_kind = os.getenv("BUSINESS_KIND", "business")
business_name = os.getenv("BUSINESS_NAME", "Our Store")
business_address = os.getenv("ADDRESS", "Av. Siempre Viva 742, Springfield")

if not api_key:
    raise RuntimeError("Missing required environment variable: OPENAI_API_KEY")

client = OpenAI(api_key=api_key)


def send_prompt(prompt: str, system_message: str) -> str:
    messages = []
    
    if system_message:
        messages.append({"role": "system", "content": system_message})
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.8,
        )
        
        return response.choices[0].message.content.strip()
    except Exception as exc:
        raise Exception(f"OpenAI API call failed: {exc}") from exc


def send_prompt_with_history(
    messages: list[dict[str, str]], temperature: float = 0.7
) -> str:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        
        return response.choices[0].message.content.strip()
    except Exception as exc:
        raise Exception(f"OpenAI API call failed: {exc}") from exc


def build_system_prompt(products: list[dict]) -> str:
    product_lines = []
    for product in products:
        name = product.get("name", "Unknown")
        price = product.get("price_half_quantity", 0.0)
        product_lines.append(f"- {name}: ${price:.2f} per 1/2 unit")
    
    catalog_text = "\n".join(product_lines) if product_lines else "- No products available"
    
    address_info = f"\n\nOur store address for pickup: {business_address}" if business_address else ""
    
    system_prompt = f"""You are a customer service agent for {business_name}, a {business_kind}.
You have the following products in your catalog:
{catalog_text}{address_info}

IMPORTANT INSTRUCTIONS:
- ALWAYS respond in the SAME LANGUAGE that the customer is using. Detect their language and match it.
- The prices shown are for HALF (1/2) of the product, NOT the full unit price. 
- If customers ask about price that is not 1/2 unit, calculate accordingly.
- Don't show the customer the process of calculation, just provide the final price.
- Be helpful, polite, and provide accurate information about the products and prices.

ORDER COMPLETION PROCESS:
- Once the customer confirms they don't want anything else, ask if they want delivery or pickup at the store.
- If they want DELIVERY: ask for their delivery address.
- If they want PICKUP at the store: use "{business_address}" as the address.
- When the customer confirms they don't want anything else AND you have the address (delivery or pickup), respond ONLY with a JSON object in this exact format:
{{
  "products": [
    {{"product": "product name", "quantity": quantity, "unit_price": unit_price}}
  ],
  "total_price": total_price,
  "address": "customer address OR store address for pickup"
}}

When returning the JSON, return ONLY the JSON object, no additional text, no greetings, no explanations."""
    
    return system_prompt


def chat_with_assistant(
    user_message: str, products: list[dict], conversation_history: list[dict] = None
) -> str:
    system_prompt = build_system_prompt(products)
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})
    return send_prompt_with_history(messages)
