#!/usr/bin/env python3
"""
Agent IA minimal (BTS CIEL) : plusieurs tours pour trouver une information.

Question : "Quels ports sont ouverts sur serveur-web ?"
  Tour 1 : trouver_ip("serveur-web")      -> 192.168.1.10
  Tour 2 : trouver_ports("192.168.1.10")  -> [22, 80, 443]
  Tour 3 : réponse finale
"""

import json
import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3:latest"
MAX_TOURS = 5

# ----------------------------------------------------------------------
# Les "bases de données" (fictives, connues UNIQUEMENT par ce programme)
# ----------------------------------------------------------------------
IP = {
    "serveur-web": "192.168.1.10",
    "serveur-bdd": "192.168.1.20",
}

PORTS = {
    "192.168.1.10": [22, 80, 443],
    "192.168.1.20": [22, 3306],
}


# ----------------------------------------------------------------------
# Les outils (ils sont exécutés à l'ÉTAPE 8)
# Tous reçoivent la même clé d'argument : "valeur"
# ----------------------------------------------------------------------
def trouver_ip(args):
    return {"ip": IP.get(args["valeur"], "inconnue")}


def trouver_ports(args):
    return {"ports": PORTS.get(args["valeur"], "inconnus")}


# Table de correspondance : nom donné par le LLM -> fonction Python
TOOLS = {"trouver_ip": trouver_ip, "trouver_ports": trouver_ports}

# ----------------------------------------------------------------------
# Description des outils : seul moyen pour le LLM de savoir qu'ils existent
# ----------------------------------------------------------------------
TOOLS_DESCRIPTION = """
- trouver_ip     : prend un NOM de machine (ex. serveur-web ou serveur_DHCP), renvoie son adresse IP.
- trouver_ports  : prend une ADRESSE IP (ex. 192.168.1.1), renvoie ses ports ouverts. Ne fonctionne pas avec un nom de machine.
"""

SYSTEM_PROMPT = f"""Tu es un agent réseau. Tu ne connais aucune adresse IP ni aucun port :
tu dois utiliser les outils, un seul par tour.

Outils disponibles :
{TOOLS_DESCRIPTION}

Réponds UNIQUEMENT en JSON, avec l'un de ces deux formats :
{{"action": "outil_selection", "nom_outil": "trouver_ip", "args": {{"valeur": "xxx"}}}}
{{"action": "outil_selection", "nom_outil": "trouver_port", "args": {{"valeur": "xxx"}}}}
{{"action": "reponse", "texte": "ta réponse en français"}}

Le premier format sert à appeler n'importe quel outil : change seulement
le nom de l'outil et la valeur."""


def demander_au_llm(messages):
    # [ÉTAPE 4] DÉCISION : on envoie TOUT l'historique à Ollama.
    payload = {"model": MODEL, "messages": messages, "stream": False, "format": "json"}
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


def agent(question):
    # [ÉTAPE 1] DÉBUT : "question" est la question de l'utilisateur.

    # [ÉTAPE 2] Création de la liste messages (rôle system + rôle user).
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # [ÉTAPE 3] TEST "tour <= MAX_TOURS ?"
    # [ÉTAPE 10] "tour = tour + 1" est fait automatiquement par le for,
    # puis le programme revient ici (flèche "Tour suivant" du logigramme).
    for tour in range(1, MAX_TOURS + 1):
        print(f"\n--- Tour {tour} ---")

        # [ÉTAPE 4] DÉCISION : envoi de messages à Ollama (POST /api/chat)
        brut = demander_au_llm(messages)
        print("Le LLM répond :", brut)

        # [ÉTAPE 5] DÉCISION : on garde la réponse du LLM dans l'historique
        messages.append({"role": "assistant", "content": brut})

        # [ÉTAPE 6] DÉCISION : décodage du JSON (texte -> dictionnaire Python).
        try:
            decision = json.loads(brut)
        except json.JSONDecodeError:
            # [ÉTAPE 6b] Branche d'erreur : JSON invalide.
            print("[!] JSON invalide, on demande au LLM de se corriger.")
            messages.append({
                "role": "user",
                "content": "Ta réponse n'est pas un JSON valide. Recommence.",
            })
            continue  # retour à l'ÉTAPE 3 (tour suivant)

        # [ÉTAPE 7] TEST "action == reponse ?"
        if decision.get("action") == "reponse":
            # [ÉTAPE 12] Afficher la réponse finale (champ "texte")
            print("\n>>> Réponse finale :", decision.get("texte"))
            # [ÉTAPE 13] FIN
            return

        # [ÉTAPE 7b] Validation : est-ce bien un appel d'outil connu ?
        if decision.get("action") != "outil_selection" or decision.get("nom_outil") not in TOOLS:
            print("[!] Format inattendu, on demande au LLM de se corriger.")
            messages.append({
                "role": "user",
                "content": (
                    'Format invalide. Utilise exactement : {"action": "outil_selection", '
                    '"nom_outil": "trouver_ip" ou "trouver_ports", '
                    '"args": {"valeur": "..."}}'
                ),
            })
            continue  # retour à l'ÉTAPE 3 (tour suivant)

        # [ÉTAPE 8] ACTION : exécution de l'outil.
        # IMPORTANT : la clé lue ici doit être celle du prompt ("nom_outil").
        try:
            resultat = TOOLS[decision["nom_outil"]](decision.get("args", {}))
        except (KeyError, TypeError) as e:
            resultat = {"erreur": f"arguments invalides ({type(e).__name__} {e}), "
                                  f"reçus : {decision.get('args')}"}
        print("Outil exécuté ->", resultat)

        # [ÉTAPE 9] PERCEPTION : le résultat de l'outil est ajouté à messages
        # (rôle user). Au tour suivant, le LLM le "perçoit" et peut décider.
        messages.append({"role": "user", "content": f"Résultat : {json.dumps(resultat)}"})

    # [ÉTAPE 11] Sortie "Trop de tours" : MAX_TOURS atteint sans réponse finale.
    print("\n[Trop de tours, l'agent n'a pas conclu.]")
    # [ÉTAPE 13] FIN : fin de la fonction.


if __name__ == "__main__":
    agent("Quels ports sont ouverts sur la machine avec le nom serveur-web ?")
