import logging
import json
import os
import re
from datetime import datetime

import pandas as pd
from flask import Flask, jsonify, request


app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


@app.route("/create_excel", methods=["GET", "POST"])
def create_excel():
    if request.method == "GET":
        return jsonify({
            "message": "Use POST /create_excel with a JSON body.",
            "example": {
                "fields": ["name", "amount"],
                "values": {
                    "name": ["test"],
                    "amount": [100]
                }
            }
        }), 200

    app.logger.debug("Received POST request to /create_excel")
    try:
        data = request.get_json(silent=True) or {}
        app.logger.debug("Request JSON received: %s", data)

        if isinstance(data, str):
            data = parse_json_value(data)

        fields = data.get("fields", [])
        values = parse_json_value(data.get("values", {}))

        if not isinstance(values, dict) and isinstance(fields, list):
            top_level_values = {
                field: data[field]
                for field in fields
                if field in data
            }
            if top_level_values:
                app.logger.warning("Using top-level field values because 'values' was not a JSON object.")
                values = top_level_values

        if not fields or not isinstance(fields, list):
            return jsonify({"error": "'fields' must be a non-empty list."}), 400

        if not values or not isinstance(values, dict):
            return jsonify({"error": "'values' must be a dictionary."}), 400

        expected_length = None
        for field in fields:
            if field not in values:
                return jsonify({"error": f"Missing values for field '{field}'."}), 400

            if not isinstance(values[field], list):
                return jsonify({"error": f"Values for field '{field}' must be a list."}), 400

            current_length = len(values[field])
            if expected_length is None:
                expected_length = current_length
            elif current_length != expected_length:
                return jsonify({
                    "error": f"All value lists must have the same length. Field '{field}' does not match."
                }), 400

        app.logger.debug("Fields received: %s", fields)
        app.logger.debug("Values received: %s", values)

        df_data = {field: values.get(field, [None] * expected_length) for field in fields}
        df = pd.DataFrame(df_data)

        base_filename = "output_{}.xlsx"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = base_filename.format(timestamp)
        file_path = os.path.join(DATA_DIR, filename)

        counter = 1
        while os.path.exists(file_path):
            filename = base_filename.format(f"{timestamp}_{counter}")
            file_path = os.path.join(DATA_DIR, filename)
            counter += 1

        with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)

        app.logger.debug("Excel file saved to: %s", file_path)
        return jsonify({
            "message": "File created successfully.",
            "file_path": file_path
        }), 200

    except Exception as e:
        app.logger.error("An error occurred: %s", str(e))
        return jsonify({"error": str(e)}), 500


def parse_json_value(value):
    if not isinstance(value, str):
        return value

    text = value.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        app.logger.warning("Could not parse JSON value: %s", value)
        return value


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=True)
