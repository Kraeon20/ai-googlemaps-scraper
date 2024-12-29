import google.generativeai as genai
import os
from dotenv import load_dotenv
import re

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_KEY")
genai.configure(api_key=GEMINI_KEY)

# Update the template to handle both search term and quantity
template = (
    "You are tasked with extracting two pieces of information from the following user query: {user_input}. "
    "1. **Extract the core search term** that would be entered in the Google Maps search bar (e.g., restaurants, hotels, or places of interest). "
    "2. **Extract the quantity** (a number) if explicitly mentioned. If no quantity is mentioned, return 999. "
    "3. **Ignore extra details** such as adjectives, irrelevant words, or extra information. "
    "4. The extracted search term should be formatted as a location-based search term for Google Maps. "
    "5. **No Extra Content:** Do not include any additional text, comments, or explanations in your response. "
    "6. Return the results as a tuple: (search_term, quantity)."
)

def parse_with_gemini(user_input, parse_description):
    prompt = template.format(user_input=user_input, parse_description=parse_description)
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        if response.candidates and len(response.candidates) > 0:
            extracted_data = ''.join(part.text for part in response.candidates[0].content.parts).strip()
        else:
            extracted_data = ""
        
        print(f"Extracted data: {extracted_data}")

        # Attempt to extract search term and quantity from the response
        search_term, quantity = extract_search_and_quantity(extracted_data)
        return search_term, quantity
    
    except Exception as e:
        print(f"Error: {e}")
        return "Error in extracting data."

def extract_search_and_quantity(data):
    # Extract quantity if present (number)
    quantity_match = re.search(r'\b(\d+)\b', data)
    if quantity_match:
        quantity = int(quantity_match.group(1))
        data = data.replace(quantity_match.group(1), "").strip()
    else:
        quantity = 999  # Default value if no quantity is found
    
    # Clean up the search term by removing anything that's not part of the location-based search
    search_term = data.strip()
    
    # Make sure search_term is clean
    search_term = search_term.replace('"', '').replace('(', '').replace(')', '')
    
    return search_term, quantity