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
    r = sh("curl -s -X POST 'http://localhost:8000/api/v1/auth/login' -d 'username=admin&password=admin123'")
    return json.loads(r)["access_token"]

def rows(fp):
    r = sh(f"python3 -c 'import pandas as pd; df=pd.read_excel(\"{fp}\"); print(len(df))'")
    return int(r) if r.isdigit() else 0

token = login()

# Clean
sh("rm -f /app/data/excel/2026-04-12/output_*.xlsx /app/data/excel/2026-04-12/deduped.xlsx /app/data/excel/2026-04-12/并购重组2026-*.xlsx")
sh("rm -f /app/data/excel/2026-04-09/output_*.xlsx /app/data/excel/2026-04-09/deduped.xlsx /app/data/excel/2026-04-09/并购重组*.xlsx")

print("=" * 60)
print("  对比测试: 单执行 vs 批量并行 (优化后)")
print("=" * 60)

# Test A: Sequential single execution (measure total time)
print("\n--- Test A: 单执行 WF1 + 单执行 WF2 (串行) ---")
t0 = time.time()
for i in range(7):
    api("POST", f"/workflows/1/execute-step/", {"step_index": i}, token)
for i in range(7):
    api("POST", f"/workflows/7/execute-step/", {"step_index": i}, token)
t_seq = time.time() - t0
wf1_rows = rows("/app/data/excel/2026-04-12/并购重组2026-04-12.xlsx")
wf2_rows = rows("/app/data/excel/2026-04-09/并购重组2026-04-09.xlsx")
print(f"  总耗时: {t_seq:.1f}s | WF1={wf1_rows}rows | WF2={wf2_rows}rows")

# Clean again for batch test
sh("rm -f /app/data/excel/2026-04-12/output_*.xlsx /app/data/excel/2026-04-12/deduped.xlsx /app/data/excel/2026-04-12/并购重组2026-*.xlsx")
sh("rm -f /app/data/excel/2026-04-09/output_*.xlsx /app/data/excel/2026-04-09/deduped.xlsx /app/data/excel/2026-04-09/并购重组*.xlsx")

# Test B: Batch parallel execution
print("\n--- Test B: 批量并行 [WF1, WF2] ---")
t0 = time.time()
br = api("POST", "/workflows/batch-run/", {"workflow_ids": [1, 7]}, token)
tid = json.loads(br).get("task_id", "")
for attempt in range(50):
    time.sleep(2)
    st = json.loads(api("GET", f"/workflows/batch-status/{tid}/", None, token))
    s = st.get("status", "?")
    c = st.get("completed", 0)
    f = st.get("failed", 0)
    tot = st.get("total", 0)
    print(f"  [{attempt+1:2d}] {s:10s} {c+f}/{tot}", end="")
    if s in ("completed", "partial", "failed", "cancelled"):
        # Print individual durations
        for res in (st.get("results") or []):
            dur = res.get("duration", 0)
            wid = res.get("workflow_id")
            rs = res.get("status")
            print(f" | WF#{wid}: {dur}s {rs}", end="")
        break
    print()
t_batch = time.time() - t0

wf1_rows_b = rows("/app/data/excel/2026-04-12/并购重组2026-04-12.xlsx")
wf2_rows_b = rows("/app/data/excel/2026-04-09/并购重组2026-04-09.xlsx")

print(f"\n{'='*60}")
print(f"  结果汇总:")
print(f"  串行单执行: {t_seq:.1f}s")
print(f"  批量并行:   {t_batch:.1f}s")
if t_seq > 0:
    speedup = t_seq / t_batch if t_batch > 0 else 0
    print(f"  加速比:     {speedup:.2f}x ({(1-speedup)*100:.0f}% faster)" if speedup > 1 else f"  加速比:     {speedup:.2f}x")
print(f"  WF1 rows:   {wf1_rows_b} | WF2 rows: {wf2_rows_b}")
print(f"  {'PASS' if wf1_rows_b >= 4100 and wf2_rows_b >= 4100 and st == 'completed' else 'FAIL'}")
