import json
from flask import Flask, request, render_template
from dotenv import load_dotenv
from database import get_connection
from classifier import classify_campaign
from risk_scorer import score_risk
from query_tool import ask_moderator_assistant

load_dotenv()

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("dashboard.html")


@app.route("/submit", methods=["POST"])
def submit_campaign():
    title = request.form.get("title")
    description = request.form.get("description")

    if not title or not description:
        return {"error": "Title and description are required."}, 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO campaigns (title, description)
        VALUES (%s, %s)
        RETURNING id;
        """,
        (title, description))

    campaign_id = cursor.fetchone()[0]

    conn.commit()

    try:
        classification = classify_campaign(title, description)

    except Exception as e:
        classification = {
            "category": "uncategorized",
            "confidence": 0,
            "raw_response": f"Classifier call failed: {str(e)}"
        }

    try:
        risk = score_risk(title, description, classification["category"])

    except Exception as e:
        risk = {
            "fraud_risk_score": 100,
            "policy_risk_score": 100,
            "risk_flags": ["risk_assesment_failed"],
            "raw_response": f"Risk assessment call failed: {str(e)}"
        }

    cpmbined_analysis = {
        "classification": classification,
        "risk_assesment": risk
    }

    cursor.execute(
        """
        UPDATE campaigns
        SET category = %s, 
             category_confidence = %s,
             fraud_risk_score = %s,
             policy_risk_score = %s,
             risk_flags = %s,
             claude_analysis = %s
        WHERE id = %s;
        """,
        (
            classification["category"],
            classification["confidence"],
            risk["fraud_risk_score"],
            risk["policy_risk_score"],
            json.dumps(risk["risk_flags"]),
            json.dumps(cpmbined_analysis),
            campaign_id
        )
    )

    conn.commit()

    cursor.close()
    conn.close()

    return {"message": "Campaign submitted,classified and risk-assessed successfully.",
            "campaign_id": campaign_id,
            "category": classification["category"],
            "confidence": classification["confidence"],
            "fraud_risk_score": risk["fraud_risk_score"],
            "policy_risk_score": risk["policy_risk_score"],
            "risk_flags": risk["risk_flags"]}, 201


@app.route("/dashboard", methods=["GET"])
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, description, category, category_confidence,
            fraud_risk_score, policy_risk_score, risk_flags, submitted_at
        FROM campaigns
        WHERE status = 'pending_review'
        ORDER BY submitted_at ASC;
        """
    )

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    campaigns = [dict(zip(columns, row)) for row in rows]

    cursor.close()
    conn.close()

    return {"campaigns": campaigns}, 200


@app.route("/decide/<int:campaign_id>", methods=["POST"])
def decide_campaign(campaign_id):
    moderator_name = request.form.get("moderator_name")
    decision = request.form.get("decision")
    notes = request.form.get("notes", "")

    if not moderator_name or not decision:
        return {"error": "moderator_name and decision are required."}, 400

    if decision not in ("approved", "rejected", "escalated"):
        return {"error": "decision must be one of: approved, rejected, escalated."}, 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO moderation_log (campaign_id, moderator_name, decision, notes)
        VALUES (%s, %s, %s, %s);
        """,
        (campaign_id, moderator_name, decision, notes)
    )

    cursor.execute(
        """
        UPDATE campaigns
        SET status = %s,
            reviewed_at = NOW()
        WHERE id = %s;
        """,
        (decision, campaign_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Decision recorded.", "campaign_id": campaign_id, "decision": decision}, 200


@app.route("/ask", methods=["POST"])
def ask_assistant():
    question = request.form.get("question")
    if not question:
        return {"error": "question is required."}, 400

    try:
        result = ask_moderator_assistant(question)
    except Exception as e:
        return {"error": f"Assistant call failed: {str(e)}"}, 500

    return result, 200


@app.route("/history", methods=["GET"])
def history():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT c.id, c.title, c.description, c.category, c.status,
               c.fraud_risk_score, c.policy_risk_score,
               m.moderator_name, m.decision, m.notes, m.decided_at
        FROM campaigns c
        JOIN moderation_log m ON m.campaign_id = c.id
        WHERE c.status != 'pending_review'
        ORDER BY m.decided_at DESC
        LIMIT 50;
        """
    )
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    history = [dict(zip(columns, row)) for row in rows]

    cursor.close()
    conn.close()
    return {"history": history}, 200


if __name__ == "__main__":
    app.run(debug=True, port=5001)
