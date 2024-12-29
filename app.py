from flask import Flask, request, render_template
from parse import parse_with_gemini
from scraper import get_google_maps_results

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    extracted_data = ""
    if request.method == "POST":
        user_input = request.form.get("query").strip()
        if user_input:
            parse_description = "Extract the main search term and quantity for finding places."
            try:
                search_term, quantity = parse_with_gemini(user_input, parse_description)
                
                extracted_data = {
                    "search_term": search_term,
                    "quantity": quantity
                }
                
                get_google_maps_results(search_term, quantity)
            except Exception as e:
                extracted_data = f"Error processing the query: {e}"
        else:
            extracted_data = "Please enter a valid query."
    
    return render_template("index.html", extracted_data=extracted_data)

if __name__ == "__main__":
    app.run(debug=True)
