import subprocess, json, time

def sh(cmd):
    r = subprocess.run(["docker", "exec", "stock_backend", "bash", "-c", cmd], capture_output=True, text=True)
    return r.stdout.strip()

def api(method, path, data=None, token=None):
    cmd = ["docker", "exec", "stock_backend", "curl", "-s", "-L", "-X", method,
           f"http://localhost:8000/api/v1{path}"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if data:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout

def login():
    r = subprocess.run(["docker", "exec", "stock_backend", "curl", "-s", "-X", "POST",
                       "http://localhost:8000/api/v1/auth/login",
                       "-d", "username=admin&password=admin123"],
                      capture_output=True, text=True)
    return json.loads(r.stdout)["access_token"]

def rows(fp):
    r = sh(f"python3 -c 'import pandas as pd; df=pd.read_excel(\"{fp}\"); print(len(df))'")
    return int(r) if r.isdigit() else 0

token = login()
results = []

# Test 1: Single execute WF1
sh("rm -f /app/data/excel/2026-04-12/output_*.xlsx /app/data/excel/2026-04-12/deduped.xlsx /app/data/excel/2026-04-12/并购重组2026-*.xlsx")
for i in range(7):
    api("POST", f"/workflows/1/execute-step/", {"step_index": i}, token)
wf1 = rows("/app/data/excel/2026-04-12/并购重组2026-04-12.xlsx")
results.append(("单执行-choice工作流", wf1, wf1 >= 4100))

# Test 2: Single execute WF2
sh("rm -f /app/data/excel/2026-04-09/output_*.xlsx /app/data/excel/2026-04-09/deduped.xlsx /app/data/excel/2026-04-09/并购重组*.xlsx")
for i in range(7):
    api("POST", f"/workflows/7/execute-step/", {"step_index": i}, token)
wf2 = rows("/app/data/excel/2026-04-09/并购重组2026-04-09.xlsx")
results.append(("单执行-choice工作2", wf2, wf2 >= 4100))

# Test 3: Batch parallel
br = api("POST", "/workflows/batch-run/", {"workflow_ids": [1, 7]}, token)
tid = json.loads(br).get("task_id", "")
for _ in range(40):
    time.sleep(3)
    st = json.loads(api("GET", f"/workflows/batch-status/{tid}/", None, token))
    s = st.get("status", "?")
    if s in ("completed", "partial", "failed", "cancelled"):
        break
batch_ok = (s == "completed")
results.append((f"批量并行[1,7]", s, batch_ok))

print("\n=== RESULTS ===")
all_pass = True
for name, val, ok in results:
    icon = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{icon}] {name}: {val}")
print(f"\n>>> {'ALL PASS' if all_pass else 'SOME FAILED'} <<<")
