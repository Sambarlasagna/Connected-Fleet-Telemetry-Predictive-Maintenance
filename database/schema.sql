-- FleetGuard PostgreSQL Schema

CREATE TABLE IF NOT EXISTS machines (
    machine_id          INTEGER PRIMARY KEY,
    machine_name        VARCHAR(50) NOT NULL,
    model               VARCHAR(50) NOT NULL,
    age                 INTEGER NOT NULL,
    risk_level          VARCHAR(20) NOT NULL DEFAULT 'healthy',
    failure_probability FLOAT NOT NULL DEFAULT 0.0,
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry (
    id          SERIAL PRIMARY KEY,
    machine_id  INTEGER NOT NULL REFERENCES machines(machine_id),
    timestamp   TIMESTAMP NOT NULL,
    volt        FLOAT,
    rotate      FLOAT,
    pressure    FLOAT,
    vibration   FLOAT
);

CREATE TABLE IF NOT EXISTS predictions (
    id                  SERIAL PRIMARY KEY,
    machine_id          INTEGER NOT NULL REFERENCES machines(machine_id),
    failure_probability FLOAT NOT NULL,
    risk_level          VARCHAR(20) NOT NULL,
    recommended_action  TEXT,
    explanation         JSONB,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id          SERIAL PRIMARY KEY,
    machine_id  INTEGER NOT NULL REFERENCES machines(machine_id),
    risk_level  VARCHAR(20) NOT NULL,
    message     TEXT,
    resolved    BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_machine ON telemetry(machine_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_machine ON predictions(machine_id);
