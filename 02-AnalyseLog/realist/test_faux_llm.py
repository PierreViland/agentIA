"""Test SANS Ollama : un faux LLM suit un chemin d'enquête scripté.
Il prouve que les outils + les fichiers permettent de retrouver l'attaque ;
il ne prouve PAS que mistral fera ce chemin."""
import json, sys
import agent_investigation as A

CHEMIN = {
 "realiste": [
  {"action":"search_firewall","args":{"ip":"198.51.100.99"}},
  {"action":"search_firewall","args":{"ip":"10.0.0.20"}},   # la machine attaquée (dans l'alerte) -> révèle 203.0.113.77
  {"action":"search_auth","args":{"ip":"203.0.113.77"}},
  {"action":"get_session_commands","args":{"session":"s-4101"}},
  {"action":"get_session_commands","args":{"session":"s-4102"}},
  {"action":"list_new_accounts","args":{}},
  {"action":"final_answer","summary":"L'IP 203.0.113.77 a fait du brute force puis réussi avec le compte deploy (s-4101), installé un cron via un script de 198.51.100.99 et exfiltré 640 Mo vers 198.51.100.99. Gravité élevée. Bloquer l'IP, désactiver deploy, supprimer le cron."}],
 "compte": [
  {"action":"search_auth","args":{"ip":"172.18.0.4"}},
  {"action":"get_session_commands","args":{"session":"s-1001"}},
  {"action":"list_new_accounts","args":{}},
  {"action":"final_answer","summary":"Compte backdoor créé par 172.18.0.4 en root. Gravité élevée."}],
 "telechargement": [
  {"action":"search_auth","args":{"ip":"203.0.113.50"}},
  {"action":"get_session_commands","args":{"session":"s-2001"}},
  {"action":"search_firewall","args":{"ip":"198.51.100.99"}},
  {"action":"final_answer","summary":"203.0.113.50 via ubuntu a téléchargé x.sh depuis 198.51.100.99 et exfiltré 850 Mo. Gravité élevée."}],
}
nom = sys.argv[1]
etapes = iter(json.dumps(x) for x in CHEMIN[nom])
vu = []
def faux(messages):
    vu.append(json.dumps(messages))
    return next(etapes)
A.call_llm = faux
A.DATA, V = A.charge_incident(nom)
assert "verite" not in A.DATA
rap = A.run_agent(A.DATA["alerte"])
assert rap, "pas de rapport"
assert not any("a_ne_pas_accuser" in m or "faits_attendus" in m for m in vu), "verite fuitee"
A.note_rapport(rap, V)
