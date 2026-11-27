CREATE TABLE agents  (id INTEGER PRIMARY KEY, name TEXT NOT NULL, team TEXT NOT NULL);
CREATE TABLE tickets (id TEXT PRIMARY KEY, summary TEXT NOT NULL, status TEXT NOT NULL,
                      priority TEXT NOT NULL, agent_id INTEGER REFERENCES agents(id), opened TEXT NOT NULL);
INSERT INTO agents VALUES (1,'Priya','access'),(2,'Tom','hardware'),(3,'Mei','network');
INSERT INTO tickets VALUES
 ('LL-2041','VPN token reset','open','high',1,'2026-11-20'),
 ('LL-2042','Laptop battery replaced','resolved','low',2,'2026-11-18'),
 ('LL-2043','Printer on floor 3 offline','open','medium',3,'2026-11-21'),
 ('LL-2044','Monitor flickers','open','low',2,'2026-11-22'),
 ('LL-2045','Shared drive access request','open','medium',1,'2026-11-23'),
 ('LL-2046','Wi-Fi drops in meeting room B','resolved','high',3,'2026-11-19');
