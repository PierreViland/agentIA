
import json
import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "mistral:latest"

SYSTEM_PROMPT = """Tu es un agent qui répond aux questions de l'utilisateur.
Réponds uniquement en français, sur une seule ligne.
Réponds toujours au format JSON : {"reponse": "ta réponse ici"}"""


def demander_au_llm(messages):
    payload = {
    "model": MODEL,
    "messages": messages,
    "stream": False,
    "format": {
        "type": "object",
        "properties": {"reponse": {"type": "string"}},
        "required": ["reponse"],
    },
    "options": {"temperature": 0, "num_predict": 300},
    }
    
    print("---Requete---")
    print(json.dumps(payload, indent=4, ensure_ascii=False))
    print("--- Fin Requete---")
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    
    
    print("---Reponse---")
    print(json.dumps(r.json(), indent=4, ensure_ascii=False))
    print("--- fin Reponse---")
  	
	
    return r.json()["message"]["content"]


def agent(question):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    brut = demander_au_llm(messages)
    
    
    
    print("Réponse :", json.loads(brut).get("reponse"))



if __name__ == "__main__":
    agent("Résume le livre écrit par Pierre Viland")


