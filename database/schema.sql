PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS establishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin_global', 'responsable_etablissement')),
    active INTEGER DEFAULT 1,
    must_change_password INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (establishment_id) REFERENCES establishments(id)
);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER NOT NULL DEFAULT 1,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    role TEXT DEFAULT 'saisonnier',
    active INTEGER DEFAULT 1,
    weekly_target_hours REAL DEFAULT 35,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (establishment_id) REFERENCES establishments(id)
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    qr_slug TEXT NOT NULL,
    qr_token TEXT UNIQUE,
    FOREIGN KEY (establishment_id) REFERENCES establishments(id),
    UNIQUE (establishment_id, name),
    UNIQUE (establishment_id, qr_slug)
);

CREATE TABLE IF NOT EXISTS punches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER NOT NULL DEFAULT 1,
    employee_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    punch_type TEXT NOT NULL CHECK (punch_type IN ('arrivee', 'depart')),
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('qr_scan', 'manual')),
    status TEXT NOT NULL DEFAULT 'En attente de validation',
    FOREIGN KEY (establishment_id) REFERENCES establishments(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (service_id) REFERENCES services(id)
);

CREATE TABLE IF NOT EXISTS work_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER NOT NULL DEFAULT 1,
    employee_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_hours REAL,
    source TEXT NOT NULL CHECK (source IN ('qr_scan', 'manual')),
    validation_status TEXT NOT NULL DEFAULT 'En attente de validation',
    employee_comment TEXT,
    manager_comment TEXT,
    corrected_duration_hours REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (establishment_id) REFERENCES establishments(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (service_id) REFERENCES services(id)
);

CREATE TABLE IF NOT EXISTS manual_time_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER NOT NULL DEFAULT 1,
    employee_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    requested_start_time TEXT NOT NULL,
    requested_end_time TEXT NOT NULL,
    requested_duration_hours REAL NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Demande manuelle en attente',
    manager_comment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    FOREIGN KEY (establishment_id) REFERENCES establishments(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (service_id) REFERENCES services(id)
);

CREATE TABLE IF NOT EXISTS validation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER NOT NULL DEFAULT 1,
    actor_user_id INTEGER,
    work_session_id INTEGER,
    manual_request_id INTEGER,
    action TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    manager_comment TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (establishment_id) REFERENCES establishments(id),
    FOREIGN KEY (actor_user_id) REFERENCES users(id),
    FOREIGN KEY (work_session_id) REFERENCES work_sessions(id),
    FOREIGN KEY (manual_request_id) REFERENCES manual_time_requests(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    establishment_id INTEGER,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    comment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (establishment_id) REFERENCES establishments(id),
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

INSERT OR IGNORE INTO establishments (id, name, slug) VALUES
    (1, 'Camping La Peyrugue', 'la-peyrugue');

INSERT OR IGNORE INTO services (id, name, qr_slug) VALUES
    (1, 'restaurant', 'restaurant'),
    (2, 'ménage', 'menage'),
    (3, 'entretien', 'entretien');

INSERT OR IGNORE INTO employees (id, first_name, last_name, role, active) VALUES
    (1, 'Camille', 'Martin', 'saisonnier', 1),
    (2, 'Alex', 'Dubois', 'saisonnier', 1),
    (3, 'Samira', 'Petit', 'responsable', 1);
