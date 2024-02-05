from flask import Flask, jsonify, request
from flasgger import Swagger, LazyJSONEncoder, swag_from
import pandas as pd
import re
import sqlite3
import unidecode


app = Flask(__name__)
app.json_encoder = LazyJSONEncoder

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "API Documentation for Data Processing and Modelling",
        "description": "Dokumentasi API untuk Data Processing dan Modelling",
        "version": "1.0.0"
    }
}

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'docs',
            "route": '/docs.json'
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs/"
}

swagger = Swagger(app, template=swagger_template, config=swagger_config)

languages = [{'name': 'JavaScript'}, {'name': 'Python'}, {'name': 'Ruby'}]

def load_data(filename, encoding='latin-1', on_bad_lines='skip'):
    return pd.read_csv(filename, encoding=encoding, on_bad_lines='skip')

def preprocess_text(text, kamus_alay_dict, abusive_list):
    # Menghapus emotikon byte dan karakter khusus
    cleaned_text = re.sub(r'\\x[\da-fA-F]{2}|[ð¤â¦ï¿½]', '', text)

    # Hanya biarkan karakter dari a hingga z (baik huruf besar maupun kecil)
    cleaned_text = re.sub(r'[^a-zA-Z0-9]', ' ', cleaned_text)
    
    # Menghapus angka berulang
    cleaned_text = re.sub(r'\d+', '', cleaned_text)
    
    # Pecah teks menjadi kata-kata
    words = cleaned_text.lower().split()
    
    # Membersihkan kata-kata
    cleaned_words = [kamus_alay_dict.get(word, word) for word in words]
    cleaned_words = ['*' * len(word) if word in abusive_list else word for word in cleaned_words]
    cleaned_words = [word for word in cleaned_words if word not in ["pengguna", "uniform resource locator", "rt", "user:", "amp"]]

    return ' '.join(cleaned_words)


def process_data(data, kamus_alay_dict, abusive_list):
    results = []
    for tweet in data:
        cleaned_tweet = preprocess_text(tweet, kamus_alay_dict, abusive_list)
        result = {'Tweet': tweet, 'Cleaned Tweet': cleaned_tweet}
        results.append(result)
    return results

def clean_text(text):
    # Convert to lowercase
    text = text.lower()
    
    # Remove non-alphanumeric characters and convert accented characters to ASCII
    text = unidecode(re.sub(r'[^a-zA-Z0-9 ]', '', str(text)))

    # Remove specific words (e.g., 'user')
    words_to_remove = ['USER']
    text = ' '.join([word for word in text.split() if word.lower() not in words_to_remove])  
    
    return text

my_data = load_data("data.csv", encoding='latin-1')
abusive = load_data("abusive.csv", encoding='latin-1')
kamus_alay = load_data("new_kamusalay.csv", encoding='latin-1')
kamus_alay_dict = dict(zip(kamus_alay.iloc[:, 0], kamus_alay.iloc[:, 1]))
abusive_list = abusive['ABUSIVE'].tolist()
results = []

conn = sqlite3.connect("tweets.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tweets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tweet TEXT,
        cleaned_tweet TEXT
    )
''')
conn.commit()

@app.route('/clean_text', methods=['POST'])
def clean_text():
    """
    Clean Text API
    ---
    parameters:
      - name: text
        in: formData
        type: string
        required: true
        description: The text to be cleaned.
    responses:
      200:
        description: Successfully cleaned text.
        schema:
          type: object
          properties:
            status_code:
              type: integer
              description: HTTP status code
            description:
              type: string
              description: Description of the response
            data:
              type: string
              description: Cleaned text
    """
    
    cleaned_text = re.sub(r'[^a-zA-Z0-9]', ' ', cleaned_text)

    json_response = {
        'status_code': 200,
        'description': "Text Cleaning Successful",
        'data': cleaned_text,
    }

    return jsonify(json_response)

@app.route('/uploadfile', methods=['POST'])
@swag_from("docs/uploadfile.yml", methods=['POST'])
def process_upload():
    conn = sqlite3.connect("tweets.db")
    cursor = conn.cursor()
    
    final_results = []
    file = request.files['file']
    try:
        data = load_data(file, encoding='iso-8859-1')
    except:
        data = load_data(file, encoding='utf-8')
    my_data_list = data["Tweet"].tolist()
    final_results = process_data(my_data_list, kamus_alay_dict, abusive_list)
    
    for result in final_results:
        cursor.execute('''
            INSERT INTO tweets (tweet, cleaned_tweet)
            VALUES (?, ?)
        ''', (result['Tweet'], result['Cleaned Tweet']))
    conn.commit()
    
    conn.close()
    
    data["Cleaned Tweet"] = [result['Cleaned Tweet'] for result in final_results]
    data1 = data[['Tweet', 'Cleaned Tweet']].to_dict('records')
    return jsonify(data1)

if __name__ == "__main__":
    app.run(debug=1)
