import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id                    SERIAL PRIMARY KEY,
            title                 TEXT NOT NULL,
            description           TEXT NOT NULL,
            category              VARCHAR(20)
                                   CHECK (category IN(
                                       'zakat', 'sadaqah', 'waqf', 'lillah', 'uncategorized'
                                   )),
            category_confidence   NUMERIC(5,2)   
                                   CHECK (category_confidence BETWEEN 0 AND 100),                    
            fraud_risk_score      INTEGER
                                   CHECK (fraud_risk_score BETWEEN 0 AND 100),
            policy_risk_score     INTEGER
                                   CHECK (policy_risk_score BETWEEN 0 AND 100),
            risk_flags            JSONB,
            status                VARCHAR(30) NOT NULL DEFAULT 'pending_review'
                                   CHECK (status IN (
                                       'pending_review', 'approved', 'rejected', 'escalated'
                                   )),
            claude_analysis        JSONB,
            submitted_at           TIMESTAMP NOT NULL DEFAULT NOW(),
            reviewed_at            TIMESTAMP
            );
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS moderation_log(
            id                    SERIAL PRIMARY KEY,
            campaign_id           INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE RESTRICT,
            moderator_name        VARCHAR(100) NOT NULL,
            decision              VARCHAR(20) NOT NULL
                                  CHECK (decision IN ('approved', 'rejected', 'escalated')),
            notes                 TEXT,
            decided_at            TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    init_db()
