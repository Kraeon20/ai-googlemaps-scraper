from flask import Flask, request, render_template
from parse import parse_with_gemini
from scraper import get_google_maps_results, split_scraped_data
import google.generativeai as genai
import os

# Flask setup
app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_KEY"))

@app.route("/", methods=["GET", "POST"])
def index():
    extracted_data = ""
    search_results = ""
    ai_response = ""
    
    if request.method == "POST":
        # Check if the user is asking a question
        if "ask_question" in request.form:
            question = request.form.get("question").strip()
            if question and search_results:
                try:
                    # Process the scraped data and generate an AI response
                    data_chunks = split_scraped_data(search_results)
                    ai_response = []
                    
                    for chunk in data_chunks:
                        prompt = f"The following is some business data:\n{chunk}\n\nAnswer the following question: {question}"
                        response = genai.generate_content(prompt=prompt)
                        ai_response.append(response.candidates[0].content.strip())
                    
                    ai_response = "\n\n".join(ai_response)
                except Exception as e:
                    ai_response = f"Error generating AI response: {e}"
            else:
                ai_response = "No search results available to answer the question."
        
        # Check if the user submitted a query for scraping
        elif "query" in request.form:
            user_input = request.form.get("query").strip()
            if user_input:
                parse_description = "Extract the main search term and quantity for finding places."
                try:
                    search_term, quantity = parse_with_gemini(user_input, parse_description)
                    
                    extracted_data = {
                        "search_term": search_term,
                        "quantity": quantity
                    }
                    
                    search_results = get_google_maps_results(search_term, quantity)
                except Exception as e:
                    extracted_data = f"Error processing the query: {e}"
            else:
                extracted_data = "Please enter a valid query."
    
    return render_template("index.html", extracted_data=extracted_data, search_results=search_results, ai_response=ai_response)

if __name__ == "__main__":
    app.run(debug=True)