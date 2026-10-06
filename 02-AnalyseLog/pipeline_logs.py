#!/usr/bin/env python3
"""
Pipeline d'analyse de logs SSH avec conclusion rédigée par un LLM 
"""

import json
import requests
from datetime import datetime

OLLAMA_URL = "http://localhost:11434"
MODEL = "mistral:latest"

# ----------------------------------------------------------------------
# Les logs (5 profils d'IP)
#   172.18.0.4    : 6 échecs en 9 s, puis succès               -> attaque réussie
#   198.51.100.23 : 8 échecs en 11 s, aucun succès             -> attaque échouée
#   203.0.113.50  : 5 comptes testés sur 14 h, puis succès     -> attaque lente réussie
#   10.0.0.7      : 3 échecs sur le même compte, puis succès   -> activité légitime
#   10.0.0.5      : connexions normales                        -> activité légitime
# ----------------------------------------------------------------------
LOGS = [
    {"time": "2026-10-05T02:14:03", "ip": "172.18.0.4", "user": "root",   "action": "Failed"},
    {"time": "2026-10-05T02:14:05", "ip": "172.18.0.4", "user": "admin",  "action": "Failed"},
    {"time": "2026-10-05T02:14:06", "ip": "172.18.0.4", "user": "root",   "action": "Failed"},
    {"time": "2026-10-05T02:14:08", "ip": "172.18.0.4", "user": "test",   "action": "Failed"},
    {"time": "2026-10-05T02:14:09", "ip": "172.18.0.4", "user": "ubuntu", "action": "Failed"},
    {"time": "2026-10-05T02:14:11", "ip": "172.18.0.4", "user": "root",   "action": "Failed"},
    {"time": "2026-10-05T02:14:12", "ip": "172.18.0.4", "user": "root",   "action": "Accepted"},
    {"time": "2026-10-05T03:40:10", "ip": "198.51.100.23", "user": "root",     "action": "Failed"},
    {"time": "2026-10-05T03:40:12", "ip": "198.51.100.23", "user": "admin",    "action": "Failed"},
    {"time": "2026-10-05T03:40:13", "ip": "198.51.100.23", "user": "oracle",   "action": "Failed"},
    {"time": "2026-10-05T03:40:15", "ip": "198.51.100.23", "user": "postgres", "action": "Failed"},
    {"time": "2026-10-05T03:40:16", "ip": "198.51.100.23", "user": "root",     "action": "Failed"},
    {"time": "2026-10-05T03:40:18", "ip": "198.51.100.23", "user": "user",     "action": "Failed"},
    {"time": "2026-10-05T03:40:19", "ip": "198.51.100.23", "user": "guest",    "action": "Failed"},
    {"time": "2026-10-05T03:40:21", "ip": "198.51.100.23", "user": "root",     "action": "Failed"},
    {"time": "2026-10-05T01:05:00", "ip": "203.0.113.50", "user": "root",   "action": "Failed"},
    {"time": "2026-10-05T04:20:00", "ip": "203.0.113.50", "user": "admin",  "action": "Failed"},
    {"time": "2026-10-05T07:50:00", "ip": "203.0.113.50", "user": "test",   "action": "Failed"},
    {"time": "2026-10-05T11:35:00", "ip": "203.0.113.50", "user": "ubuntu", "action": "Failed"},
    {"time": "2026-10-05T14:40:00", "ip": "203.0.113.50", "user": "oracle", "action": "Failed"},
    {"time": "2026-10-05T15:10:00", "ip": "203.0.113.50", "user": "ubuntu", "action": "Accepted"},
    {"time": "2026-10-05T09:08:40", "ip": "10.0.0.7", "user": "marie", "action": "Failed"},
    {"time": "2026-10-05T09:10:15", "ip": "10.0.0.7", "user": "marie", "action": "Failed"},
    {"time": "2026-10-05T09:12:40", "ip": "10.0.0.7", "user": "marie", "action": "Failed"},
    {"time": "2026-10-05T09:12:55", "ip": "10.0.0.7", "user": "marie", "action": "Accepted"},
    {"time": "2026-10-05T08:31:02", "ip": "10.0.0.5", "user": "pierre", "action": "Accepted"},
    {"time": "2026-10-05T17:45:30", "ip": "10.0.0.5", "user": "pierre", "action": "Accepted"},
]
LOGS.sort(key=lambda l: l["time"])


# ----------------------------------------------------------------------
# ÉTAPE 1 : ANALYSE (code uniquement)
# ----------------------------------------------------------------------
def analyser_ip(ip):
    """Calcule les métriques d'une IP."""
    events = [l for l in LOGS if l["ip"] == ip]
    echecs = [l for l in events if l["action"] == "Failed"]
    t_echecs = [datetime.fromisoformat(l["time"]) for l in echecs]

    # Rythme des échecs
    ecarts = [(b - a).total_seconds() for a, b in zip(t_echecs, t_echecs[1:])]
    moyenne = round(sum(ecarts) / len(ecarts), 1) if ecarts else None

    max_60s, debut = 0, 0
    for i in range(len(t_echecs)):
        while (t_echecs[i] - t_echecs[debut]).total_seconds() > 60:
            debut += 1
        max_60s = max(max_60s, i - debut + 1)

    # Ce qui précède le premier succès
    succes = next((l for l in events if l["action"] == "Accepted"), None)
    avant = [l for l in echecs if succes and l["time"] < succes["time"]]
    dans_60s = 0
    if succes:
        t_s = datetime.fromisoformat(succes["time"])
        dans_60s = sum(1 for l in avant
                       if (t_s - datetime.fromisoformat(l["time"])).total_seconds() <= 60)

    return {
        "ip": ip,
        "failures": len(echecs),
        "success": succes is not None,
        "first_success_at": succes["time"] if succes else None,
        "distinct_users_failed": len({l["user"] for l in echecs}),
        "avg_seconds_between_failures": moyenne,
        "max_failures_in_60s": max_60s,
        "failures_before_success": len(avant),
        "failures_in_60s_before_success": dans_60s,
    }


def etape_analyse():
    ips = sorted({l["ip"] for l in LOGS})
    return [analyser_ip(ip) for ip in ips]


# ----------------------------------------------------------------------
# ÉTAPE 2 : CONCLUSION (un seul appel au LLM)
# ----------------------------------------------------------------------
VERDICTS = ["attaque réussie", "attaque échouée", "activité légitime"]

# Schéma JSON : Ollama contraint la sortie à cette structure (version 0.5 ou plus)
SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string"},
                    "verdict": {"type": "string", "enum": VERDICTS},
                    "justification": {"type": "string"},
                },
                "required": ["ip", "verdict", "justification"],
            },
        },
        "recommandations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdicts", "recommandations"],
}

SYSTEM_PROMPT = f"""Tu es un analyste de sécurité. On te fournit, pour chaque adresse IP des logs SSH,
des mesures déjà calculées. Pour CHAQUE IP, donne un verdict parmi {VERDICTS} et une
justification courte appuyée sur les mesures fournies. Termine par des recommandations.

Repères sur les mesures :
- failures_in_60s_before_success : échecs dans la minute qui précède le premier succès.
- distinct_users_failed : nombre de comptes différents pour lesquels il y a eu des échecs.
- avg_seconds_between_failures : temps moyen entre deux échecs, en secondes.

N'utilise QUE les chiffres fournis. N'invente aucune donnée. Réponds en français."""


def etape_conclusion(resultats):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(resultats, ensure_ascii=False)},
        ],
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0, "num_predict": 800},
    }
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
        r.raise_for_status()
        
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except requests.exceptions.Timeout:
        print("[!] Ollama n'a pas répondu en 300 s (voir : ollama ps).")
        return None
    return r.json()["message"]["content"]


# ----------------------------------------------------------------------
# ÉTAPE 3 : VÉRIFICATION (code) : on ne fait pas confiance au LLM sans contrôle
# ----------------------------------------------------------------------
def etape_verification(resultats, brut):
    try:
        rapport = json.loads(brut)
        verdicts = {v["ip"]: v for v in rapport["verdicts"]}
    except (json.JSONDecodeError, KeyError, TypeError):
        print("[!] Réponse du LLM illisible :", brut)
        return None, ["réponse illisible"]

    alertes = []
    par_ip = {r["ip"]: r for r in resultats}

    for ip in par_ip:
        if ip not in verdicts:
            alertes.append(f"{ip} : aucun verdict (IP oubliée par le LLM)")
    for ip, v in verdicts.items():
        if ip not in par_ip:
            alertes.append(f"{ip} : IP inventée (absente des logs)")
        elif v["verdict"] == "attaque réussie" and not par_ip[ip]["success"]:
            alertes.append(f"{ip} : verdict « attaque réussie » mais aucun succès dans les logs")
    return rapport, alertes


# ----------------------------------------------------------------------
# Programme principal
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=== ÉTAPE 1 : analyse (code) ===")
    resultats = etape_analyse()
    for r in resultats:
        print(f"  {r['ip']:15} échecs={r['failures']:2}  succès={r['success']!s:5}  "
              f"comptes={r['distinct_users_failed']}  "
              f"écart moyen={r['avg_seconds_between_failures']} s  "
              f"avant succès (60 s)={r['failures_in_60s_before_success']}")

    print("\n=== ÉTAPE 2 : conclusion (LLM, un seul appel) ===")
    brut = etape_conclusion(resultats)
    if brut is None:
        raise SystemExit(1)

    print("\n=== ÉTAPE 3 : vérification (code) ===")
    rapport, alertes = etape_verification(resultats, brut)
    if rapport:
        for v in rapport["verdicts"]:
            print(f"\n  {v['ip']} -> {v['verdict'].upper()}\n     {v['justification']}")
        print("\n  Recommandations :")
        for reco in rapport["recommandations"]:
            print(f"   - {reco}")
    print("\n  Contrôles :", "OK, aucune incohérence détectée" if not alertes else "")
    for a in alertes:
        print("   [!]", a)
