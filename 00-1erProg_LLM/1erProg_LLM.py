
import json
import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "mistral:latest"

SYSTEM_PROMPT = """Tu es un agent qui répond aux questions de l'utilisateur.
Réponds uniquement en français, sur une seule ligne.
Réponds toujours au format JSON : {"reponse": "ta réponse ici"}"""


def demander_au_llm(messages):
    payload = {"model": MODEL, "messages": messages, "stream": False, "format": "json"}
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    print(type(r))          # <class 'requests.models.Response'>
    print(r.status_code)    # 200 si tout va bien
    print(r.headers)        # en-têtes HTTP de la réponse
    print(r.text)           # corps de la réponse, en texte brut (str)
    print(r.json())         # corps converti en dictionnaire Python (dict)
    print(r.elapsed)        # durée de la requête
    return r.json()["message"]["content"]


def agent(question):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    brut = demander_au_llm(messages)
    print("Réponse brute :", repr(brut))
    print("Réponse :", json.loads(brut).get("reponse") or data)



if __name__ == "__main__":
    agent("Comment faire le jeu soupape d'un guzzi V11")


