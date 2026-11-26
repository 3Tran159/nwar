from pathlib import Path
from datetime import datetime
import hashlib, json, os, shutil, uuid

root=Path(r"E:\ntnu_mesh_optimization_20261030")
rb=root/"AUTONOMOUS_RECOVERY_PROMPT.md"
pf=root/"plan.json"
plan=json.loads(pf.read_text(encoding="utf-8-sig"))
before=rb.read_bytes()
oldhash=hashlib.sha256(before).hexdigest()
assert plan["recovery_policy"]["runbook_sha256"]==oldhash, "Runbook modified elsewhere"
s=before.decode("utf-8-sig")
anchor="## Warunki każdego odzyskiwania"
old="Nie uruchamiaj M11/M10 jako duplikatów i nie pomijaj niezakończonych kryteriów M12."
assert s.count(anchor)==1 and s.count(old)==1
assert "## H. Powtarzalna awaria" not in s, "Rule already present"
new="Nie uruchamiaj M11/M10 jako duplikatów. Wyjątek H pozwala na niezależną próbę innego etapu po potwierdzonej powtarzalnej awarii; M12 pozostaje wówczas nierozstrzygnięty, nie zaliczony."
s=s.replace(old,new,1)
amendment="""## H. Powtarzalna awaria: zmień parametr lub przejdź do innej symulacji
Użytkownik wyraźnie upoważnił: nie powtarzaj bez końca nieudanych uruchomień tej samej konfiguracji. Po powtarzających się awariach zmieniaj sposób diagnozy lub przechodź do innej sensownej symulacji. W tym wąskim zakresie H uściśla C/F/G; NIE znosi naukowych kryteriów, zabezpieczeń ani limitów interwencji.

Wyzwalacz: dwie niezależnie udokumentowane awarie o wspólnej sygnaturze (powtarzalny typ błędu i etap) lub wiarygodny zapis drugiej takiej awarii z wcześniejszego przebiegu. Najpierw sprawdź logi, residuals, CFL/VOF, siły, siatkę, bilans masy, GPU/RAM i dysk oraz tożsamość procesów. Świadoma pauza, licencja, sprzęt, nieweryfikowalny checkpoint, brak zasobów i STOP_ALL nie upoważniają do prób obejścia.

Plan A: na oddzielnej kopii ostatniego zweryfikowanego ZDROWEGO checkpointu wykonaj krótki, ograniczony budżetem test JEDNEJ zmiennej, oparty na hipotezie i przejrzanym workflow: dt/2 tylko dla problemu z krokiem/CFL; 20 iteracji wewnętrznych zamiast 10 tylko dla niedomkniętej iteracyjnej zbieżności; w przypadku rozpoznanej wady siatki wyłącznie osobny wariant diagnostyczny z audytem i z poszanowaniem dotychczasowej polityki M13-M15. Nie zmieniaj jednocześnie modelu, dt, iteracji, geometrii i rozdzielczości; nie obniżaj progów ani nie modyfikuj działającego kontrolera. Każdy nowy pilot ma osobną konfigurację, źródło, zapis kosztu i wynik w dzienniku. Maksymalnie DWIE różne hipotezy/testy parametru na rodzinę błędu, wliczając już dozwolony pojedynczy test dt/2 i zachowując globalny limit CZTERECH startów odzyskiwania, dwa restarty na etap i budżet czasowy. Gdy pilot działa, zweryfikuj rzeczywisty postęp; inny dt/iteracje to osobny eksperyment, nie porównywalny wynik GCI bez zgodnych referencji.

Plan B: jeżeli wariant nie pomaga albo dalsze wznowienia M12 nie mają uzasadnienia, zamiast kręcić się w kółko przejdź do następnej ZWERYFIKOWANEJ, niezależnej symulacji M11/G10_M, a później M10/W01a, albo wykonaj audyt i analizę dostępnych pól bez nowego solvera. Przełączenie jest możliwe dopiero po potwierdzonym pełnym zakończeniu/zabezpieczonym zatrzymaniu dotychczasowej próby, ustaleniu właścicieli PID, wykluczeniu oczekującego startu i konflikujących blokad, sprawdzeniu jej zapisów oraz przygotowaniu oddzielnego przetestowanego workflow. NIE omijaj ani nie przerabiaj aktywnego kontrolera, nie uruchamiaj równoległych solverów i nie usuwaj cudzych blokad. Jeśli bezpieczny start nie jest możliwy, zgłoś przeszkodę, zachowaj dane.

M12 oznacz wyraźnie jako failed/unresolved, nigdy jako stabilized. Wyniki innych siatek z odmiennym dt, stanem końcowym lub oknem to osobne dane i nie zastępują brakującej walidacji M12. Nie przechodź automatycznie do fal/C01, zachowaj sesję HF. Każdą próbę, zmianę jednej zmiennej, powód zmiany kierunku, koszt, pochodzenie checkpointu i postęp zapisz w decisions.jsonl i attempts.jsonl na E:. Powiadom użytkownika raz o faktycznym przełączeniu lub nierozwiązanej blokadzie, bez alertów o zwykłym running.

"""
s=s.replace(anchor,amendment+anchor,1)
newhash=hashlib.sha256(s.encode("utf-8")).hexdigest()
now=datetime.now().astimezone().isoformat()
backup=root/("recovery_before_adaptive_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(exist_ok=False)
shutil.copy2(rb,backup/rb.name)
shutil.copy2(pf,backup/pf.name)
plan["updated_at"]=now
plan["version"]="light-mesh-watch-4-adaptive-recovery"
plan["authorization"]+=" User additionally authorized targeted parameter change or independent simulation after repeated failure, with scientific and safety gates unchanged."
plan["recovery_policy"]["runbook_sha256"]=newhash
plan["recovery_policy"]["repeated_failure_pivot"]={"authorized":True,"trigger":"two evidenced matching failures","max_distinct_diagnostic_changes_per_failure_family":2,"all_starts_count_against_existing_global_limit":4,"one_variable_at_a_time":True,"fallback":"M11, then M10 if independent start is safe; otherwise offline analysis","no_false_M12_stabilization":True,"no_wave_autostart":True}
plan["watch_policy"]["unexpected_stop"]="Diagnose first. Follow recovery runbook H on repeated verified failures: controlled one-parameter diagnostic on separate copy, then pivot to independently prepared next mesh or offline analysis if appropriate. Preserve locks, hardware gates, wave hold, original solver and total start limit."
tmp1=root/("runbook_"+uuid.uuid4().hex+".tmp")
tmp2=root/("plan_"+uuid.uuid4().hex+".tmp")
tmp1.write_text(s,encoding="utf-8")
tmp2.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
assert json.loads(tmp2.read_text(encoding="utf-8"))["recovery_policy"]["runbook_sha256"]==newhash
os.replace(tmp1,rb)
os.replace(tmp2,pf)
with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
    f.write(json.dumps({"at":now,"event":"adaptive_recovery_authorized","runbook_sha256":newhash,"backup":str(backup),"solver_changed":False,"note":"After two confirmed matching failures: one-variable diagnostic or independent mesh, existing safety and recovery budget unchanged"},ensure_ascii=False)+"\n")
print(json.dumps({"updated":True,"new_runbook_sha256":newhash,"backup":str(backup),"plan_version":plan["version"],"solver_changed":False},ensure_ascii=False))
