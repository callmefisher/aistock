import asyncio
import httpx
import json
import time

async def test():
    base = 'http://localhost:8000/api/v1'
    async with httpx.AsyncClient(base_url=base, timeout=180) as client:
        login = await client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        token = login.json().get('access_token')
        headers = {'Authorization': f'Bearer {token}'}

        resp = await client.get('/workflows/', headers=headers)
        wfs = resp.json()
        wf_ids = [w['id'] for w in wfs[:1]]

        print(f'=== 批量执行 wf_ids={wf_ids} ===')
        batch_resp = await client.post('/workflows/batch-run/', json={'workflow_ids': wf_ids}, headers=headers)
        task_id = batch_resp.json().get('task_id')
        print(f'task_id={task_id}')

        for attempt in range(40):
            time.sleep(3)
            sr = await client.get(f'/workflows/batch-status/{task_id}/', headers=headers)
            status = sr.json()
            s = status.get('status', '?')
            c = status.get('completed', 0)
            f = status.get('failed', 0)
            t = status.get('total', 0)
            print(f'  [{attempt+1:2d}] {s:10s} {c+f}/{t}')
            if s in ('completed', 'partial', 'failed', 'cancelled'):
                for r in (status.get('results') or []):
                    print(f'\n  WF#{r["workflow_id"]}: {r["status"]}')
                    for st in (r.get('steps') or []):
                        msg = st.get('message', '')[:120]
                        out = (st.get('output_file') or '')[-60:]
                        err = (st.get('error') or '')[:120]
                        info = f'msg={msg}' if msg else ''
                        info += f' out={out}' if out else ''
                        info += f' err={err}' if err else ''
                        print(f'    step[{st.get("step_index")}] {st.get("type"):20s} {st.get("status"):10s} {info}')
                break

asyncio.run(test())
