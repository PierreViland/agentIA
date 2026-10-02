#!/usr/bin/env python3
"""
Exemple pédagogique : un vrai AGENT IA pour l'analyse de logs SSH.

Différence avec un pipeline classique :
- Le pipeline suit toujours les mêmes étapes, dans le même ordre.
- L'agent reçoit un objectif et une liste d'OUTILS. C'est le LLM qui décide,
  à chaque tour, quel outil appeler et avec quels arguments, en fonction de
  ce qu'il a déjà observé. La boucle s'arrête quand le LLM juge avoir
  assez d'informations (ou après un nombre maximal de tours, par sécurité).

Boucle agent : DÉCIDER -> AGIR -> OBSERVER -> (recommencer ou conclure)

Prérequis : Ollama lancé en local avec un modèle qui suit bien les
instructions de formatage JSON (ex. llama3.1, qwen2.5).
"""

import json
import re
import requests
from collections import Counter

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3:latest"
MAX_TOURS = 6  # garde-fou : on ne laisse pas l'agent boucler indéfiniment

# ----------------------------------------------------------------------
# Données simulées (remplace par de vrais appels Elasticsearch si besoin)
# ----------------------------------------------------------------------

FAKE_LOGS = [
    {"ip": "172.18.0.4", "user": "root", "action": "Failed"},
    {"ip": "172.18.0.4", "user": "root", "action": "Failed"},
    {"ip": "172.18.0.4", "user": "admin", "action": "Failed"},
    {"ip": "172.18.0.4", "user": "root", "action": "Accepted"},
    {"ip": "10.0.0.5", "user": "pierre", "action": "Accepted"},
]

# ----------------------------------------------------------------------
# OUTILS que l'agent a le droit d'utiliser
# Chaque outil est une fonction Python normale. L'agent ne les exécute
# jamais directement : il ne fait que DEMANDER à les appeler, et c'est
# notre code qui exécute réellement l'action (garde-fou important).
# ----------------------------------------------------------------------

def tool_list_source_ips(_args):
    """Retourne les IP sources et leur nombre d'événements."""
    c = Counter(l["ip"] for l in FAKE_LOGS)
    return dict(c)


def tool_count_failures(args):
    """Compte les échecs de connexion pour une IP donnée."""
    ip = args.get("ip")
    n = sum(1 for l in FAKE_LOGS if l["ip"] == ip and l["action"] == "Failed")
    return {"ip": ip, "failed_attempts": n}


def tool_check_success_after_failures(args):
    """Vérifie si une IP a fini par réussir une connexion après des échecs."""
    ip = args.get("ip")
    actions = [l["action"] for l in FAKE_LOGS if l["ip"] == ip]
    success = "Accepted" in actions
    return {"ip": ip, "eventual_success": success, "sequence": actions}


TOOLS = {
    "list_source_ips": tool_list_source_ips,
    "count_failures": tool_count_failures,
    "check_success_after_failures": tool_check_success_after_failures,
}

TOOLS_DESCRIPTION = """
- list_source_ips() : liste toutes les IP sources et leur nombre d'événements.
- count_failures(ip) : compte les tentatives échouées pour une IP donnée.
- check_success_after_failures(ip) : indique si cette IP a fini par réussir
  une connexion après des échecs (signe possible de brute force réussi).
"""

# ----------------------------------------------------------------------
# Appel au LLM
# ----------------------------------------------------------------------

def call_llm(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",  # on force une réponse JSON structurée
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


SYSTEM_PROMPT = f"""Tu es un agent SOC autonome. Objectif : déterminer si une
attaque brute force SSH a réussi dans les logs, et sur quelle IP.

Outils disponibles :
{TOOLS_DESCRIPTION}

À chaque tour, réponds UNIQUEMENT en JSON, avec l'un de ces deux formats :

Pour appeler un outil :
{{"action": "call_tool", "tool": "<nom_outil>", "args": {{...}}}}

Pour conclure l'investigation :
{{"action": "final_answer", "summary": "<ton rapport en français>"}}

Ne réponds jamais avec autre chose que ce JSON."""


# ----------------------------------------------------------------------
# Boucle agent : décider -> agir -> observer
# ----------------------------------------------------------------------

def run_agent():
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Analyse les logs SSH disponibles."},
    ]

    for tour in range(1, MAX_TOURS + 1):
        print(f"\n--- Tour {tour} ---")

        # 1) DÉCIDER : le LLM choisit une action
        print(messages)
        raw = call_llm(messages)
        print("[LLM décide]", raw)

        try:
            decision = json.loads(raw)
        except json.JSONDecodeError:
            print("[!] Réponse non JSON, on arrête par sécurité.")
            break

        messages.append({"role": "assistant", "content": raw})

        # 2) Conclusion ?
        if decision.get("action") == "final_answer":
            print("\n=== Rapport final de l'agent ===")
            print(decision.get("summary"))
            return

        # 3) AGIR : on exécute l'outil demandé (jamais le LLM directement)
        tool_name = decision.get("tool")
        args = decision.get("args", {})

        if tool_name not in TOOLS:
            observation = {"error": f"outil inconnu: {tool_name}"}
        else:
            observation = TOOLS[tool_name](args)

        print("[Outil exécuté]", tool_name, args, "->", observation)

        # 4) OBSERVER : le résultat est renvoyé au LLM pour le tour suivant
        messages.append({
            "role": "user",
            "content": f"Résultat de l'outil : {json.dumps(observation)}"
        })

    print("\n[!] Nombre maximal de tours atteint sans conclusion.")


if __name__ == "__main__":
    run_agent()
