#!/usr/bin/env python3
"""
Exemple à DEUX TOURS, où l'outil est OBLIGATOIRE.

Contrairement à "12*7" ou "capitale de l'Italie", que le LLM connaît déjà
par cœur, ici l'information n'existe que dans notre programme. Le LLM ne
peut donc pas répondre sans appeler l'outil : la boucle à 2 tours devient
visible et nécessaire.

Tour 1 : le LLM n'a pas la réponse -> il appelle l'outil.
Tour 2 : le LLM a le résultat de l'outil -> il répond.
"""

import json
import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3:latest"
MAX_TOURS = 3


# ----------------------------------------------------------------------
# Un outil dont le résultat n'est connu QUE par notre code
# ----------------------------------------------------------------------

def code_secret(args):
    login = args.get("login", "").lower()
    codes = {
        "julie": 4821,
        "marc": 7193,
        "sofia": 2650,
    }
    return {"code": codes.get(login, "inconnu")}


TOOLS = {
    "code_secret": code_secret,
}

TOOLS_DESCRIPTION = """
- code_secret(login) : donne le code secret associé à un login.
"""

# NOTE: le "f" devant les """ est indispensable, sinon {TOOLS_DESCRIPTION}
# reste tel quel dans le texte au lieu d'être remplacé par sa valeur.
SYSTEM_PROMPT = f"""Tu es un agent qui répond aux questions de l'utilisateur.

Outils uniquement disponibles :
{TOOLS_DESCRIPTION}

Tu ne connais AUCUN code secret par toi-même : tu dois TOUJOURS utiliser
un outils disponibles

À chaque tour, réponds UNIQUEMENT en JSON, avec l'un de ces deux formats :

Pour appeler un outil :
{{"action": "outil", "nom": "<nom_outil>", "args": {{...}}}}

Pour répondre une fois que tu as le résultat :
{{"action": "reponse", "texte": "<ta réponse en français>"}}

Ne réponds jamais avec autre chose que ce JSON."""


def demander_au_llm(messages):
    payload = {"model": MODEL, "messages": messages, "stream": False, "format": "json"}
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


def agent(question):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for tour in range(1, MAX_TOURS + 1):
        print(f"\n--- Tour {tour} ---")
        print(f"(la liste messages contient {len(messages)} éléments)")

        brut = demander_au_llm(messages)
        print("Le LLM répond :", brut)
        decision = json.loads(brut)
        messages.append({"role": "assistant", "content": brut})

        if decision.get("action") == "reponse":
            print("\n>>> Réponse finale :", decision.get("texte"))
            return

        if decision.get("action") != "outil" or decision.get("nom") not in TOOLS:
            # Le LLM n'a pas respecté le format attendu : au lieu de planter
            # ou d'exécuter n'importe quoi, on le lui signale pour qu'il se
            # corrige au tour suivant.
            print("[!] Format inattendu, on demande au LLM de se corriger.")
            messages.append({
                "role": "user",
                "content": (
                    'Format invalide. Rappel strict : {"action": "outil", '
                    '"nom": "code_secret", "args": {"login": "<login>"}}'
                ),
            })
            continue

        nom_outil = decision.get("nom")
        args = decision.get("args", {})
        resultat = TOOLS[nom_outil](args)
        print(f"Outil '{nom_outil}' exécuté avec {args} -> {resultat}")

        messages.append({"role": "user", "content": f"Résultat : {json.dumps(resultat)}"})

    print("\n[Trop de tours, l'agent n'a pas conclu.]")


if __name__ == "__main__":
    agent("Quel est le code secret de Julie ?")
